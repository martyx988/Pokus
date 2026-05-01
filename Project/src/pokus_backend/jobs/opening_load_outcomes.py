from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from pokus_backend.domain.load_tracking_models import ExchangeDayLoad, InstrumentLoadOutcome


@dataclass(frozen=True, slots=True)
class OpeningLoadOutcomeInput:
    has_selected_price: bool
    missing: bool = False
    stale: bool = False
    halted: bool = False
    suspended: bool = False
    late_open: bool = False
    provider_failed: bool = False


@dataclass(frozen=True, slots=True)
class OpeningLoadOutcomeClassification:
    outcome: str
    outcome_class: str
    is_terminal: bool
    failure_reason: str | None


def classify_opening_load_outcome(payload: OpeningLoadOutcomeInput) -> OpeningLoadOutcomeClassification:
    if payload.has_selected_price:
        return OpeningLoadOutcomeClassification(
            outcome="succeeded",
            outcome_class="success",
            is_terminal=True,
            failure_reason=None,
        )
    if payload.halted:
        return OpeningLoadOutcomeClassification("pending", "halted", False, "halted")
    if payload.suspended:
        return OpeningLoadOutcomeClassification("pending", "suspended", False, "suspended")
    if payload.late_open:
        return OpeningLoadOutcomeClassification("pending", "late_open", False, "late_open")
    if payload.stale:
        return OpeningLoadOutcomeClassification("failed", "stale", True, "stale")
    if payload.provider_failed:
        return OpeningLoadOutcomeClassification("failed", "provider_failed", True, "provider_failed")
    return OpeningLoadOutcomeClassification("failed", "missing", True, "missing")


def upsert_opening_load_outcome(
    session: Session,
    *,
    exchange_day_load_id: int,
    listing_id: int,
    job_id: int | None,
    classification: OpeningLoadOutcomeClassification,
    occurred_at: datetime | None = None,
) -> InstrumentLoadOutcome:
    existing = session.scalar(
        select(InstrumentLoadOutcome).where(
            InstrumentLoadOutcome.exchange_day_load_id == exchange_day_load_id,
            InstrumentLoadOutcome.listing_id == listing_id,
        )
    )
    if existing is None:
        existing = InstrumentLoadOutcome(
            exchange_day_load_id=exchange_day_load_id,
            listing_id=listing_id,
        )
        session.add(existing)

    existing.job_id = job_id
    existing.outcome = classification.outcome
    existing.outcome_class = classification.outcome_class
    existing.is_terminal = classification.is_terminal
    existing.failure_reason = classification.failure_reason
    existing.updated_at = occurred_at.astimezone(timezone.utc) if occurred_at else datetime.now(timezone.utc)
    session.flush()
    refresh_exchange_day_opening_load_aggregate(
        session,
        exchange_day_load_id=exchange_day_load_id,
        occurred_at=existing.updated_at,
    )
    return existing


def refresh_exchange_day_opening_load_aggregate(
    session: Session,
    *,
    exchange_day_load_id: int,
    occurred_at: datetime | None = None,
) -> ExchangeDayLoad:
    exchange_day_load = session.scalar(
        select(ExchangeDayLoad).where(ExchangeDayLoad.id == exchange_day_load_id)
    )
    if exchange_day_load is None:
        raise ValueError(f"unknown exchange_day_load_id: {exchange_day_load_id}")

    aggregate = session.execute(
        select(
            func.count(InstrumentLoadOutcome.id).label("outcome_count"),
            func.sum(case((InstrumentLoadOutcome.outcome == "succeeded", 1), else_=0)).label("succeeded_count"),
            func.sum(case((InstrumentLoadOutcome.outcome == "failed", 1), else_=0)).label("failed_count"),
            func.min(InstrumentLoadOutcome.updated_at).label("first_outcome_at"),
        ).where(InstrumentLoadOutcome.exchange_day_load_id == exchange_day_load_id)
    ).one()

    outcome_count = int(aggregate.outcome_count or 0)
    succeeded_count = int(aggregate.succeeded_count or 0)
    failed_count = int(aggregate.failed_count or 0)
    first_outcome_at = aggregate.first_outcome_at
    eligible_count = int(exchange_day_load.eligible_instrument_count)
    terminal_count = succeeded_count + failed_count

    if terminal_count == 0 and outcome_count == 0:
        next_status = "not_started"
    elif terminal_count < eligible_count:
        next_status = "in_progress"
    elif failed_count == 0:
        next_status = "ready"
    elif succeeded_count == 0:
        next_status = "failed"
    else:
        next_status = "partial_problematic"

    now_utc = _as_utc(occurred_at) or datetime.now(timezone.utc)

    exchange_day_load.succeeded_count = succeeded_count
    exchange_day_load.failed_count = failed_count
    exchange_day_load.status = next_status

    if next_status == "not_started":
        exchange_day_load.started_at = None
        exchange_day_load.completed_at = None
        exchange_day_load.duration_seconds = None
    else:
        exchange_day_load.started_at = _as_utc(exchange_day_load.started_at) or _as_utc(first_outcome_at) or now_utc
        if next_status in {"ready", "failed", "partial_problematic"}:
            exchange_day_load.completed_at = now_utc
            exchange_day_load.duration_seconds = max(
                0,
                int((exchange_day_load.completed_at - exchange_day_load.started_at).total_seconds()),
            )
        else:
            exchange_day_load.completed_at = None
            exchange_day_load.duration_seconds = None

    session.flush()
    return exchange_day_load


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
