from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.discovery.contract import DiscoveryCandidate
from pokus_backend.domain.instrument_models import IdentifierRecord, Instrument, Listing
from pokus_backend.domain.reference_models import Exchange, InstrumentType


@dataclass(frozen=True, slots=True)
class PersistDiscoveryCandidatesResult:
    listing_ids: tuple[int, ...]


def persist_discovery_candidates(
    session: Session,
    candidates: Sequence[DiscoveryCandidate],
    *,
    provider_code: str,
) -> PersistDiscoveryCandidatesResult:
    normalized_provider_code = provider_code.strip().upper()
    if not normalized_provider_code:
        raise ValueError("provider_code must be a non-empty string")

    listing_ids: list[int] = []
    for candidate in candidates:
        exchange_id = _get_exchange_id(session=session, code=candidate.exchange)
        instrument_type_id = _get_instrument_type_id(session=session, code=candidate.instrument_type)

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
        else:
            instrument = session.get(Instrument, listing.instrument_id)
            if instrument is None:
                raise ValueError("listing references a missing instrument")
            instrument.instrument_type_id = instrument_type_id
            instrument.canonical_name = candidate.name

        _upsert_identifiers(
            session=session,
            listing=listing,
            instrument=instrument,
            provider_code=normalized_provider_code,
            stable_identifiers=candidate.stable_identifiers,
        )
        listing_ids.append(listing.id)

    return PersistDiscoveryCandidatesResult(listing_ids=tuple(listing_ids))


def _get_exchange_id(*, session: Session, code: str) -> int:
    exchange_id = session.scalar(select(Exchange.id).where(Exchange.code == code))
    if exchange_id is None:
        raise ValueError(f"Unknown exchange code: {code}")
    return exchange_id


def _get_instrument_type_id(*, session: Session, code: str) -> int:
    instrument_type_id = session.scalar(select(InstrumentType.id).where(InstrumentType.code == code))
    if instrument_type_id is None:
        raise ValueError(f"Unknown instrument type code: {code}")
    return instrument_type_id


def _upsert_identifiers(
    *,
    session: Session,
    listing: Listing,
    instrument: Instrument,
    provider_code: str,
    stable_identifiers: dict[str, str],
) -> None:
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
            continue

        existing.instrument_id = instrument.id
        existing.identifier_value = identifier_value
