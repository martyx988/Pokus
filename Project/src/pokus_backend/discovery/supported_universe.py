from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pokus_backend.domain.instrument_models import Instrument, Listing, SupportedUniverseState, SupportedUniverseStatus
from pokus_backend.domain.reference_models import Exchange, InstrumentType


@dataclass(frozen=True, slots=True)
class SupportedUniverseProjectionResult:
    supported_listing_ids: tuple[int, ...]


def project_supported_universe_state(
    session: Session,
    *,
    selected_listing_ids: Sequence[int],
    supported_exchange_codes: Sequence[str],
    supported_instrument_type_codes: Sequence[str],
) -> SupportedUniverseProjectionResult:
    scoped_listing_rows = session.execute(
        select(Listing.id, Listing.instrument_id)
        .join(Exchange, Exchange.id == Listing.exchange_id)
        .join(Instrument, Instrument.id == Listing.instrument_id)
        .join(InstrumentType, InstrumentType.id == Instrument.instrument_type_id)
        .where(Exchange.code.in_(tuple(supported_exchange_codes)))
        .where(InstrumentType.code.in_(tuple(supported_instrument_type_codes)))
    ).all()

    scoped_listing_ids = {row.id for row in scoped_listing_rows}
    selected_scoped_listing_ids = sorted(set(selected_listing_ids) & scoped_listing_ids)

    instrument_ids = session.scalars(
        select(Listing.instrument_id).where(Listing.id.in_(selected_scoped_listing_ids))
    ).all()
    if len(instrument_ids) != len(set(instrument_ids)):
        raise ValueError("selected listings must contain at most one listing per instrument")

    session.execute(
        delete(SupportedUniverseState).where(
            SupportedUniverseState.listing_id.in_(scoped_listing_ids - set(selected_scoped_listing_ids))
        )
    )

    existing_states = {
        state.listing_id: state
        for state in session.scalars(
            select(SupportedUniverseState).where(SupportedUniverseState.listing_id.in_(selected_scoped_listing_ids))
        )
    }
    for listing_id in selected_scoped_listing_ids:
        state = existing_states.get(listing_id)
        if state is None:
            session.add(
                SupportedUniverseState(
                    listing_id=listing_id,
                    status=SupportedUniverseStatus.SUPPORTED,
                )
            )
            continue
        state.status = SupportedUniverseStatus.SUPPORTED

    return SupportedUniverseProjectionResult(supported_listing_ids=tuple(selected_scoped_listing_ids))
