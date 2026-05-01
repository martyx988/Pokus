from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, Exchange
from pokus_backend.domain.reference_models import Provider, ProviderExchangeReliabilityScore
from pokus_backend.pricing.reliability_scores import (
    ReliabilityOutcomeWindow,
    update_provider_exchange_reliability_score,
)
from pokus_backend.pricing.source_prioritization import SourcePrioritizationCandidate, select_source_candidate


class ReliabilityScoresTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.session.add_all(
            [
                Provider(code="ALPHA", name="Alpha", is_active=True),
                Provider(code="BETA", name="Beta", is_active=True),
                Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True),
                Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True),
            ]
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_persists_deterministic_score_update_for_provider_exchange_scope(self) -> None:
        first = update_provider_exchange_reliability_score(
            self.session,
            provider_code="ALPHA",
            exchange_code="NYSE",
            outcome=self._window(window_key="2026-05-01-open"),
        )
        self.session.commit()

        self.assertEqual(first.reliability_score, Decimal("0.9385"))
        self.assertEqual(first.observations_count, 1)
        self.assertEqual(
            self.session.query(ProviderExchangeReliabilityScore).count(),
            1,
        )

        second = update_provider_exchange_reliability_score(
            self.session,
            provider_code="ALPHA",
            exchange_code="NYSE",
            outcome=self._window(
                window_key="2026-05-01-close",
                benchmark_match_rate=Decimal("0.50"),
                missing_rate=Decimal("0.20"),
                timeliness_rate=Decimal("0.70"),
                stale_data_rate=Decimal("0.10"),
                provider_error_rate=Decimal("0.30"),
                disagreement_rate=Decimal("0.40"),
            ),
        )
        self.session.commit()

        self.assertEqual(second.reliability_score, Decimal("0.7993"))
        self.assertEqual(second.observations_count, 2)

    def test_repeated_same_window_key_is_stable(self) -> None:
        created = update_provider_exchange_reliability_score(
            self.session,
            provider_code="ALPHA",
            exchange_code="NYSE",
            outcome=self._window(window_key="2026-05-01-open"),
        )
        self.session.commit()
        repeated = update_provider_exchange_reliability_score(
            self.session,
            provider_code="ALPHA",
            exchange_code="NYSE",
            outcome=self._window(window_key="2026-05-01-open"),
        )
        self.session.commit()

        self.assertEqual(created.id, repeated.id)
        self.assertEqual(repeated.reliability_score, Decimal("0.9385"))
        self.assertEqual(repeated.observations_count, 1)

    def test_score_updates_are_scoped_per_provider_and_exchange(self) -> None:
        alpha_nyse = update_provider_exchange_reliability_score(
            self.session,
            provider_code="ALPHA",
            exchange_code="NYSE",
            outcome=self._window(window_key="w1"),
        )
        alpha_nasdaq = update_provider_exchange_reliability_score(
            self.session,
            provider_code="ALPHA",
            exchange_code="NASDAQ",
            outcome=self._window(window_key="w1", benchmark_match_rate=Decimal("0.30")),
        )
        beta_nyse = update_provider_exchange_reliability_score(
            self.session,
            provider_code="BETA",
            exchange_code="NYSE",
            outcome=self._window(window_key="w1", benchmark_match_rate=Decimal("0.99")),
        )
        self.session.commit()

        self.assertEqual(self.session.query(ProviderExchangeReliabilityScore).count(), 3)
        self.assertNotEqual(alpha_nyse.reliability_score, alpha_nasdaq.reliability_score)
        self.assertNotEqual(alpha_nyse.reliability_score, beta_nyse.reliability_score)

    def test_source_prioritization_can_consume_updated_score(self) -> None:
        alpha = update_provider_exchange_reliability_score(
            self.session,
            provider_code="ALPHA",
            exchange_code="NYSE",
            outcome=self._window(window_key="w-alpha", benchmark_match_rate=Decimal("0.95")),
        )
        beta = update_provider_exchange_reliability_score(
            self.session,
            provider_code="BETA",
            exchange_code="NYSE",
            outcome=self._window(window_key="w-beta", benchmark_match_rate=Decimal("0.40")),
        )
        self.session.commit()

        selected = select_source_candidate(
            [
                SourcePrioritizationCandidate(
                    candidate_key="alpha-candidate",
                    provider_code="ALPHA",
                    value=Decimal("100.00"),
                    reliability_score=Decimal(str(alpha.reliability_score)),
                    historical_availability_ratio=Decimal("0.50"),
                    exchange_coverage_quality=Decimal("0.50"),
                    fixed_source_order=2,
                ),
                SourcePrioritizationCandidate(
                    candidate_key="beta-candidate",
                    provider_code="BETA",
                    value=Decimal("100.00"),
                    reliability_score=Decimal(str(beta.reliability_score)),
                    historical_availability_ratio=Decimal("0.99"),
                    exchange_coverage_quality=Decimal("0.99"),
                    fixed_source_order=1,
                ),
            ]
        )

        self.assertEqual(selected.winner.candidate_key, "alpha-candidate")
        self.assertEqual(selected.evidence.winner_reason, "provider_exchange_reliability_score")

    def _window(
        self,
        *,
        window_key: str,
        benchmark_match_rate: Decimal = Decimal("0.90"),
        missing_rate: Decimal = Decimal("0.05"),
        timeliness_rate: Decimal = Decimal("0.95"),
        stale_data_rate: Decimal = Decimal("0.02"),
        provider_error_rate: Decimal = Decimal("0.03"),
        disagreement_rate: Decimal = Decimal("0.04"),
    ) -> ReliabilityOutcomeWindow:
        return ReliabilityOutcomeWindow(
            window_key=window_key,
            benchmark_match_rate=benchmark_match_rate,
            missing_rate=missing_rate,
            timeliness_rate=timeliness_rate,
            stale_data_rate=stale_data_rate,
            provider_error_rate=provider_error_rate,
            disagreement_rate=disagreement_rate,
            observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
