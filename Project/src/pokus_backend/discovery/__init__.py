"""Discovery adapter boundaries and normalized candidate contracts."""

from pokus_backend.discovery.adapter import (
    DiscoveryAdapter,
    DiscoveryRequest,
    normalize_discovery_payloads,
)
from pokus_backend.discovery.contract import DiscoveryCandidate, candidate_from_payload

__all__ = [
    "DiscoveryAdapter",
    "DiscoveryCandidate",
    "DiscoveryRequest",
    "candidate_from_payload",
    "normalize_discovery_payloads",
]
