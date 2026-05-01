from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.calendars.service import (
    ExchangeCalendarService,
    build_launch_exchange_calendar_service,
)
from pokus_backend.calendars.result import TradingDayStatus
from pokus_backend.jobs.load_job import LoadJobState, TERMINAL_LOAD_JOB_STATES
from pokus_backend.observability.logging import log_event

DAILY_OPEN_LOAD_TYPE = "daily_open"

_exchange_table = sa.table(
    "exchange",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
    sa.column("is_launch_active", sa.Boolean),
)
_load_jobs_table = sa.table(
    "load_jobs",
    sa.column("id", sa.BigInteger),
    sa.column("idempotency_key", sa.Text),
    sa.column("state", sa.Text),
)
_exchange_day_load_table = sa.table(
    "exchange_day_load",
    sa.column("id", sa.BigInteger),
    sa.column("exchange_id", sa.Integer),
    sa.column("job_id", sa.BigInteger),
    sa.column("trading_date", sa.Date),
    sa.column("load_type", sa.String),
    sa.column("status", sa.String),
)


@dataclass(frozen=True, slots=True)
class OpeningLoadScheduleResult:
    enqueued_count: int
    skipped_market_closed_count: int
    skipped_existing_count: int


def build_opening_load_job_idempotency_key(*, exchange_code: str, trading_date: date) -> str:
    normalized_exchange_code = exchange_code.strip().upper()
    if not normalized_exchange_code:
        raise ValueError("exchange_code must be a non-empty string")
    return f"opening-load:{normalized_exchange_code}:{trading_date.isoformat()}"


def schedule_today_opening_load_jobs(
    session: Session,
    *,
    today: date | None = None,
    calendar_service: ExchangeCalendarService | None = None,
) -> OpeningLoadScheduleResult:
    trading_date = today or datetime.now(UTC).date()
    service = calendar_service or build_launch_exchange_calendar_service()

    supported_exchanges = list(
        session.execute(
            sa.select(_exchange_table.c.id, _exchange_table.c.code)
            .where(_exchange_table.c.is_launch_active.is_(True))
            .order_by(_exchange_table.c.code.asc())
        )
    )

    enqueued_count = 0
    skipped_market_closed_count = 0
    skipped_existing_count = 0

    for exchange_id, exchange_code in supported_exchanges:
        decision = service.evaluate(exchange=exchange_code, local_date=trading_date)
        if decision.status != TradingDayStatus.EXPECTED_TRADING_DAY:
            skipped_market_closed_count += 1
            log_event(
                "worker.opening_load.schedule.skipped",
                exchange=exchange_code,
                trading_date=trading_date.isoformat(),
                reason=decision.status.value,
            )
            continue

        idempotency_key = build_opening_load_job_idempotency_key(
            exchange_code=exchange_code,
            trading_date=trading_date,
        )
        if _has_existing_exchange_day_load(
            session=session,
            exchange_id=exchange_id,
            trading_date=trading_date,
        ):
            skipped_existing_count += 1
            continue

        job_id = _find_active_job_id(session=session, idempotency_key=idempotency_key)
        if job_id is None:
            try:
                with session.begin_nested():
                    session.execute(
                        sa.insert(_load_jobs_table).values(
                            idempotency_key=idempotency_key,
                            state=LoadJobState.QUEUED.value,
                        )
                    )
            except IntegrityError:
                job_id = _find_active_job_id(session=session, idempotency_key=idempotency_key)
                if job_id is None:
                    skipped_existing_count += 1
                    continue
            else:
                job_id = _find_active_job_id(session=session, idempotency_key=idempotency_key)
                if job_id is None:
                    skipped_existing_count += 1
                    continue

        try:
            with session.begin_nested():
                session.execute(
                    sa.insert(_exchange_day_load_table).values(
                        exchange_id=exchange_id,
                        job_id=job_id,
                        trading_date=trading_date,
                        load_type=DAILY_OPEN_LOAD_TYPE,
                        status="not_started",
                    )
                )
        except IntegrityError:
            skipped_existing_count += 1
            continue

        enqueued_count += 1
        log_event(
            "worker.opening_load.enqueued",
            exchange=exchange_code,
            trading_date=trading_date.isoformat(),
            idempotency_key=idempotency_key,
            job_id=job_id,
        )

    return OpeningLoadScheduleResult(
        enqueued_count=enqueued_count,
        skipped_market_closed_count=skipped_market_closed_count,
        skipped_existing_count=skipped_existing_count,
    )


def _has_existing_exchange_day_load(*, session: Session, exchange_id: int, trading_date: date) -> bool:
    existing = session.execute(
        sa.select(_exchange_day_load_table.c.id).where(
            _exchange_day_load_table.c.exchange_id == exchange_id,
            _exchange_day_load_table.c.trading_date == trading_date,
            _exchange_day_load_table.c.load_type == DAILY_OPEN_LOAD_TYPE,
        )
    ).first()
    return existing is not None


def _find_active_job_id(*, session: Session, idempotency_key: str) -> int | None:
    terminal_values = tuple(state.value for state in TERMINAL_LOAD_JOB_STATES)
    existing = session.execute(
        sa.select(_load_jobs_table.c.id).where(
            _load_jobs_table.c.idempotency_key == idempotency_key,
            sa.not_(_load_jobs_table.c.state.in_(terminal_values)),
        )
    ).first()
    if existing is None:
        return None
    return int(existing[0])
