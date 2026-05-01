from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class ListingRankingCandidate:
    listing_id: int
    is_home_exchange: bool
    turnover: Decimal
    exchange_activity_priority: int


@dataclass(frozen=True, slots=True)
class ListingSelectionEvidence:
    listing_id: int
    is_home_exchange: bool
    turnover: Decimal
    exchange_activity_priority: int


@dataclass(frozen=True, slots=True)
class ListingSelectionResult:
    selected_listing_id: int
    selected_evidence: ListingSelectionEvidence


def select_best_listing(candidates: Sequence[ListingRankingCandidate]) -> ListingSelectionResult:
    if not candidates:
        raise ValueError("candidates must contain at least one listing")

    ranked_candidates = sorted(candidates, key=_ranking_key)
    selected = ranked_candidates[0]
    return ListingSelectionResult(
        selected_listing_id=selected.listing_id,
        selected_evidence=ListingSelectionEvidence(
            listing_id=selected.listing_id,
            is_home_exchange=selected.is_home_exchange,
            turnover=selected.turnover,
            exchange_activity_priority=selected.exchange_activity_priority,
        ),
    )


def _ranking_key(candidate: ListingRankingCandidate) -> tuple[int, Decimal, int, int]:
    return (
        0 if candidate.is_home_exchange else 1,
        -candidate.turnover,
        candidate.exchange_activity_priority,
        candidate.listing_id,
    )
