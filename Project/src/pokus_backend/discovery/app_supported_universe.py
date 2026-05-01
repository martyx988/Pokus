from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.db import to_sqlalchemy_url
from pokus_backend.domain.instrument_models import (
    Instrument,
    Listing,
    SupportedUniverseState,
    SupportedUniverseStatus,
)
from pokus_backend.domain.reference_models import Exchange, InstrumentType


_APP_VISIBLE_STATUSES = (
    SupportedUniverseStatus.SUPPORTED,
    SupportedUniverseStatus.NOT_YET_SIGNAL_ELIGIBLE,
    SupportedUniverseStatus.DELISTING_SUSPECTED,
)


@dataclass(frozen=True, slots=True)
class AppSupportedUniverseItem:
    exchange: str
    instrument_type: str
    symbol: str
    canonical_name: str
    support_status: str
    signal_ready: bool


def fetch_app_supported_universe(database_url: str) -> list[AppSupportedUniverseItem]:
    engine = create_engine(to_sqlalchemy_url(database_url))
    try:
        with Session(engine) as session:
            rows = session.execute(_app_supported_universe_query()).all()
    finally:
        engine.dispose()

    return [
        AppSupportedUniverseItem(
            exchange=exchange_code,
            instrument_type=instrument_type_code,
            symbol=symbol,
            canonical_name=canonical_name,
            support_status=status.value,
            signal_ready=status != SupportedUniverseStatus.NOT_YET_SIGNAL_ELIGIBLE,
        )
        for exchange_code, instrument_type_code, symbol, canonical_name, status in rows
    ]


def _app_supported_universe_query() -> Select[tuple[str, str, str, str, SupportedUniverseStatus]]:
    return (
        select(
            Exchange.code,
            InstrumentType.code,
            Listing.symbol,
            Instrument.canonical_name,
            SupportedUniverseState.status,
        )
        .join(Listing, Listing.id == SupportedUniverseState.listing_id)
        .join(Exchange, Exchange.id == Listing.exchange_id)
        .join(Instrument, Instrument.id == Listing.instrument_id)
        .join(InstrumentType, InstrumentType.id == Instrument.instrument_type_id)
        .where(SupportedUniverseState.status.in_(_APP_VISIBLE_STATUSES))
        .order_by(Exchange.code.asc(), InstrumentType.code.asc(), Listing.symbol.asc())
    )
