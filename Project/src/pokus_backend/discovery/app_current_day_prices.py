from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.db import to_sqlalchemy_url
from pokus_backend.domain.instrument_models import Listing, PriceRecord
from pokus_backend.domain.reference_models import Exchange
from pokus_backend.discovery.app_exchange_readiness import fetch_current_app_exchange_readiness
from pokus_backend.jobs import get_current_day_price_read_model, list_readiness_read_models


@dataclass(frozen=True, slots=True)
class AppCurrentDayPriceValue:
    listing_id: int
    symbol: str
    value: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class AppCurrentDayPriceItem:
    exchange: str
    trading_date: str
    current_day_prices: tuple[AppCurrentDayPriceValue, ...]


def fetch_current_app_exchange_current_day_prices(
    database_url: str,
    *,
    exchange_code: str,
) -> AppCurrentDayPriceItem | None:
    exchange = _resolve_exchange(database_url, exchange_code=exchange_code)
    readiness_row = _resolve_current_readiness_row(exchange_id=exchange.id)
    if readiness_row is None:
        readiness_item = fetch_current_app_exchange_readiness(database_url, exchange_code=exchange.code)
        if readiness_item is None or not readiness_item.publication_available:
            return None
        trading_date = date.fromisoformat(readiness_item.trading_date)
    else:
        if not readiness_row.is_ready:
            return None
        trading_date = readiness_row.trading_date

    if readiness_row is None:
        price_rows = _load_current_day_prices_from_database(
            database_url=database_url,
            exchange_id=exchange.id,
            trading_date=trading_date,
        )
        if not price_rows:
            return None
        return AppCurrentDayPriceItem(
            exchange=exchange.code,
            trading_date=trading_date.isoformat(),
            current_day_prices=price_rows,
        )

    if not readiness_row.is_ready:
        return None

    price_rows = get_current_day_price_read_model(exchange_day_load_id=readiness_row.exchange_day_load_id)
    if not price_rows:
        price_rows = _load_current_day_prices_from_database(
            database_url=database_url,
            exchange_id=exchange.id,
            trading_date=readiness_row.trading_date,
        )
    if not price_rows:
        return None

    return AppCurrentDayPriceItem(
        exchange=exchange.code,
        trading_date=readiness_row.trading_date.isoformat(),
        current_day_prices=tuple(
            AppCurrentDayPriceValue(
                listing_id=row.listing_id,
                symbol=row.symbol,
                value=row.value,
                currency=row.currency,
            )
            for row in price_rows
        ),
    )


def _resolve_exchange(database_url: str, *, exchange_code: str) -> Exchange:
    normalized_code = exchange_code.strip().upper()
    if not normalized_code:
        raise ValueError("Exchange code is required.")

    engine = create_engine(to_sqlalchemy_url(database_url))
    try:
        with Session(engine) as session:
            exchange = session.scalar(select(Exchange).where(Exchange.code == normalized_code))
            if exchange is None:
                raise ValueError(f"Unknown exchange code: {normalized_code}")
            return exchange
    finally:
        engine.dispose()


def _resolve_current_readiness_row(*, exchange_id: int):
    current_row = None
    for row in list_readiness_read_models():
        if row.exchange_id != exchange_id:
            continue
        if current_row is None or row.trading_date > current_row.trading_date:
            current_row = row
    return current_row


def _load_current_day_prices_from_database(
    *,
    database_url: str,
    exchange_id: int,
    trading_date: date,
) -> tuple[AppCurrentDayPriceValue, ...]:
    engine = create_engine(to_sqlalchemy_url(database_url))
    try:
        with Session(engine) as session:
            rows = session.execute(
                select(
                    PriceRecord.listing_id,
                    Listing.symbol,
                    PriceRecord.value,
                    PriceRecord.currency,
                )
                .join(Listing, Listing.id == PriceRecord.listing_id)
                .where(
                    Listing.exchange_id == exchange_id,
                    PriceRecord.trading_date == trading_date,
                    PriceRecord.price_type == "current_day_unadjusted_open",
                )
                .order_by(PriceRecord.listing_id.asc())
            ).all()
            return tuple(
                AppCurrentDayPriceValue(
                    listing_id=int(row.listing_id),
                    symbol=str(row.symbol),
                    value=row.value,
                    currency=str(row.currency),
                )
                for row in rows
            )
    finally:
        engine.dispose()
