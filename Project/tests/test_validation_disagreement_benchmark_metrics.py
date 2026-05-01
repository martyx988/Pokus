from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, CandidatePriceValue, Exchange, Instrument, InstrumentType, Listing
from pokus_backend.domain.reference_models import Provider, ProviderAttempt, ValidationExchangeReport, ValidationRun
from pokus_backend.validation.run_orchestrator import orchestrate_launch_exchange_validation_run


class ValidationDisagreementBenchmarkMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.provider_a = Provider(code="ALPHA", name="Alpha", is_active=True)
        self.provider_b = Provider(code="BETA", name="Beta", is_active=True)
        self.session.add_all([self.exchange, self.instrument_type, self.provider_a, self.provider_b])
        self.session.flush()
        self.attempt_a = self._create_attempt(provider_id=self.provider_a.id, attempt_key="attempt-a")
        self.attempt_b = self._create_attempt(provider_id=self.provider_b.id, attempt_key="attempt-b")
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_populates_passing_disagreement_benchmark_metrics(self) -> None:
        listing = self._create_listing("AAA")
        for idx in range(1, 21):
            self._add_candidate(
                listing_id=listing.id,
                provider_id=self.provider_a.id,
                provider_attempt_id=self.attempt_a.id,
                candidate_key=f"pass-{idx}-a",
                value=Decimal("100"),
                benchmark=Decimal("100"),
            )
            self._add_candidate(
                listing_id=listing.id,
                provider_id=self.provider_b.id,
                provider_attempt_id=self.attempt_b.id,
                candidate_key=f"pass-{idx}-b",
                value=Decimal("100"),
                benchmark=Decimal("100"),
            )
        self.session.commit()

        orchestrate_launch_exchange_validation_run(self.session, target_exchange_codes=["NYSE"], run_key="db-pass")
        self.session.commit()

        report = self._report_for_run("db-pass")
        bucket = report.result_buckets["disagreement_benchmark"]
        self.assertEqual(bucket["status"], "pass")
        self.assertEqual(bucket["evidence"]["disagreement_frequency"]["disagreement_count"], 0)
        self.assertEqual(bucket["evidence"]["disagreement_frequency"]["disagreement_rate"], 0.0)
        self.assertEqual(bucket["evidence"]["benchmark_match"]["mismatch_count"], 0)
        self.assertEqual(bucket["evidence"]["benchmark_match"]["mismatch_percent"], 0.0)
        self.assertTrue(bucket["evidence"]["benchmark_match"]["pass"])

    def test_populates_failing_benchmark_threshold_and_evidence_refs(self) -> None:
        listing = self._create_listing("BBB")
        for idx in range(1, 11):
            if idx == 1:
                alpha_value = Decimal("99")
                beta_value = Decimal("98")
            else:
                alpha_value = Decimal("100")
                beta_value = Decimal("100")
            self._add_candidate(
                listing_id=listing.id,
                provider_id=self.provider_a.id,
                provider_attempt_id=self.attempt_a.id,
                candidate_key=f"fail-{idx}-a",
                value=alpha_value,
                benchmark=Decimal("100"),
            )
            self._add_candidate(
                listing_id=listing.id,
                provider_id=self.provider_b.id,
                provider_attempt_id=self.attempt_b.id,
                candidate_key=f"fail-{idx}-b",
                value=beta_value,
                benchmark=Decimal("100"),
            )
        self.session.commit()

        orchestrate_launch_exchange_validation_run(self.session, target_exchange_codes=["NYSE"], run_key="db-fail")
        self.session.commit()

        report = self._report_for_run("db-fail")
        bucket = report.result_buckets["disagreement_benchmark"]
        self.assertEqual(bucket["status"], "fail")
        self.assertIn("provider_disagreement_detected", bucket["findings"])
        self.assertIn("benchmark_mismatch_threshold_not_met", bucket["findings"])
        self.assertEqual(bucket["evidence"]["benchmark_match"]["compared_benchmark_count"], 10)
        self.assertEqual(bucket["evidence"]["benchmark_match"]["mismatch_count"], 1)
        self.assertEqual(bucket["evidence"]["benchmark_match"]["mismatch_percent"], 10.0)
        self.assertFalse(bucket["evidence"]["benchmark_match"]["pass"])
        self.assertEqual(len(bucket["evidence"]["benchmark_match"]["mismatch_evidence_refs"]), 1)

    def _create_listing(self, symbol: str) -> Listing:
        instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name=f"Instrument {symbol}")
        self.session.add(instrument)
        self.session.flush()
        listing = Listing(instrument_id=instrument.id, exchange_id=self.exchange.id, symbol=symbol)
        self.session.add(listing)
        self.session.flush()
        return listing

    def _add_candidate(
        self,
        *,
        listing_id: int,
        provider_id: int,
        provider_attempt_id: int,
        candidate_key: str,
        value: Decimal,
        benchmark: Decimal,
    ) -> None:
        self.session.add(
            CandidatePriceValue(
                candidate_key=candidate_key,
                candidate_set_key=f"set-{candidate_key}",
                listing_id=listing_id,
                provider_id=provider_id,
                provider_attempt_id=provider_attempt_id,
                trading_date=date(2026, 5, int(candidate_key.split("-")[1])),
                price_type="current_day_unadjusted_open",
                value=value,
                currency="USD",
                provider_request_id=f"req-{candidate_key}",
                provider_observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
                audit_metadata={"selection_inputs": {"benchmark_value": str(benchmark)}},
            )
        )

    def _create_attempt(self, *, provider_id: int, attempt_key: str) -> ProviderAttempt:
        attempt = ProviderAttempt(
            attempt_key=attempt_key,
            provider_id=provider_id,
            exchange_id=self.exchange.id,
            request_purpose="pricing",
            load_type="current_day_open",
            requested_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
            result_status="success",
        )
        self.session.add(attempt)
        self.session.flush()
        return attempt

    def _report_for_run(self, run_key: str) -> ValidationExchangeReport:
        return (
            self.session.query(ValidationExchangeReport)
            .join(ValidationRun, ValidationRun.id == ValidationExchangeReport.validation_run_id)
            .filter(ValidationRun.run_key == run_key)
            .one()
        )


if __name__ == "__main__":
    unittest.main()
