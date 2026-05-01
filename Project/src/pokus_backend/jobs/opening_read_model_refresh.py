from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from pokus_backend.domain.instrument_models import Listing, PriceRecord
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad
from pokus_backend.domain.publication_models import PublicationRecord


@dataclass(frozen=True, slots=True)
class AppReadinessRow:
    exchange_day_load_id: int
    exchange_id: int
    trading_date: date
    publication_status: str
    is_ready: bool
    status_updated_at: datetime | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class AppCurrentDayPriceRow:
    exchange_day_load_id: int
    exchange_id: int
    trading_date: date
    listing_id: int
    symbol: str
    value: Decimal
    currency: str


_READINESS_BY_EXCHANGE_DAY_LOAD: dict[int, AppReadinessRow] = {}
_CURRENT_DAY_PRICES_BY_EXCHANGE_DAY_LOAD: dict[int, tuple[AppCurrentDayPriceRow, ...]] = {}


def refresh_publication_read_models(
    session: Session,
    *,
    exchange_day_load_id: int,
) -> tuple[AppReadinessRow, tuple[AppCurrentDayPriceRow, ...]]:
    publication = session.scalar(
        select(PublicationRecord).where(PublicationRecord.exchange_day_load_id == exchange_day_load_id)
    )
    if publication is None:
        raise ValueError(f"missing publication record for exchange_day_load_id={exchange_day_load_id}")

    exchange_day_load = session.scalar(select(ExchangeDayLoad).where(ExchangeDayLoad.id == exchange_day_load_id))
    if exchange_day_load is None:
        raise ValueError(f"unknown exchange_day_load_id: {exchange_day_load_id}")

    readiness_row = AppReadinessRow(
        exchange_day_load_id=exchange_day_load_id,
        exchange_id=exchange_day_load.exchange_id,
        trading_date=exchange_day_load.trading_date,
        publication_status=publication.status,
        is_ready=publication.status == "ready",
        status_updated_at=publication.status_updated_at,
        published_at=publication.published_at,
    )
    _READINESS_BY_EXCHANGE_DAY_LOAD[exchange_day_load_id] = readiness_row

    if publication.status != "ready":
        _CURRENT_DAY_PRICES_BY_EXCHANGE_DAY_LOAD[exchange_day_load_id] = ()
        return readiness_row, ()

    try:
        selected_rows = session.execute(
            select(
                PriceRecord.listing_id,
                Listing.symbol,
                PriceRecord.value,
                PriceRecord.currency,
            )
            .join(Listing, Listing.id == PriceRecord.listing_id)
            .where(
                Listing.exchange_id == exchange_day_load.exchange_id,
                PriceRecord.trading_date == exchange_day_load.trading_date,
                PriceRecord.price_type == "current_day_unadjusted_open",
            )
            .order_by(PriceRecord.listing_id.asc())
        ).all()
    except OperationalError:
        _CURRENT_DAY_PRICES_BY_EXCHANGE_DAY_LOAD[exchange_day_load_id] = ()
        return readiness_row, ()

    price_rows = tuple(
        AppCurrentDayPriceRow(
            exchange_day_load_id=exchange_day_load_id,
            exchange_id=exchange_day_load.exchange_id,
            trading_date=exchange_day_load.trading_date,
            listing_id=int(row.listing_id),
            symbol=str(row.symbol),
            value=row.value,
            currency=str(row.currency),
        )
        for row in selected_rows
    )
    _CURRENT_DAY_PRICES_BY_EXCHANGE_DAY_LOAD[exchange_day_load_id] = price_rows
    return readiness_row, price_rows


def get_readiness_read_model(*, exchange_day_load_id: int) -> AppReadinessRow | None:
    return _READINESS_BY_EXCHANGE_DAY_LOAD.get(exchange_day_load_id)


def get_current_day_price_read_model(*, exchange_day_load_id: int) -> tuple[AppCurrentDayPriceRow, ...]:
    return _CURRENT_DAY_PRICES_BY_EXCHANGE_DAY_LOAD.get(exchange_day_load_id, ())
