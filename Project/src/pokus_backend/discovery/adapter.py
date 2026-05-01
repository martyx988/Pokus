from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from pokus_backend.discovery.contract import DiscoveryCandidate, candidate_from_payload


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    exchange: str
    instrument_types: tuple[str, ...]


class DiscoveryAdapter(Protocol):
    def discover(self, request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]:
        ...


def normalize_discovery_payloads(payloads: Sequence[Mapping[str, Any]]) -> list[DiscoveryCandidate]:
    return [candidate_from_payload(payload) for payload in payloads]
