from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from pokus_backend.domain.instrument_models import Instrument, Listing, SupportedUniverseStatus
from pokus_backend.domain.reference_models import Exchange, InstrumentType
from pokus_backend.domain.universe_change_models import UniverseChangeEventType, UniverseChangeRecord


@dataclass(frozen=True, slots=True)
class UniverseChangeContext:
    listing: Listing
    instrument: Instrument
    exchange: Exchange
    instrument_type: InstrumentType


def record_universe_change(
    session: Session,
    *,
    event_type: UniverseChangeEventType,
    effective_day: date,
    context: UniverseChangeContext,
    reason: str,
    details: str | None,
    old_state: dict[str, Any] | None,
    new_state: dict[str, Any] | None,
) -> None:
    session.add(
        UniverseChangeRecord(
            event_type=event_type,
            effective_day=effective_day,
            reason=reason,
            details=details,
            old_state_evidence=old_state,
            new_state_evidence=new_state,
            instrument_id=context.instrument.id,
            listing_id=context.listing.id,
            exchange_id=context.exchange.id,
            instrument_type_id=context.instrument_type.id,
        )
    )


def build_state_evidence(
    *,
    status: SupportedUniverseStatus | None,
    symbol: str,
    canonical_name: str,
    identifiers: dict[str, str] | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "status": None if status is None else status.value,
        "symbol": symbol,
        "canonical_name": canonical_name,
    }
    if identifiers is not None:
        evidence["identifiers"] = identifiers
    return evidence
