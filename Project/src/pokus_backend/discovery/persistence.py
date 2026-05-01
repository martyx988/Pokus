from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.discovery.contract import DiscoveryCandidate
from pokus_backend.discovery.universe_change_events import (
    UniverseChangeContext,
    build_state_evidence,
    record_universe_change,
)
from pokus_backend.domain.instrument_models import IdentifierRecord, Instrument, Listing
from pokus_backend.domain.reference_models import Exchange, InstrumentType
from pokus_backend.domain.universe_change_models import UniverseChangeEventType


@dataclass(frozen=True, slots=True)
class PersistDiscoveryCandidatesResult:
    listing_ids: tuple[int, ...]


def persist_discovery_candidates(
    session: Session,
    candidates: Sequence[DiscoveryCandidate],
    *,
    provider_code: str,
    effective_day: date | None = None,
) -> PersistDiscoveryCandidatesResult:
    normalized_provider_code = provider_code.strip().upper()
    if not normalized_provider_code:
        raise ValueError("provider_code must be a non-empty string")

    resolved_effective_day = effective_day or date.today()
    listing_ids: list[int] = []
    for candidate in candidates:
        exchange = _get_exchange(session=session, code=candidate.exchange)
        instrument_type = _get_instrument_type(session=session, code=candidate.instrument_type)
        exchange_id = exchange.id
        instrument_type_id = instrument_type.id

        listing = session.scalar(
            select(Listing).where(
                Listing.exchange_id == exchange_id,
                Listing.symbol == candidate.symbol,
            )
        )
        if listing is None:
            instrument = Instrument(
                instrument_type_id=instrument_type_id,
                canonical_name=candidate.name,
            )
            session.add(instrument)
            session.flush()

            listing = Listing(
                instrument_id=instrument.id,
                exchange_id=exchange_id,
                symbol=candidate.symbol,
            )
            session.add(listing)
            session.flush()
            record_universe_change(
                session,
                event_type=UniverseChangeEventType.ADDED,
                effective_day=resolved_effective_day,
                context=UniverseChangeContext(
                    listing=listing,
                    instrument=instrument,
                    exchange=exchange,
                    instrument_type=instrument_type,
                ),
                reason="discovery_ingest_new_listing",
                details="New listing added from discovery candidate ingest.",
                old_state=None,
                new_state=build_state_evidence(
                    status=None,
                    symbol=listing.symbol,
                    canonical_name=instrument.canonical_name,
                    identifiers=candidate.stable_identifiers,
                ),
            )
            was_existing_listing = False
        else:
            was_existing_listing = True
            instrument = session.get(Instrument, listing.instrument_id)
            if instrument is None:
                raise ValueError("listing references a missing instrument")
            old_name = instrument.canonical_name
            old_symbol = listing.symbol
            old_identifiers = _identifier_snapshot(
                session=session,
                listing_id=listing.id,
                provider_code=normalized_provider_code,
            )
            instrument.instrument_type_id = instrument_type_id
            instrument.canonical_name = candidate.name

        identifier_changed = _upsert_identifiers(
            session=session,
            listing=listing,
            instrument=instrument,
            provider_code=normalized_provider_code,
            stable_identifiers=candidate.stable_identifiers,
        )
        if was_existing_listing:
            if old_symbol != candidate.symbol:
                record_universe_change(
                    session,
                    event_type=UniverseChangeEventType.SYMBOL_CHANGED,
                    effective_day=resolved_effective_day,
                    context=UniverseChangeContext(
                        listing=listing,
                        instrument=instrument,
                        exchange=exchange,
                        instrument_type=instrument_type,
                    ),
                    reason="discovery_symbol_change",
                    details="Listing symbol changed during discovery ingest.",
                    old_state=build_state_evidence(
                        status=None,
                        symbol=old_symbol,
                        canonical_name=old_name,
                    ),
                    new_state=build_state_evidence(
                        status=None,
                        symbol=candidate.symbol,
                        canonical_name=instrument.canonical_name,
                    ),
                )
            if old_name != instrument.canonical_name:
                record_universe_change(
                    session,
                    event_type=UniverseChangeEventType.NAME_CHANGED,
                    effective_day=resolved_effective_day,
                    context=UniverseChangeContext(
                        listing=listing,
                        instrument=instrument,
                        exchange=exchange,
                        instrument_type=instrument_type,
                    ),
                    reason="discovery_name_change",
                    details="Instrument canonical name changed during discovery ingest.",
                    old_state=build_state_evidence(
                        status=None,
                        symbol=listing.symbol,
                        canonical_name=old_name,
                    ),
                    new_state=build_state_evidence(
                        status=None,
                        symbol=listing.symbol,
                        canonical_name=instrument.canonical_name,
                    ),
                )
            if identifier_changed:
                record_universe_change(
                    session,
                    event_type=UniverseChangeEventType.IDENTIFIER_CHANGED,
                    effective_day=resolved_effective_day,
                    context=UniverseChangeContext(
                        listing=listing,
                        instrument=instrument,
                        exchange=exchange,
                        instrument_type=instrument_type,
                    ),
                    reason="discovery_identifier_change",
                    details="Stable identifiers changed during discovery ingest.",
                    old_state=build_state_evidence(
                        status=None,
                        symbol=listing.symbol,
                        canonical_name=instrument.canonical_name,
                        identifiers=old_identifiers,
                    ),
                    new_state=build_state_evidence(
                        status=None,
                        symbol=listing.symbol,
                        canonical_name=instrument.canonical_name,
                        identifiers=candidate.stable_identifiers,
                    ),
                )
        listing_ids.append(listing.id)

    return PersistDiscoveryCandidatesResult(listing_ids=tuple(listing_ids))


def _get_exchange(*, session: Session, code: str) -> Exchange:
    exchange = session.scalar(select(Exchange).where(Exchange.code == code))
    if exchange is None:
        raise ValueError(f"Unknown exchange code: {code}")
    return exchange


def _get_instrument_type(*, session: Session, code: str) -> InstrumentType:
    instrument_type = session.scalar(select(InstrumentType).where(InstrumentType.code == code))
    if instrument_type is None:
        raise ValueError(f"Unknown instrument type code: {code}")
    return instrument_type


def _upsert_identifiers(
    *,
    session: Session,
    listing: Listing,
    instrument: Instrument,
    provider_code: str,
    stable_identifiers: dict[str, str],
) -> bool:
    changed = False
    for identifier_type, identifier_value in stable_identifiers.items():
        existing = session.scalar(
            select(IdentifierRecord).where(
                IdentifierRecord.listing_id == listing.id,
                IdentifierRecord.provider_code == provider_code,
                IdentifierRecord.identifier_type == identifier_type.upper(),
            )
        )
        if existing is None:
            session.add(
                IdentifierRecord(
                    instrument_id=instrument.id,
                    listing_id=listing.id,
                    provider_code=provider_code,
                    identifier_type=identifier_type.upper(),
                    identifier_value=identifier_value,
                )
            )
            changed = True
            continue

        existing.instrument_id = instrument.id
        if existing.identifier_value != identifier_value:
            changed = True
        existing.identifier_value = identifier_value
    return changed


def _identifier_snapshot(*, session: Session, listing_id: int, provider_code: str) -> dict[str, str]:
    records = session.scalars(
        select(IdentifierRecord).where(
            IdentifierRecord.listing_id == listing_id,
            IdentifierRecord.provider_code == provider_code,
        )
    ).all()
    return {record.identifier_type.lower(): record.identifier_value for record in records}
