"""Discovery adapter boundaries and normalized candidate contracts."""

from pokus_backend.discovery.adapter import (
    DiscoveryAdapter,
    DiscoveryRequest,
    normalize_discovery_payloads,
)
from pokus_backend.discovery.contract import DiscoveryCandidate, candidate_from_payload
from pokus_backend.discovery.persistence import (
    PersistDiscoveryCandidatesResult,
    persist_discovery_candidates,
)

__all__ = [
    "DiscoveryAdapter",
    "DiscoveryCandidate",
    "DiscoveryRequest",
    "PersistDiscoveryCandidatesResult",
    "candidate_from_payload",
    "normalize_discovery_payloads",
    "persist_discovery_candidates",
]
