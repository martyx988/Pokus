from __future__ import annotations

import unittest
from decimal import Decimal

from pokus_backend.pricing.source_prioritization import (
    SourcePrioritizationCandidate,
    select_source_candidate,
)


class SourcePrioritizationTests(unittest.TestCase):
    def test_selects_by_reliability_score_first(self) -> None:
        winner = select_source_candidate(
            [
                self._candidate("b", "BETA", "0.88", "0.95", "0.90", 2),
                self._candidate("a", "ALPHA", "0.91", "0.10", "0.10", 99),
            ]
        )

        self.assertEqual(winner.winner.candidate_key, "a")
        self.assertEqual(winner.evidence.winner_reason, "provider_exchange_reliability_score")

    def test_selects_by_historical_availability_when_reliability_tied(self) -> None:
        winner = select_source_candidate(
            [
                self._candidate("a", "ALPHA", "0.91", "0.70", "0.95", 1),
                self._candidate("b", "BETA", "0.91", "0.85", "0.10", 99),
            ]
        )

        self.assertEqual(winner.winner.candidate_key, "b")
        self.assertEqual(winner.evidence.winner_reason, "historical_availability_ratio")

    def test_selects_by_exchange_coverage_quality_when_first_two_tied(self) -> None:
        winner = select_source_candidate(
            [
                self._candidate("a", "ALPHA", "0.91", "0.80", "0.90", 5),
                self._candidate("b", "BETA", "0.91", "0.80", "0.92", 99),
            ]
        )

        self.assertEqual(winner.winner.candidate_key, "b")
        self.assertEqual(winner.evidence.winner_reason, "exchange_coverage_quality")

    def test_resolves_tie_by_fixed_source_order(self) -> None:
        winner = select_source_candidate(
            [
                self._candidate("a", "ALPHA", "0.91", "0.80", "0.92", 3),
                self._candidate("b", "BETA", "0.91", "0.80", "0.92", 1),
            ]
        )

        self.assertEqual(winner.winner.candidate_key, "b")
        self.assertEqual(winner.evidence.winner_reason, "fixed_source_order")

    def test_evidence_contains_policy_order_and_ranked_inputs(self) -> None:
        winner = select_source_candidate(
            [
                self._candidate("z", "ZETA", "0.60", "0.10", "0.10", 9),
                self._candidate("a", "ALPHA", "0.95", "0.95", "0.95", 1),
            ]
        )

        self.assertEqual(
            winner.evidence.policy_order,
            (
                "provider_exchange_reliability_score",
                "historical_availability_ratio",
                "exchange_coverage_quality",
                "fixed_source_order",
            ),
        )
        self.assertEqual(winner.evidence.winner_candidate_key, "a")
        self.assertEqual([row.candidate_key for row in winner.evidence.ranked_candidates], ["a", "z"])

    def test_deterministic_when_all_policy_inputs_tie(self) -> None:
        winner = select_source_candidate(
            [
                self._candidate("zz", "ALPHA", "0.90", "0.80", "0.70", 1),
                self._candidate("aa", "BETA", "0.90", "0.80", "0.70", 1),
            ]
        )

        self.assertEqual(winner.winner.candidate_key, "aa")
        self.assertEqual(winner.evidence.winner_reason, "deterministic_candidate_key_tiebreak")

    def test_rejects_empty_candidate_set(self) -> None:
        with self.assertRaises(ValueError):
            select_source_candidate([])

    def _candidate(
        self,
        candidate_key: str,
        provider_code: str,
        reliability_score: str,
        historical_availability_ratio: str,
        exchange_coverage_quality: str,
        fixed_source_order: int,
    ) -> SourcePrioritizationCandidate:
        return SourcePrioritizationCandidate(
            candidate_key=candidate_key,
            provider_code=provider_code,
            value=Decimal("100.00"),
            reliability_score=Decimal(reliability_score),
            historical_availability_ratio=Decimal(historical_availability_ratio),
            exchange_coverage_quality=Decimal(exchange_coverage_quality),
            fixed_source_order=fixed_source_order,
        )


if __name__ == "__main__":
    unittest.main()
