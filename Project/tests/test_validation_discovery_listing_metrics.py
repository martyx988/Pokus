from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing, SupportedUniverseState
from pokus_backend.domain.instrument_models import SupportedUniverseStatus
from pokus_backend.domain.reference_models import ValidationExchangeReport, ValidationRun
from pokus_backend.validation.run_orchestrator import orchestrate_launch_exchange_validation_run


class ValidationDiscoveryListingMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        nyse = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True, activity_priority_rank=1)
        nasdaq = Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True, activity_priority_rank=2)
        self.session.add_all([nyse, nasdaq, InstrumentType(code="STOCK", name="Stock", is_launch_active=True)])
        self.session.flush()

        stock_type_id = self.session.query(InstrumentType).filter_by(code="STOCK").one().id
        nyse_id = self.session.query(Exchange).filter_by(code="NYSE").one().id
        nasdaq_id = self.session.query(Exchange).filter_by(code="NASDAQ").one().id

        inst_a = Instrument(instrument_type_id=stock_type_id, canonical_name="Alpha")
        inst_b = Instrument(instrument_type_id=stock_type_id, canonical_name="Beta")
        self.session.add_all([inst_a, inst_b])
        self.session.flush()

        self.listing_a_nyse = Listing(instrument_id=inst_a.id, exchange_id=nyse_id, symbol="ALP")
        self.listing_a_nasdaq = Listing(instrument_id=inst_a.id, exchange_id=nasdaq_id, symbol="ALP")
        self.listing_b_nyse = Listing(instrument_id=inst_b.id, exchange_id=nyse_id, symbol="BET")
        self.session.add_all([self.listing_a_nyse, self.listing_a_nasdaq, self.listing_b_nyse])
        self.session.flush()
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_populates_passing_discovery_listing_metrics(self) -> None:
        self.session.add_all(
            [
                SupportedUniverseState(listing_id=self.listing_a_nyse.id, status=SupportedUniverseStatus.SUPPORTED),
                SupportedUniverseState(listing_id=self.listing_b_nyse.id, status=SupportedUniverseStatus.SUPPORTED),
            ]
        )
        self.session.commit()

        result = orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["NYSE", "NASDAQ"],
            run_key="metrics-pass",
        )
        self.session.commit()

        report_by_exchange = {
            report.exchange.code: report
            for report in self.session.query(ValidationExchangeReport)
            .join(ValidationRun, ValidationRun.id == ValidationExchangeReport.validation_run_id)
            .join(Exchange, Exchange.id == ValidationExchangeReport.exchange_id)
            .filter(ValidationRun.id == result.run.id)
            .all()
        }

        nyse_bucket = report_by_exchange["NYSE"].result_buckets["discovery_listing"]
        self.assertEqual(nyse_bucket["status"], "pass")
        self.assertEqual(nyse_bucket["findings"], [])
        self.assertEqual(nyse_bucket["evidence"]["discovery_quality"]["discovered_listing_count"], 2)
        self.assertEqual(nyse_bucket["evidence"]["discovery_quality"]["supported_listing_count"], 2)
        self.assertEqual(nyse_bucket["evidence"]["primary_listing_behavior"]["priority_order_violation_count"], 0)

        nasdaq_bucket = report_by_exchange["NASDAQ"].result_buckets["discovery_listing"]
        self.assertEqual(nasdaq_bucket["status"], "fail")
        self.assertIn("discovery_quality_threshold_not_met", nasdaq_bucket["findings"])

    def test_populates_failing_primary_listing_metrics(self) -> None:
        self.session.add_all(
            [
                SupportedUniverseState(listing_id=self.listing_a_nyse.id, status=SupportedUniverseStatus.SUPPORTED),
                SupportedUniverseState(listing_id=self.listing_a_nasdaq.id, status=SupportedUniverseStatus.SUPPORTED),
            ]
        )
        self.session.commit()

        orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["NYSE", "NASDAQ"],
            run_key="metrics-fail",
        )
        self.session.commit()

        reports = (
            self.session.query(ValidationExchangeReport)
            .join(ValidationRun, ValidationRun.id == ValidationExchangeReport.validation_run_id)
            .filter(ValidationRun.run_key == "metrics-fail")
            .all()
        )

        for report in reports:
            bucket = report.result_buckets["discovery_listing"]
            self.assertEqual(bucket["status"], "fail")
            self.assertIn("multiple_supported_listings_for_same_instrument", bucket["findings"])
            self.assertGreaterEqual(bucket["evidence"]["primary_listing_behavior"]["conflicting_supported_instrument_count"], 1)
            self.assertIsInstance(report.updated_at, datetime)
            self.assertIsNotNone(report.updated_at.tzinfo or timezone.utc)


if __name__ == "__main__":
    unittest.main()
