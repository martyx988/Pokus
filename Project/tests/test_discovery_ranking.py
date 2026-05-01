from __future__ import annotations

import unittest
from decimal import Decimal

from pokus_backend.discovery.ranking import ListingRankingCandidate, select_best_listing


class ListingRankingServiceTests(unittest.TestCase):
    def test_home_exchange_precedence_wins_over_higher_turnover(self) -> None:
        result = select_best_listing(
            [
                ListingRankingCandidate(
                    listing_id=100,
                    is_home_exchange=False,
                    turnover=Decimal("1000000"),
                    exchange_activity_priority=1,
                ),
                ListingRankingCandidate(
                    listing_id=200,
                    is_home_exchange=True,
                    turnover=Decimal("10"),
                    exchange_activity_priority=999,
                ),
            ]
        )

        self.assertEqual(result.selected_listing_id, 200)
        self.assertTrue(result.selected_evidence.is_home_exchange)

    def test_turnover_precedence_applies_after_home_exchange_tie(self) -> None:
        result = select_best_listing(
            [
                ListingRankingCandidate(
                    listing_id=10,
                    is_home_exchange=False,
                    turnover=Decimal("1500.50"),
                    exchange_activity_priority=99,
                ),
                ListingRankingCandidate(
                    listing_id=11,
                    is_home_exchange=False,
                    turnover=Decimal("2500.75"),
                    exchange_activity_priority=100,
                ),
            ]
        )

        self.assertEqual(result.selected_listing_id, 11)
        self.assertEqual(result.selected_evidence.turnover, Decimal("2500.75"))

    def test_exchange_activity_priority_breaks_remaining_tie(self) -> None:
        result = select_best_listing(
            [
                ListingRankingCandidate(
                    listing_id=1,
                    is_home_exchange=False,
                    turnover=Decimal("100"),
                    exchange_activity_priority=3,
                ),
                ListingRankingCandidate(
                    listing_id=2,
                    is_home_exchange=False,
                    turnover=Decimal("100"),
                    exchange_activity_priority=2,
                ),
            ]
        )

        self.assertEqual(result.selected_listing_id, 2)
        self.assertEqual(result.selected_evidence.exchange_activity_priority, 2)

    def test_full_tie_is_deterministic_by_listing_id(self) -> None:
        result = select_best_listing(
            [
                ListingRankingCandidate(
                    listing_id=8,
                    is_home_exchange=False,
                    turnover=Decimal("100"),
                    exchange_activity_priority=2,
                ),
                ListingRankingCandidate(
                    listing_id=3,
                    is_home_exchange=False,
                    turnover=Decimal("100"),
                    exchange_activity_priority=2,
                ),
            ]
        )

        self.assertEqual(result.selected_listing_id, 3)

    def test_rejects_empty_candidate_set(self) -> None:
        with self.assertRaises(ValueError):
            select_best_listing([])


if __name__ == "__main__":
    unittest.main()
