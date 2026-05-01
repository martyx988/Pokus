from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import (
    Base,
    CandidatePriceValue,
    Exchange,
    Instrument,
    InstrumentType,
    Listing,
    SupportedUniverseState,
    SupportedUniverseStatus,
)
from pokus_backend.domain.reference_models import Provider, ProviderAttempt, ValidationExchangeReport, ValidationRun
from pokus_backend.validation.run_orchestrator import orchestrate_launch_exchange_validation_run


class ValidationCompletenessTimelinessMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.provider = Provider(code="ALPHA", name="Alpha", is_active=True)
        self.session.add_all([self.exchange, self.instrument_type, self.provider])
        self.session.flush()
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_populates_passing_completeness_timeliness_metrics(self) -> None:
        listing = self._create_supported_listing(symbol="AAA")
        self._add_candidate(listing_id=listing.id, price_type="current_day_unadjusted_open", value=Decimal("100"))
        self._add_candidate(listing_id=listing.id, price_type="historical_adjusted_close", value=Decimal("99"))
        self._add_attempt(latency_ms=60000, requested_at=datetime(2026, 5, 1, 13, 31, tzinfo=timezone.utc))
        self.session.commit()

        result = orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["NYSE"],
            run_key="ct-pass",
        )
        self.session.commit()

        report = (
            self.session.query(ValidationExchangeReport)
            .join(ValidationRun, ValidationRun.id == ValidationExchangeReport.validation_run_id)
            .filter(ValidationRun.id == result.run.id)
            .one()
        )
        bucket = report.result_buckets["completeness_timeliness"]
        self.assertEqual(bucket["status"], "pass")
        self.assertEqual(bucket["findings"], [])
        self.assertTrue(bucket["evidence"]["daily_completeness"]["pass"])
        self.assertTrue(bucket["evidence"]["historical_completeness"]["pass"])
        self.assertTrue(bucket["evidence"]["timeliness"]["pass"])
        self.assertTrue(bucket["evidence"]["stale_missing_behavior"]["pass"])
        self.assertTrue(bucket["evidence"]["rate_limit_behavior"]["pass"])

    def test_populates_failing_completeness_timeliness_metrics(self) -> None:
        listing_a = self._create_supported_listing(symbol="AAA")
        listing_b = self._create_supported_listing(symbol="BBB")
        self._add_candidate(listing_id=listing_a.id, price_type="current_day_unadjusted_open", value=Decimal("100"))
        self._add_attempt(
            latency_ms=31 * 60 * 1000,
            requested_at=datetime(2026, 5, 1, 13, 40, tzinfo=timezone.utc),
            stale_data=True,
            missing_values=True,
        )
        for index in range(1, 5):
            self._add_attempt(
                latency_ms=32 * 60 * 1000,
                requested_at=datetime(2026, 5, 1, 13, 40, tzinfo=timezone.utc) - timedelta(minutes=index),
                result_status="rate_limited",
                rate_limit_hit=True,
            )
        self.session.commit()

        orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["NYSE"],
            run_key="ct-fail",
        )
        self.session.commit()

        report = (
            self.session.query(ValidationExchangeReport)
            .join(ValidationRun, ValidationRun.id == ValidationExchangeReport.validation_run_id)
            .filter(ValidationRun.run_key == "ct-fail")
            .one()
        )
        bucket = report.result_buckets["completeness_timeliness"]
        self.assertEqual(bucket["status"], "fail")
        self.assertIn("daily_completeness_threshold_not_met", bucket["findings"])
        self.assertIn("historical_completeness_threshold_not_met", bucket["findings"])
        self.assertIn("timeliness_threshold_not_met", bucket["findings"])
        self.assertIn("stale_or_missing_data_detected", bucket["findings"])
        self.assertIn("rate_limit_behavior_detected", bucket["findings"])
        self.assertEqual(bucket["evidence"]["daily_completeness"]["supported_listing_count"], 2)
        self.assertEqual(bucket["evidence"]["daily_completeness"]["covered_listing_count"], 1)
        self.assertEqual(bucket["evidence"]["timeliness"]["miss_count"], 5)
        self.assertEqual(bucket["evidence"]["stale_missing_behavior"]["stale_or_missing_count"], 1)
        self.assertEqual(bucket["evidence"]["rate_limit_behavior"]["rate_limit_count"], 4)

    def _create_supported_listing(self, *, symbol: str) -> Listing:
        instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name=f"Instrument {symbol}")
        self.session.add(instrument)
        self.session.flush()
        listing = Listing(instrument_id=instrument.id, exchange_id=self.exchange.id, symbol=symbol)
        self.session.add(listing)
        self.session.flush()
        self.session.add(SupportedUniverseState(listing_id=listing.id, status=SupportedUniverseStatus.SUPPORTED))
        self.session.flush()
        return listing

    def _add_candidate(self, *, listing_id: int, price_type: str, value: Decimal) -> None:
        self.session.add(
            CandidatePriceValue(
                candidate_key=f"{listing_id}-{price_type}-{value}",
                candidate_set_key=f"set-{listing_id}-{price_type}",
                listing_id=listing_id,
                provider_id=self.provider.id,
                provider_attempt_id=None,
                trading_date=date(2026, 5, 1),
                price_type=price_type,
                value=value,
                currency="USD",
                provider_request_id=None,
                provider_observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
                audit_metadata={"source": "test"},
            )
        )

    def _add_attempt(
        self,
        *,
        latency_ms: int,
        requested_at: datetime,
        result_status: str = "success",
        rate_limit_hit: bool = False,
        stale_data: bool = False,
        missing_values: bool = False,
    ) -> None:
        self.session.add(
            ProviderAttempt(
                attempt_key=f"attempt-{requested_at.timestamp()}-{result_status}-{latency_ms}",
                provider_id=self.provider.id,
                exchange_id=self.exchange.id,
                request_purpose="pricing",
                load_type="current_day_open",
                requested_at=requested_at,
                latency_ms=latency_ms,
                result_status=result_status,
                rate_limit_hit=rate_limit_hit,
                stale_data=stale_data,
                missing_values=missing_values,
            )
        )


if __name__ == "__main__":
    unittest.main()
