from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, CandidatePriceValue, Exchange, Instrument, InstrumentType, Listing
from pokus_backend.domain.reference_models import Provider, ProviderAttempt, ValidationExchangeReport, ValidationRun
from pokus_backend.validation.run_orchestrator import orchestrate_launch_exchange_validation_run


class ValidationCalendarMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.provider = Provider(code="ALPHA", name="Alpha", is_active=True)
        self.session.add_all([self.exchange, self.instrument_type, self.provider])
        self.session.flush()

        instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Instrument AAA")
        self.session.add(instrument)
        self.session.flush()
        self.listing = Listing(instrument_id=instrument.id, exchange_id=self.exchange.id, symbol="AAA")
        self.session.add(self.listing)
        self.session.flush()

        self.attempt = ProviderAttempt(
            attempt_key="calendar-attempt",
            provider_id=self.provider.id,
            exchange_id=self.exchange.id,
            request_purpose="validation_calendar",
            load_type="current_day_open",
            requested_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
            result_status="success",
        )
        self.session.add(self.attempt)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_calendar_validation_matches_and_keeps_library_acceptable(self) -> None:
        self._add_reference_candidate(
            candidate_key="cal-pass-weekend",
            trading_date=date(2026, 5, 2),
            expected_is_trading_day=False,
            reference_type="weekend",
        )
        self._add_reference_candidate(
            candidate_key="cal-pass-holiday",
            trading_date=date(2026, 7, 3),
            expected_is_trading_day=False,
            reference_type="holiday",
        )
        self.session.commit()

        orchestrate_launch_exchange_validation_run(self.session, target_exchange_codes=["NYSE"], run_key="calendar-pass")
        self.session.commit()

        bucket = self._report_for_run("calendar-pass").result_buckets["calendar_validation"]
        self.assertEqual(bucket["status"], "pass")
        self.assertEqual(bucket["decision"]["state"], "library_acceptable")
        self.assertFalse(bucket["decision"]["custom_adapter_followup_required"])
        self.assertEqual(bucket["evidence"]["comparison"]["match_count"], 2)
        self.assertEqual(bucket["evidence"]["comparison"]["mismatch_count"], 0)
        self.assertEqual(bucket["evidence"]["validation_window"]["start"], "2026-05-02")
        self.assertEqual(bucket["evidence"]["validation_window"]["end"], "2026-07-03")

    def test_calendar_validation_mismatch_requires_custom_adapter_followup(self) -> None:
        self._add_reference_candidate(
            candidate_key="cal-fail-weekday",
            trading_date=date(2026, 5, 4),
            expected_is_trading_day=False,
            reference_type="holiday",
        )
        self.session.commit()

        orchestrate_launch_exchange_validation_run(self.session, target_exchange_codes=["NYSE"], run_key="calendar-fail")
        self.session.commit()

        bucket = self._report_for_run("calendar-fail").result_buckets["calendar_validation"]
        self.assertEqual(bucket["status"], "fail")
        self.assertIn("calendar_library_reference_mismatch_detected", bucket["findings"])
        self.assertEqual(bucket["decision"]["state"], "custom_adapter_required")
        self.assertTrue(bucket["decision"]["custom_adapter_followup_required"])
        self.assertEqual(bucket["evidence"]["comparison"]["mismatch_count"], 1)
        self.assertEqual(len(bucket["evidence"]["mismatch_evidence_refs"]), 1)

    def _add_reference_candidate(
        self,
        *,
        candidate_key: str,
        trading_date: date,
        expected_is_trading_day: bool,
        reference_type: str,
    ) -> None:
        self.session.add(
            CandidatePriceValue(
                candidate_key=candidate_key,
                candidate_set_key=f"set-{candidate_key}",
                listing_id=self.listing.id,
                provider_id=self.provider.id,
                provider_attempt_id=self.attempt.id,
                trading_date=trading_date,
                price_type="current_day_unadjusted_open",
                value=Decimal("100"),
                currency="USD",
                provider_request_id=f"req-{candidate_key}",
                provider_observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
                audit_metadata={
                    "selection_inputs": {
                        "calendar_reference": {
                            "expected_is_trading_day": expected_is_trading_day,
                            "reference_type": reference_type,
                            "reference_source": "official_exchange_calendar",
                        }
                    }
                },
            )
        )

    def _report_for_run(self, run_key: str) -> ValidationExchangeReport:
        return (
            self.session.query(ValidationExchangeReport)
            .join(ValidationRun, ValidationRun.id == ValidationExchangeReport.validation_run_id)
            .filter(ValidationRun.run_key == run_key)
            .one()
        )


if __name__ == "__main__":
    unittest.main()
