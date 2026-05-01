from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import psycopg


class CheckStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    MISSING = "missing"
    STALE = "stale"
    EMPTY = "empty"
    PLACEHOLDER = "placeholder"


@dataclass(frozen=True)
class HeartbeatState:
    status: CheckStatus
    last_heartbeat_at: str | None


def upsert_runtime_heartbeat(database_url: str, role: str, heartbeat_at: datetime | None = None) -> None:
    if heartbeat_at is None:
        heartbeat_at = datetime.now(UTC)
    with psycopg.connect(database_url, connect_timeout=1) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runtime_heartbeats (role, last_heartbeat_at, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (role)
                DO UPDATE SET
                    last_heartbeat_at = EXCLUDED.last_heartbeat_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (role, heartbeat_at, heartbeat_at),
            )
        conn.commit()


def collect_platform_health(
    database_url: str,
    worker_stale_after_seconds: float,
    scheduler_stale_after_seconds: float,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": CheckStatus.OK.value,
        "checks": {
            "api": {"status": CheckStatus.OK.value},
            "database": {"status": CheckStatus.OK.value},
            "worker_heartbeat": {"status": CheckStatus.MISSING.value, "last_heartbeat_at": None},
            "scheduler_heartbeat": {"status": CheckStatus.MISSING.value, "last_heartbeat_at": None},
            "queue": {"status": CheckStatus.EMPTY.value, "depth": 0, "oldest_pending_age_seconds": None},
            "backup": {
                "status": CheckStatus.PLACEHOLDER.value,
                "last_successful_backup_at": None,
            },
        },
    }
    try:
        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT now()")
                now = _ensure_utc(cur.fetchone()[0])
                heartbeats = _read_heartbeats(cur)
                queue = _read_queue_state(cur, now)
    except psycopg.Error:
        response["status"] = CheckStatus.ERROR.value
        response["checks"]["database"] = {"status": CheckStatus.ERROR.value}
        response["checks"]["queue"] = {
            "status": CheckStatus.ERROR.value,
            "depth": 0,
            "oldest_pending_age_seconds": None,
        }
        return response

    return evaluate_platform_health(
        now=now,
        worker_heartbeat_at=heartbeats.get("worker"),
        scheduler_heartbeat_at=heartbeats.get("scheduler"),
        queue_depth=queue["depth"],
        oldest_pending_age_seconds=queue["oldest_pending_age_seconds"],
        worker_stale_after_seconds=worker_stale_after_seconds,
        scheduler_stale_after_seconds=scheduler_stale_after_seconds,
    )


def evaluate_platform_health(
    *,
    now: datetime,
    worker_heartbeat_at: datetime | None,
    scheduler_heartbeat_at: datetime | None,
    queue_depth: int,
    oldest_pending_age_seconds: float | None,
    worker_stale_after_seconds: float,
    scheduler_stale_after_seconds: float,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": CheckStatus.OK.value,
        "checks": {
            "api": {"status": CheckStatus.OK.value},
            "database": {"status": CheckStatus.OK.value},
            "worker_heartbeat": {},
            "scheduler_heartbeat": {},
            "queue": {},
            "backup": {
                "status": CheckStatus.PLACEHOLDER.value,
                "last_successful_backup_at": None,
            },
        },
    }
    worker_state = _heartbeat_state(worker_heartbeat_at, now, worker_stale_after_seconds)
    scheduler_state = _heartbeat_state(scheduler_heartbeat_at, now, scheduler_stale_after_seconds)
    queue_status = CheckStatus.EMPTY
    if queue_depth > 0:
        if oldest_pending_age_seconds is not None and oldest_pending_age_seconds > 3600:
            queue_status = CheckStatus.STALE
        else:
            queue_status = CheckStatus.OK
    response["checks"]["worker_heartbeat"] = worker_state.__dict__
    response["checks"]["worker_heartbeat"]["status"] = worker_state.status.value
    response["checks"]["scheduler_heartbeat"] = scheduler_state.__dict__
    response["checks"]["scheduler_heartbeat"]["status"] = scheduler_state.status.value
    response["checks"]["queue"] = {
        "status": queue_status.value,
        "depth": queue_depth,
        "oldest_pending_age_seconds": oldest_pending_age_seconds,
    }
    degraded_states = {CheckStatus.ERROR, CheckStatus.STALE, CheckStatus.MISSING}
    if worker_state.status in degraded_states or scheduler_state.status in degraded_states or queue_status == CheckStatus.STALE:
        response["status"] = CheckStatus.ERROR.value
    return response


def _read_heartbeats(cur: psycopg.Cursor[Any]) -> dict[str, datetime]:
    cur.execute("SELECT role, last_heartbeat_at FROM runtime_heartbeats WHERE role IN ('worker', 'scheduler')")
    rows = cur.fetchall()
    return {role: _ensure_utc(last_heartbeat_at) for role, last_heartbeat_at in rows}


def _read_queue_state(cur: psycopg.Cursor[Any], now: datetime) -> dict[str, Any]:
    cur.execute(
        """
        SELECT COUNT(*), MIN(created_at)
        FROM load_jobs
        WHERE state IN ('queued', 'retry_wait')
        """
    )
    depth_raw, oldest_pending = cur.fetchone()
    depth = int(depth_raw)
    if depth == 0:
        return {"status": CheckStatus.EMPTY, "depth": 0, "oldest_pending_age_seconds": None}
    oldest = _ensure_utc(oldest_pending)
    oldest_age_seconds = max(0.0, (now - oldest).total_seconds())
    status = CheckStatus.STALE if oldest_age_seconds > 3600 else CheckStatus.OK
    return {"status": status, "depth": depth, "oldest_pending_age_seconds": round(oldest_age_seconds, 3)}


def _heartbeat_state(last_heartbeat: datetime | None, now: datetime, stale_after_seconds: float) -> HeartbeatState:
    if last_heartbeat is None:
        return HeartbeatState(status=CheckStatus.MISSING, last_heartbeat_at=None)
    heartbeat = _ensure_utc(last_heartbeat)
    age_seconds = (now - heartbeat).total_seconds()
    if age_seconds > stale_after_seconds:
        return HeartbeatState(status=CheckStatus.STALE, last_heartbeat_at=heartbeat.isoformat())
    return HeartbeatState(status=CheckStatus.OK, last_heartbeat_at=heartbeat.isoformat())


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
