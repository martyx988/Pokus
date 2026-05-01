from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.db import to_sqlalchemy_url
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad
from pokus_backend.domain.publication_models import PublicationRecord
from pokus_backend.domain.reference_models import Exchange
from pokus_backend.jobs import list_readiness_read_models


@dataclass(frozen=True, slots=True)
class AppExchangeReadinessItem:
    exchange: str
    trading_date: str
    readiness_state: str
    publication_status: str
    publication_available: bool


def fetch_app_exchange_readiness(database_url: str, *, exchange_codes: tuple[str, ...] | None = None) -> list[AppExchangeReadinessItem]:
    normalized_codes = _normalize_requested_codes(exchange_codes)
    exchanges = _resolve_exchanges(database_url, exchange_codes=normalized_codes)
    readiness_rows = list_readiness_read_models()

    latest_by_exchange_id: dict[int, object] = {}
    for row in readiness_rows:
        current = latest_by_exchange_id.get(row.exchange_id)
        if current is None or row.trading_date > current.trading_date:
            latest_by_exchange_id[row.exchange_id] = row

    if not latest_by_exchange_id:
        latest_by_exchange_id = _load_readiness_rows_from_database(
            database_url=database_url,
            exchange_ids=tuple(exchange.id for exchange in exchanges),
        )

    items: list[AppExchangeReadinessItem] = []
    for exchange in exchanges:
        row = latest_by_exchange_id.get(exchange.id)
        if row is None:
            continue
        items.append(
            AppExchangeReadinessItem(
                exchange=exchange.code,
                trading_date=row.trading_date.isoformat(),
                readiness_state=_map_readiness_state(row.publication_status),
                publication_status=row.publication_status,
                publication_available=row.is_ready,
            )
        )
    return items


def fetch_current_app_exchange_readiness(database_url: str, *, exchange_code: str) -> AppExchangeReadinessItem | None:
    items = fetch_app_exchange_readiness(database_url, exchange_codes=(exchange_code,))
    if not items:
        return None
    return items[0]


def _resolve_exchanges(database_url: str, *, exchange_codes: tuple[str, ...] | None) -> list[Exchange]:
    engine = create_engine(to_sqlalchemy_url(database_url))
    try:
        with Session(engine) as session:
            if exchange_codes:
                rows = list(session.scalars(select(Exchange).where(Exchange.code.in_(exchange_codes))))
                found_codes = {row.code for row in rows}
                missing = [code for code in exchange_codes if code not in found_codes]
                if missing:
                    raise ValueError(f"Unknown exchange code(s): {', '.join(missing)}")
                rows.sort(key=lambda row: row.code)
                return rows
            return list(session.scalars(select(Exchange).where(Exchange.is_launch_active.is_(True)).order_by(Exchange.code.asc())))
    finally:
        engine.dispose()


def _normalize_requested_codes(exchange_codes: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if exchange_codes is None:
        return None
    normalized: list[str] = []
    for code in exchange_codes:
        value = code.strip().upper()
        if not value:
            continue
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("At least one exchange code is required.")
    return tuple(normalized)


def _map_readiness_state(publication_status: str) -> str:
    if publication_status == "ready":
        return "ready"
    if publication_status == "market_closed":
        return "market_closed"
    return "not_ready"


def _load_readiness_rows_from_database(*, database_url: str, exchange_ids: tuple[int, ...]) -> dict[int, object]:
    if not exchange_ids:
        return {}
    engine = create_engine(to_sqlalchemy_url(database_url))
    try:
        with Session(engine) as session:
            rows: dict[int, object] = {}
            for exchange_id in exchange_ids:
                record = session.execute(
                    select(
                        ExchangeDayLoad.id,
                        ExchangeDayLoad.exchange_id,
                        ExchangeDayLoad.trading_date,
                        PublicationRecord.status,
                        PublicationRecord.status_updated_at,
                        PublicationRecord.published_at,
                    )
                    .join(
                        PublicationRecord,
                        PublicationRecord.exchange_day_load_id == ExchangeDayLoad.id,
                    )
                    .where(
                        ExchangeDayLoad.exchange_id == exchange_id,
                        ExchangeDayLoad.load_type == "daily_open",
                    )
                    .order_by(ExchangeDayLoad.trading_date.desc(), ExchangeDayLoad.id.desc())
                    .limit(1)
                ).first()
                if record is None:
                    continue
                rows[exchange_id] = type(
                    "_ReadinessRow",
                    (),
                    {
                        "exchange_day_load_id": int(record.id),
                        "exchange_id": int(record.exchange_id),
                        "trading_date": record.trading_date,
                        "publication_status": str(record.status),
                        "is_ready": str(record.status) == "ready",
                        "status_updated_at": record.status_updated_at,
                        "published_at": record.published_at,
                    },
                )()
            return rows
    finally:
        engine.dispose()
