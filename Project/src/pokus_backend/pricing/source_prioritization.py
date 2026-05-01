from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class SourcePrioritizationCandidate:
    candidate_key: str
    provider_code: str
    value: Decimal
    reliability_score: Decimal
    historical_availability_ratio: Decimal
    exchange_coverage_quality: Decimal
    fixed_source_order: int


@dataclass(frozen=True, slots=True)
class SourceCandidateEvidence:
    candidate_key: str
    provider_code: str
    reliability_score: Decimal
    historical_availability_ratio: Decimal
    exchange_coverage_quality: Decimal
    fixed_source_order: int


@dataclass(frozen=True, slots=True)
class SourceSelectionEvidence:
    policy_order: tuple[str, str, str, str]
    winner_reason: str
    winner_candidate_key: str
    ranked_candidates: tuple[SourceCandidateEvidence, ...]


@dataclass(frozen=True, slots=True)
class SourceSelectionResult:
    winner: SourcePrioritizationCandidate
    evidence: SourceSelectionEvidence


def select_source_candidate(candidates: Sequence[SourcePrioritizationCandidate]) -> SourceSelectionResult:
    if not candidates:
        raise ValueError("candidates must contain at least one candidate")

    ranked_candidates = sorted(candidates, key=_ranking_key)
    winner = ranked_candidates[0]
    runner_up = ranked_candidates[1] if len(ranked_candidates) > 1 else None

    winner_reason = _winner_reason(winner=winner, runner_up=runner_up)
    evidence = SourceSelectionEvidence(
        policy_order=(
            "provider_exchange_reliability_score",
            "historical_availability_ratio",
            "exchange_coverage_quality",
            "fixed_source_order",
        ),
        winner_reason=winner_reason,
        winner_candidate_key=winner.candidate_key,
        ranked_candidates=tuple(
            SourceCandidateEvidence(
                candidate_key=candidate.candidate_key,
                provider_code=candidate.provider_code,
                reliability_score=candidate.reliability_score,
                historical_availability_ratio=candidate.historical_availability_ratio,
                exchange_coverage_quality=candidate.exchange_coverage_quality,
                fixed_source_order=candidate.fixed_source_order,
            )
            for candidate in ranked_candidates
        ),
    )
    return SourceSelectionResult(winner=winner, evidence=evidence)


def _ranking_key(candidate: SourcePrioritizationCandidate) -> tuple[Decimal, Decimal, Decimal, int, str]:
    return (
        -candidate.reliability_score,
        -candidate.historical_availability_ratio,
        -candidate.exchange_coverage_quality,
        candidate.fixed_source_order,
        candidate.candidate_key,
    )


def _winner_reason(
    *, winner: SourcePrioritizationCandidate, runner_up: SourcePrioritizationCandidate | None
) -> str:
    if runner_up is None:
        return "single_candidate"
    if winner.reliability_score != runner_up.reliability_score:
        return "provider_exchange_reliability_score"
    if winner.historical_availability_ratio != runner_up.historical_availability_ratio:
        return "historical_availability_ratio"
    if winner.exchange_coverage_quality != runner_up.exchange_coverage_quality:
        return "exchange_coverage_quality"
    if winner.fixed_source_order != runner_up.fixed_source_order:
        return "fixed_source_order"
    return "deterministic_candidate_key_tiebreak"
