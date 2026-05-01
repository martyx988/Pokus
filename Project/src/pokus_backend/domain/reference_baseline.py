from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.domain.reference_models import Exchange, InstrumentType

LAUNCH_EXCHANGES: tuple[tuple[str, str], ...] = (
    ("NYSE", "New York Stock Exchange"),
    ("NASDAQ", "Nasdaq"),
    ("PSE", "Prague Stock Exchange"),
)

LAUNCH_INSTRUMENT_TYPES: tuple[tuple[str, str], ...] = (
    ("STOCK", "Stocks"),
    ("ETF", "ETF"),
    ("ETN", "ETN"),
)


def seed_launch_baseline_records(database_url: str) -> None:
    engine = create_engine(_to_sqlalchemy_url(database_url))
    session = Session(engine)
    try:
        _upsert_exchanges(session)
        _upsert_instrument_types(session)
        session.commit()
    finally:
        session.close()
        engine.dispose()


def _to_sqlalchemy_url(database_url: str) -> str:
    parts = urlsplit(database_url)
    if "+" in parts.scheme:
        return database_url
    if parts.scheme == "postgresql":
        return urlunsplit(("postgresql+psycopg", parts.netloc, parts.path, parts.query, parts.fragment))
    return database_url


def _upsert_exchanges(session: Session) -> None:
    existing = {
        row.code: row
        for row in session.scalars(
            select(Exchange).where(Exchange.code.in_([code for code, _ in LAUNCH_EXCHANGES]))
        )
    }
    for code, name in LAUNCH_EXCHANGES:
        row = existing.get(code)
        if row is None:
            session.add(Exchange(code=code, name=name, is_launch_active=True))
            continue
        row.name = name
        row.is_launch_active = True


def _upsert_instrument_types(session: Session) -> None:
    existing = {
        row.code: row
        for row in session.scalars(
            select(InstrumentType).where(
                InstrumentType.code.in_([code for code, _ in LAUNCH_INSTRUMENT_TYPES])
            )
        )
    }
    for code, name in LAUNCH_INSTRUMENT_TYPES:
        row = existing.get(code)
        if row is None:
            session.add(InstrumentType(code=code, name=name, is_launch_active=True))
            continue
        row.name = name
        row.is_launch_active = True
