from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    exchange: str
    instrument_type: str
    symbol: str
    name: str
    stable_identifiers: Mapping[str, str]


def candidate_from_payload(payload: Mapping[str, Any]) -> DiscoveryCandidate:
    exchange = _required_text(payload=payload, field_name="exchange", normalize_upper=True)
    instrument_type = _required_text(
        payload=payload,
        field_name="instrument_type",
        normalize_upper=True,
    )
    symbol = _required_text(payload=payload, field_name="symbol", normalize_upper=True)
    name = _required_text(payload=payload, field_name="name", normalize_upper=False)
    stable_identifiers = _optional_identifier_map(payload.get("stable_identifiers"))

    return DiscoveryCandidate(
        exchange=exchange,
        instrument_type=instrument_type,
        symbol=symbol,
        name=name,
        stable_identifiers=stable_identifiers,
    )


def _required_text(payload: Mapping[str, Any], field_name: str, normalize_upper: bool) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")

    normalized = value.strip()
    if normalize_upper:
        normalized = normalized.upper()
    return normalized


def _optional_identifier_map(raw_identifiers: Any) -> dict[str, str]:
    if raw_identifiers is None:
        return {}
    if not isinstance(raw_identifiers, Mapping):
        raise ValueError("stable_identifiers must be a mapping of non-empty string keys and values")

    normalized_identifiers: dict[str, str] = {}
    for key, value in raw_identifiers.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("stable_identifiers keys must be non-empty strings")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("stable_identifiers values must be non-empty strings")

        normalized_identifiers[key.strip().lower()] = value.strip()

    return normalized_identifiers
