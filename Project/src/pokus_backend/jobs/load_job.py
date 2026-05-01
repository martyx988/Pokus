from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class LoadJobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE_ABANDONED = "stale_abandoned"


TERMINAL_LOAD_JOB_STATES = frozenset(
    {
        LoadJobState.SUCCEEDED,
        LoadJobState.FAILED,
        LoadJobState.CANCELLED,
    }
)


def is_terminal_load_job_state(state: LoadJobState) -> bool:
    return state in TERMINAL_LOAD_JOB_STATES


@dataclass(slots=True)
class LoadJob:
    id: int | None
    idempotency_key: str
    state: LoadJobState = LoadJobState.QUEUED
    attempt_count: int = 0
    max_attempts: int = 3
    request_timeout_seconds: int = 30
    next_retry_at: datetime | None = None
    lock_token: str | None = None
    lock_acquired_at: datetime | None = None
    lock_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    stale_abandoned_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

