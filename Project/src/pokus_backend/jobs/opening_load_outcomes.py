from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.load_tracking_models import InstrumentLoadOutcome


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
    return existing
