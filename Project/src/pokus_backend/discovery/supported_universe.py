from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from pokus_backend.discovery.universe_change_events import (
    UniverseChangeContext,
    build_state_evidence,
    record_universe_change,
)
from pokus_backend.domain.instrument_models import Instrument, Listing, SupportedUniverseState, SupportedUniverseStatus
from pokus_backend.domain.reference_models import Exchange, InstrumentType
from pokus_backend.domain.universe_change_models import UniverseChangeEventType


@dataclass(frozen=True, slots=True)
class SupportedUniverseProjectionResult:
    supported_listing_ids: tuple[int, ...]


def project_supported_universe_state(
    session: Session,
    *,
    selected_listing_ids: Sequence[int],
    supported_exchange_codes: Sequence[str],
    supported_instrument_type_codes: Sequence[str],
    effective_day: date | None = None,
) -> SupportedUniverseProjectionResult:
    resolved_effective_day = effective_day or date.today()
    scoped_listing_rows = session.execute(
        select(Listing, Instrument, Exchange, InstrumentType)
        .join(Exchange, Exchange.id == Listing.exchange_id)
        .join(Instrument, Instrument.id == Listing.instrument_id)
        .join(InstrumentType, InstrumentType.id == Instrument.instrument_type_id)
        .where(Exchange.code.in_(tuple(supported_exchange_codes)))
        .where(InstrumentType.code.in_(tuple(supported_instrument_type_codes)))
    ).all()

    scoped_listing_ids = {row[0].id for row in scoped_listing_rows}
    selected_scoped_listing_ids = sorted(set(selected_listing_ids) & scoped_listing_ids)
    context_by_listing_id = {
        row[0].id: UniverseChangeContext(
            listing=row[0],
            instrument=row[1],
            exchange=row[2],
            instrument_type=row[3],
        )
        for row in scoped_listing_rows
    }

    instrument_ids = session.scalars(
        select(Listing.instrument_id).where(Listing.id.in_(selected_scoped_listing_ids))
    ).all()
    if len(instrument_ids) != len(set(instrument_ids)):
        raise ValueError("selected listings must contain at most one listing per instrument")

    removed_listing_ids = scoped_listing_ids - set(selected_scoped_listing_ids)
    removable_states = session.scalars(
        select(SupportedUniverseState).where(SupportedUniverseState.listing_id.in_(removed_listing_ids))
    ).all()
    for removed_state in removable_states:
        context = context_by_listing_id.get(removed_state.listing_id)
        if context is None:
            continue
        event_type = (
            UniverseChangeEventType.EXCLUDED
            if removed_state.status == SupportedUniverseStatus.SUPPORTED
            else UniverseChangeEventType.DEGRADED
        )
        record_universe_change(
            session,
            event_type=event_type,
            effective_day=resolved_effective_day,
            context=context,
            reason="supported_universe_listing_unselected",
            details="Listing dropped from selected scoped universe state.",
            old_state=build_state_evidence(
                status=removed_state.status,
                symbol=context.listing.symbol,
                canonical_name=context.instrument.canonical_name,
            ),
            new_state=build_state_evidence(
                status=SupportedUniverseStatus.REMOVED,
                symbol=context.listing.symbol,
                canonical_name=context.instrument.canonical_name,
            ),
        )
        record_universe_change(
            session,
            event_type=UniverseChangeEventType.REMOVED,
            effective_day=resolved_effective_day,
            context=context,
            reason="supported_universe_state_removed",
            details="Supported universe state row removed for unselected listing.",
            old_state=build_state_evidence(
                status=removed_state.status,
                symbol=context.listing.symbol,
                canonical_name=context.instrument.canonical_name,
            ),
            new_state=build_state_evidence(
                status=SupportedUniverseStatus.REMOVED,
                symbol=context.listing.symbol,
                canonical_name=context.instrument.canonical_name,
            ),
        )

    session.execute(
        delete(SupportedUniverseState).where(
            SupportedUniverseState.listing_id.in_(removed_listing_ids)
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
            context = context_by_listing_id.get(listing_id)
            if context is None:
                continue
            session.add(
                SupportedUniverseState(
                    listing_id=listing_id,
                    status=SupportedUniverseStatus.SUPPORTED,
                )
            )
            record_universe_change(
                session,
                event_type=UniverseChangeEventType.ADDED,
                effective_day=resolved_effective_day,
                context=context,
                reason="supported_universe_listing_added",
                details="Listing entered selected supported universe.",
                old_state=build_state_evidence(
                    status=None,
                    symbol=context.listing.symbol,
                    canonical_name=context.instrument.canonical_name,
                ),
                new_state=build_state_evidence(
                    status=SupportedUniverseStatus.SUPPORTED,
                    symbol=context.listing.symbol,
                    canonical_name=context.instrument.canonical_name,
                ),
            )
            continue
        old_status = state.status
        state.status = SupportedUniverseStatus.SUPPORTED
        if old_status != SupportedUniverseStatus.SUPPORTED:
            context = context_by_listing_id.get(listing_id)
            if context is None:
                continue
            record_universe_change(
                session,
                event_type=UniverseChangeEventType.RESTORED,
                effective_day=resolved_effective_day,
                context=context,
                reason="supported_universe_status_restored",
                details="Listing support-state restored to supported.",
                old_state=build_state_evidence(
                    status=old_status,
                    symbol=context.listing.symbol,
                    canonical_name=context.instrument.canonical_name,
                ),
                new_state=build_state_evidence(
                    status=SupportedUniverseStatus.SUPPORTED,
                    symbol=context.listing.symbol,
                    canonical_name=context.instrument.canonical_name,
                ),
            )

    return SupportedUniverseProjectionResult(supported_listing_ids=tuple(selected_scoped_listing_ids))
