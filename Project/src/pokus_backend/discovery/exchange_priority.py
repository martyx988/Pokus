from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, create_engine, func, select
from sqlalchemy.orm import Session

from pokus_backend.calendars.service import build_launch_exchange_calendar_service
from pokus_backend.db import to_sqlalchemy_url
from pokus_backend.domain.instrument_models import Listing, PriceRecord
from pokus_backend.domain.reference_models import Exchange


@dataclass(frozen=True, slots=True)
class ExchangeActivitySnapshot:
    exchange_id: int
    exchange_code: str
    trailing_average_traded_value: Decimal


def recompute_exchange_activity_priority(database_url: str, *, trailing_days: int = 60) -> int:
    if trailing_days <= 0:
        raise ValueError("trailing_days must be positive")

    engine = create_engine(to_sqlalchemy_url(database_url))
    calendar = build_launch_exchange_calendar_service()
    try:
        with Session(engine) as session:
            exchanges = session.scalars(select(Exchange).order_by(Exchange.id.asc())).all()
            if not exchanges:
                return 0

            snapshots: list[ExchangeActivitySnapshot] = []
            for exchange in exchanges:
                avg_value = _compute_trailing_average(
                    session=session,
                    exchange=exchange,
                    trailing_days=trailing_days,
                    calendar=calendar,
                )
                snapshots.append(
                    ExchangeActivitySnapshot(
                        exchange_id=exchange.id,
                        exchange_code=exchange.code,
                        trailing_average_traded_value=avg_value,
                    )
                )

            normalization_base = max((row.trailing_average_traded_value for row in snapshots), default=Decimal("0"))
            ranked = sorted(
                snapshots,
                key=lambda row: (
                    -row.trailing_average_traded_value,
                    row.exchange_code,
                ),
            )

            by_id = {exchange.id: exchange for exchange in exchanges}
            for rank, row in enumerate(ranked, start=1):
                score = Decimal("0")
                if normalization_base > 0:
                    score = row.trailing_average_traded_value / normalization_base
                exchange = by_id[row.exchange_id]
                exchange.activity_priority_rank = rank
                exchange.activity_priority_score = float(score)

            session.commit()
            return len(ranked)
    finally:
        engine.dispose()


def _compute_trailing_average(
    *,
    session: Session,
    exchange: Exchange,
    trailing_days: int,
    calendar,
) -> Decimal:
    trading_dates = _trailing_expected_dates(
        session=session,
        exchange_id=exchange.id,
        exchange_code=exchange.code,
        trailing_days=trailing_days,
        calendar=calendar,
    )
    if not trading_dates:
        return Decimal("0")

    total_value = session.scalar(_traded_value_statement(exchange_id=exchange.id, trading_dates=trading_dates))
    if total_value is None:
        return Decimal("0")
    return Decimal(total_value) / Decimal(len(trading_dates))


def _trailing_expected_dates(*, session: Session, exchange_id: int, exchange_code: str, trailing_days: int, calendar) -> list[date]:
    raw_dates = session.scalars(
        select(PriceRecord.trading_date)
        .join(Listing, Listing.id == PriceRecord.listing_id)
        .where(Listing.exchange_id == exchange_id)
        .where(PriceRecord.price_type == "historical_adjusted_close")
        .distinct()
        .order_by(PriceRecord.trading_date.desc())
    ).all()

    expected_dates: list[date] = []
    for trading_date in raw_dates:
        decision = calendar.evaluate(exchange=exchange_code, local_date=trading_date)
        if decision.status.value != "expected_trading_day":
            continue
        expected_dates.append(trading_date)
        if len(expected_dates) >= trailing_days:
            break

    return expected_dates


def _traded_value_statement(*, exchange_id: int, trading_dates: list[date]) -> Select[tuple[Decimal | None]]:
    return (
        select(func.sum(PriceRecord.value))
        .join(Listing, Listing.id == PriceRecord.listing_id)
        .where(Listing.exchange_id == exchange_id)
        .where(PriceRecord.price_type == "historical_adjusted_close")
        .where(PriceRecord.trading_date.in_(trading_dates))
    )
