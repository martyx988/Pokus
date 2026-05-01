from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, Exchange
from pokus_backend.domain.reference_models import ValidationExchangeReport, ValidationRun
from pokus_backend.validation.run_orchestrator import orchestrate_launch_exchange_validation_run


class ValidationRunOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.session.add_all(
            [
                Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True),
                Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True),
                Exchange(code="PSE", name="Prague Stock Exchange", is_launch_active=True),
            ]
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_orchestrator_creates_run_and_report_shells_and_finishes(self) -> None:
        result = orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["NYSE", "NASDAQ", "PSE"],
            run_key="launch-window-1",
        )
        self.session.commit()

        self.assertEqual(result.run.state, "succeeded")
        self.assertIsNotNone(result.run.started_at)
        self.assertIsNotNone(result.run.finished_at)
        self.assertIsNone(result.run.failure_reason)
        self.assertEqual(len(result.reports), 3)
        self.assertEqual(self.session.query(ValidationRun).count(), 1)
        self.assertEqual(self.session.query(ValidationExchangeReport).count(), 3)
        self.assertEqual(result.reports[0].final_verdict, "pending")
        self.assertEqual(
            sorted(result.reports[0].result_buckets.keys()),
            sorted(
                [
                    "discovery_listing",
                    "completeness_timeliness",
                    "disagreement_benchmark",
                    "calendar_validation",
                ]
            ),
        )

    def test_orchestrator_can_mark_run_failed(self) -> None:
        result = orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["PSE"],
            run_key="launch-window-fail",
            fail_reason="blocked by fixture",
        )
        self.session.commit()

        self.assertEqual(result.run.state, "failed")
        self.assertEqual(result.run.failure_reason, "blocked by fixture")
        self.assertIsNotNone(result.run.started_at)
        self.assertIsNotNone(result.run.finished_at)
        self.assertEqual(len(result.reports), 1)
        self.assertEqual(result.reports[0].final_verdict, "pending")

    def test_rerun_with_same_run_key_is_idempotent(self) -> None:
        first = orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["NYSE", "NASDAQ"],
            run_key="stable-run-key",
        )
        self.session.commit()

        second = orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["NYSE", "NASDAQ"],
            run_key="stable-run-key",
        )
        self.session.commit()

        self.assertEqual(first.run.id, second.run.id)
        self.assertEqual(self.session.query(ValidationRun).count(), 1)
        self.assertEqual(self.session.query(ValidationExchangeReport).count(), 2)
        self.assertEqual(second.run.state, "succeeded")


if __name__ == "__main__":
    unittest.main()


