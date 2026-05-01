from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Mapping

PriceType = Literal["historical_adjusted_close", "current_day_unadjusted_open"]
_ALLOWED_PRICE_TYPES: tuple[str, ...] = ("historical_adjusted_close", "current_day_unadjusted_open")


@dataclass(frozen=True, slots=True)
class PriceCandidate:
    instrument_id: str
    listing_id: str
    exchange: str
    trading_day: date
    price_type: PriceType
    value: Decimal
    currency: str
    provider_code: str
    provider_observed_at: datetime | None
    provider_request_id: str | None
    provider_metadata: Mapping[str, str]


def candidate_from_payload(payload: Mapping[str, Any]) -> PriceCandidate:
    instrument_id = _required_text(payload=payload, field_name="instrument_id", normalize_upper=False)
    listing_id = _required_text(payload=payload, field_name="listing_id", normalize_upper=False)
    exchange = _required_text(payload=payload, field_name="exchange", normalize_upper=True)
    trading_day = _required_date(payload=payload, field_name="trading_day")
    price_type = _required_price_type(payload=payload, field_name="price_type")
    value = _required_decimal(payload=payload, field_name="value")
    currency = _required_text(payload=payload, field_name="currency", normalize_upper=True)
    provider_code = _required_text(payload=payload, field_name="provider_code", normalize_upper=False)
    provider_observed_at = _optional_datetime(payload.get("provider_observed_at"), "provider_observed_at")
    provider_request_id = _optional_text(payload.get("provider_request_id"), "provider_request_id")
    provider_metadata = _optional_metadata_map(payload.get("provider_metadata"))

    return PriceCandidate(
        instrument_id=instrument_id,
        listing_id=listing_id,
        exchange=exchange,
        trading_day=trading_day,
        price_type=price_type,
        value=value,
        currency=currency,
        provider_code=provider_code,
        provider_observed_at=provider_observed_at,
        provider_request_id=provider_request_id,
        provider_metadata=provider_metadata,
    )


def _required_text(payload: Mapping[str, Any], field_name: str, normalize_upper: bool) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")

    normalized = value.strip()
    if normalize_upper:
        normalized = normalized.upper()
    return normalized


def _optional_text(raw: Any, field_name: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field_name} must be a non-empty string when provided")
    return raw.strip()


def _required_date(payload: Mapping[str, Any], field_name: str) -> date:
    raw = payload.get(field_name)
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field_name} must be an ISO date string")

    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date string") from exc


def _required_price_type(payload: Mapping[str, Any], field_name: str) -> PriceType:
    raw = payload.get(field_name)
    if raw not in _ALLOWED_PRICE_TYPES:
        raise ValueError(f"{field_name} must be one of {_ALLOWED_PRICE_TYPES}")
    return raw


def _required_decimal(payload: Mapping[str, Any], field_name: str) -> Decimal:
    raw = payload.get(field_name)
    if isinstance(raw, bool) or raw is None:
        raise ValueError(f"{field_name} must be a decimal-compatible value")

    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a decimal-compatible value") from exc

    if value <= Decimal("0"):
        raise ValueError(f"{field_name} must be greater than zero")
    return value


def _optional_datetime(raw: Any, field_name: str) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field_name} must be an ISO datetime string when provided")

    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime string when provided") from exc


def _optional_metadata_map(raw_metadata: Any) -> dict[str, str]:
    if raw_metadata is None:
        return {}
    if not isinstance(raw_metadata, Mapping):
        raise ValueError("provider_metadata must be a mapping of non-empty string keys and values")

    normalized: dict[str, str] = {}
    for key, value in raw_metadata.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("provider_metadata keys must be non-empty strings")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("provider_metadata values must be non-empty strings")

        normalized[key.strip().lower()] = value.strip()

    return normalized
