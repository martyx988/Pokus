from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.reference_models import (
    Exchange,
    Provider,
    ProviderExchangeReliabilityScore,
)


@dataclass(frozen=True, slots=True)
class ReliabilityOutcomeWindow:
    window_key: str
    benchmark_match_rate: Decimal
    missing_rate: Decimal
    timeliness_rate: Decimal
    stale_data_rate: Decimal
    provider_error_rate: Decimal
    disagreement_rate: Decimal
    observed_at: datetime


def update_provider_exchange_reliability_score(
    session: Session,
    *,
    provider_code: str,
    exchange_code: str,
    outcome: ReliabilityOutcomeWindow,
) -> ProviderExchangeReliabilityScore:
    provider = _get_provider_by_code(session=session, provider_code=provider_code)
    exchange = _get_exchange_by_code(session=session, exchange_code=exchange_code)
    existing = session.scalar(
        select(ProviderExchangeReliabilityScore).where(
            ProviderExchangeReliabilityScore.provider_id == provider.id,
            ProviderExchangeReliabilityScore.exchange_id == exchange.id,
        )
    )
    normalized_window_key = outcome.window_key.strip()
    if not normalized_window_key:
        raise ValueError("window_key must be a non-empty string")

    window_score = _calculate_window_score(outcome)
    if existing is None:
        existing = ProviderExchangeReliabilityScore(
            provider_id=provider.id,
            exchange_id=exchange.id,
            reliability_score=window_score,
            observations_count=1,
            last_window_key=normalized_window_key,
            updated_at=outcome.observed_at.astimezone(timezone.utc),
        )
        session.add(existing)
        session.flush()
        return existing

    if existing.last_window_key == normalized_window_key:
        existing.updated_at = outcome.observed_at.astimezone(timezone.utc)
        session.flush()
        return existing

    previous_score = Decimal(str(existing.reliability_score))
    observation_count = existing.observations_count + 1
    updated_score = _quantize_score(
        ((previous_score * Decimal(existing.observations_count)) + window_score) / Decimal(observation_count)
    )
    existing.reliability_score = updated_score
    existing.observations_count = observation_count
    existing.last_window_key = normalized_window_key
    existing.updated_at = outcome.observed_at.astimezone(timezone.utc)
    session.flush()
    return existing


def _calculate_window_score(outcome: ReliabilityOutcomeWindow) -> Decimal:
    benchmark_match_rate = _validate_rate("benchmark_match_rate", outcome.benchmark_match_rate)
    missing_rate = _validate_rate("missing_rate", outcome.missing_rate)
    timeliness_rate = _validate_rate("timeliness_rate", outcome.timeliness_rate)
    stale_data_rate = _validate_rate("stale_data_rate", outcome.stale_data_rate)
    provider_error_rate = _validate_rate("provider_error_rate", outcome.provider_error_rate)
    disagreement_rate = _validate_rate("disagreement_rate", outcome.disagreement_rate)

    score = (
        Decimal("0.35") * benchmark_match_rate
        + Decimal("0.20") * (Decimal("1") - missing_rate)
        + Decimal("0.15") * timeliness_rate
        + Decimal("0.10") * (Decimal("1") - stale_data_rate)
        + Decimal("0.10") * (Decimal("1") - provider_error_rate)
        + Decimal("0.10") * (Decimal("1") - disagreement_rate)
    )
    return _quantize_score(score)


def _validate_rate(name: str, value: Decimal) -> Decimal:
    if value < Decimal("0") or value > Decimal("1"):
        raise ValueError(f"{name} must be in [0, 1]")
    return value


def _quantize_score(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


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
