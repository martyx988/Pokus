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
from pokus_backend.discovery.ranking import (
    ListingRankingCandidate,
    ListingSelectionEvidence,
    ListingSelectionResult,
    select_best_listing,
)

__all__ = [
    "DiscoveryAdapter",
    "DiscoveryCandidate",
    "DiscoveryRequest",
    "ListingRankingCandidate",
    "ListingSelectionEvidence",
    "ListingSelectionResult",
    "PersistDiscoveryCandidatesResult",
    "candidate_from_payload",
    "normalize_discovery_payloads",
    "persist_discovery_candidates",
    "select_best_listing",
]
