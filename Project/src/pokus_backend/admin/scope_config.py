from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.db import to_sqlalchemy_url
from pokus_backend.domain.reference_models import Exchange, InstrumentType


@dataclass(frozen=True)
class ScopeUpdateResult:
    supported_exchanges: tuple[str, ...]
    supported_instrument_types: tuple[str, ...]


def get_supported_scope(database_url: str) -> ScopeUpdateResult:
    with _session(database_url) as session:
        exchange_codes = tuple(
            session.scalars(select(Exchange.code).where(Exchange.is_launch_active.is_(True)).order_by(Exchange.code.asc()))
        )
        type_codes = tuple(
            session.scalars(
                select(InstrumentType.code)
                .where(InstrumentType.is_launch_active.is_(True))
                .order_by(InstrumentType.code.asc())
            )
        )
    return ScopeUpdateResult(supported_exchanges=exchange_codes, supported_instrument_types=type_codes)


def set_supported_exchanges(database_url: str, exchange_codes: list[str]) -> ScopeUpdateResult:
    normalized = _normalize_codes(exchange_codes, field_name="exchange_codes")
    with _session(database_url) as session:
        rows = session.scalars(select(Exchange).order_by(Exchange.code.asc())).all()
        _validate_supported_codes(
            requested_codes=normalized,
            allowed_codes={row.code for row in rows},
            code_type="exchange",
        )
        requested = set(normalized)
        for row in rows:
            row.is_launch_active = row.code in requested
        session.commit()
    return get_supported_scope(database_url)


def set_supported_instrument_types(database_url: str, instrument_type_codes: list[str]) -> ScopeUpdateResult:
    normalized = _normalize_codes(instrument_type_codes, field_name="instrument_type_codes")
    with _session(database_url) as session:
        rows = session.scalars(select(InstrumentType).order_by(InstrumentType.code.asc())).all()
        _validate_supported_codes(
            requested_codes=normalized,
            allowed_codes={row.code for row in rows},
            code_type="instrument_type",
        )
        requested = set(normalized)
        for row in rows:
            row.is_launch_active = row.code in requested
        session.commit()
    return get_supported_scope(database_url)


def _normalize_codes(codes: list[str], field_name: str) -> list[str]:
    if not isinstance(codes, list):
        raise ValueError(f"{field_name} must be a list of strings.")
    normalized = []
    for code in codes:
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"{field_name} must only contain non-empty strings.")
        normalized.append(code.strip().upper())
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicate values.")
    return normalized


def _validate_supported_codes(requested_codes: list[str], allowed_codes: set[str], code_type: str) -> None:
    unsupported = sorted(set(requested_codes) - allowed_codes)
    if unsupported:
        raise ValueError(f"Unsupported {code_type} code(s): {', '.join(unsupported)}")


@contextmanager
def _session(database_url: str):
    engine = create_engine(to_sqlalchemy_url(database_url))
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
