from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Protocol, Sequence

from pokus_backend.pricing.contract import PriceCandidate, candidate_from_payload


@dataclass(frozen=True, slots=True)
class PriceCandidateRequest:
    instrument_id: str
    listing_id: str
    exchange: str
    symbol: str
    trading_day: date


class ProviderPriceAdapter(Protocol):
    def fetch_historical_close_candidates(self, request: PriceCandidateRequest) -> Sequence[PriceCandidate]:
        ...

    def fetch_current_day_open_candidates(self, request: PriceCandidateRequest) -> Sequence[PriceCandidate]:
        ...


def normalize_price_candidate_payloads(payloads: Sequence[Mapping[str, Any]]) -> list[PriceCandidate]:
    return [candidate_from_payload(payload) for payload in payloads]
