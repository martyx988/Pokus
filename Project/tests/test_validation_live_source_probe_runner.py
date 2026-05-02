from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.live_source_probe_runner import (
    LiveSourceProbeDefinition,
    LiveSourceProbeExecutionContext,
    LiveSourceProbeExecutionPayload,
    run_live_source_probes,
)
from pokus_backend.validation.source_validation_records import list_source_validation_records_for_run


class LiveSourceProbeRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_runner_normalizes_source_selection_and_persists_success_evidence(self) -> None:
        def _probe(_: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
            return LiveSourceProbeExecutionPayload(
                is_available=True,
                quota_rate_limit_notes="No limiting seen in probe window.",
                speed_notes="Median 120ms over sample requests.",
                exchange_coverage_notes="Useful for NYSE/NASDAQ; PSE partial.",
                classification_verdict="promote",
                assigned_role="primary_discovery",
                observed_latency_ms=120,
            )

        result = run_live_source_probes(
            self.session,
            source_codes=[" yf ", "YF"],
            validation_run_key="m3.1-live-source-run",
            probe_registry={
                "YF": LiveSourceProbeDefinition(source_code="YF", probe=_probe),
            },
        )
        self.session.commit()

        self.assertEqual(result.validation_run_key, "m3.1-live-source-run")
        self.assertEqual(len(result.source_results), 1)
        self.assertEqual(result.source_results[0].source_code, "YF")
        self.assertEqual(result.source_results[0].status, "succeeded")
        self.assertEqual(result.succeeded_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(result.failed_count, 0)

        rows = list_source_validation_records_for_run(self.session, validation_run_key="m3.1-live-source-run")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].source_code, "YF")
        self.assertTrue(rows[0].is_available)
        self.assertEqual(rows[0].classification_verdict, "promote")
        self.assertEqual(rows[0].assigned_role, "primary_discovery")

    def test_runner_marks_missing_required_secret_as_auditable_skip(self) -> None:
        probe_called = False

        def _probe(_: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
            nonlocal probe_called
            probe_called = True
            return LiveSourceProbeExecutionPayload(
                is_available=True,
                quota_rate_limit_notes="n/a",
                speed_notes="n/a",
                exchange_coverage_notes="n/a",
                classification_verdict="promote",
            )

        result = run_live_source_probes(
            self.session,
            source_codes=["FMP"],
            validation_run_key="m3.1-live-source-required-secret",
            probe_registry={
                "FMP": LiveSourceProbeDefinition(
                    source_code="FMP",
                    probe=_probe,
                    secret_mode="required",
                    secret_env_vars=("FMP_API_KEY",),
                ),
            },
            env={},
        )
        self.session.commit()

        self.assertFalse(probe_called)
        self.assertEqual(result.source_results[0].status, "skipped_missing_required_secret")
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.failed_count, 0)

        rows = list_source_validation_records_for_run(
            self.session,
            validation_run_key="m3.1-live-source-required-secret",
        )
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].is_available)
        self.assertTrue(rows[0].auth_required)
        self.assertEqual(rows[0].classification_verdict, "validation_only")
        self.assertEqual(rows[0].assigned_role, "validation_only")
        self.assertIn("missing_required_secrets:FMP_API_KEY", rows[0].quota_rate_limit_notes)

    def test_runner_marks_missing_optional_secret_as_auditable_skip(self) -> None:
        result = run_live_source_probes(
            self.session,
            source_codes=["POLYGON"],
            validation_run_key="m3.1-live-source-optional-secret",
            probe_registry={
                "POLYGON": LiveSourceProbeDefinition(
                    source_code="POLYGON",
                    probe=lambda _: LiveSourceProbeExecutionPayload(
                        is_available=True,
                        quota_rate_limit_notes="n/a",
                        speed_notes="n/a",
                        exchange_coverage_notes="n/a",
                        classification_verdict="promote",
                    ),
                    secret_mode="optional",
                    secret_env_vars=("POLYGON_API_KEY",),
                ),
            },
            env={},
        )
        self.session.commit()

        self.assertEqual(result.source_results[0].status, "skipped_missing_optional_secret")
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.failed_count, 0)

        rows = list_source_validation_records_for_run(
            self.session,
            validation_run_key="m3.1-live-source-optional-secret",
        )
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].is_available)
        self.assertFalse(rows[0].auth_required)
        self.assertEqual(rows[0].classification_verdict, "validation_only")
        self.assertEqual(rows[0].assigned_role, "validation_only")
        self.assertIn("missing_optional_secrets:POLYGON_API_KEY", rows[0].quota_rate_limit_notes)


if __name__ == "__main__":
    unittest.main()
