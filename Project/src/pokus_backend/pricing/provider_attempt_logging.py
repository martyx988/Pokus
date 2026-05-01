from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.reference_models import Exchange, Provider, ProviderAttempt

ResultStatus = Literal["success", "timeout", "error", "rate_limited"]


@dataclass(frozen=True, slots=True)
class ProviderAttemptLogInput:
    attempt_key: str
    provider_code: str
    exchange_code: str
    request_purpose: str
    load_type: str
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    latency_ms: int | None
    result_status: ResultStatus
    error_code: str | None = None
    error_detail: str | None = None
    rate_limit_hit: bool = False
    stale_data: bool = False
    missing_values: bool = False
    normalized_metadata: dict[str, object] | None = None


def log_provider_attempt(session: Session, payload: ProviderAttemptLogInput) -> ProviderAttempt:
    attempt_key = payload.attempt_key.strip()
    if not attempt_key:
        raise ValueError("attempt_key must be a non-empty string")

    existing = session.scalar(select(ProviderAttempt).where(ProviderAttempt.attempt_key == attempt_key))
    provider = _get_provider_by_code(session=session, provider_code=payload.provider_code)
    exchange = _get_exchange_by_code(session=session, exchange_code=payload.exchange_code)
    if existing is None:
        attempt = ProviderAttempt(
            attempt_key=attempt_key,
            provider_id=provider.id,
            exchange_id=exchange.id,
            request_purpose=payload.request_purpose,
            load_type=payload.load_type,
            requested_at=payload.requested_at,
            started_at=payload.started_at,
            completed_at=payload.completed_at,
            latency_ms=payload.latency_ms,
            result_status=payload.result_status,
            error_code=payload.error_code,
            error_detail=payload.error_detail,
            rate_limit_hit=payload.rate_limit_hit,
            stale_data=payload.stale_data,
            missing_values=payload.missing_values,
            normalized_metadata=payload.normalized_metadata,
        )
        session.add(attempt)
        session.flush()
        return attempt

    existing.provider_id = provider.id
    existing.exchange_id = exchange.id
    existing.request_purpose = payload.request_purpose
    existing.load_type = payload.load_type
    existing.requested_at = payload.requested_at
    existing.started_at = payload.started_at
    existing.completed_at = payload.completed_at
    existing.latency_ms = payload.latency_ms
    existing.result_status = payload.result_status
    existing.error_code = payload.error_code
    existing.error_detail = payload.error_detail
    existing.rate_limit_hit = payload.rate_limit_hit
    existing.stale_data = payload.stale_data
    existing.missing_values = payload.missing_values
    existing.normalized_metadata = payload.normalized_metadata
    session.flush()
    return existing


def get_provider_attempt_by_key(session: Session, attempt_key: str) -> ProviderAttempt | None:
    normalized_attempt_key = attempt_key.strip()
    if not normalized_attempt_key:
        raise ValueError("attempt_key must be a non-empty string")
    return session.scalar(select(ProviderAttempt).where(ProviderAttempt.attempt_key == normalized_attempt_key))


def _get_provider_by_code(*, session: Session, provider_code: str) -> Provider:
    normalized_provider_code = provider_code.strip().upper()
    if not normalized_provider_code:
        raise ValueError("provider_code must be a non-empty string")
    provider = session.scalar(select(Provider).where(Provider.code == normalized_provider_code))
    if provider is None:
        raise ValueError(f"unknown provider code: {normalized_provider_code}")
    return provider


def _get_exchange_by_code(*, session: Session, exchange_code: str) -> Exchange:
    normalized_exchange_code = exchange_code.strip().upper()
    if not normalized_exchange_code:
        raise ValueError("exchange_code must be a non-empty string")
    exchange = session.scalar(select(Exchange).where(Exchange.code == normalized_exchange_code))
    if exchange is None:
        raise ValueError(f"unknown exchange code: {normalized_exchange_code}")
    return exchange
