from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.live_source_probe_runner import (
    LiveSourceProbeDefinition,
    LiveSourceProbeExecutionContext,
    LiveSourceProbeExecutionPayload,
)
from pokus_backend.validation.source_probes.macro_enrichment.workflow import (
    run_macro_enrichment_source_probes,
)
from pokus_backend.validation.source_validation_records import list_source_validation_records_for_run


class MacroEnrichmentWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_workflow_persists_records_for_all_macro_enrichment_sources(self) -> None:
        def _payload_for(source_code: str) -> LiveSourceProbeExecutionPayload:
            return LiveSourceProbeExecutionPayload(
                is_available=True,
                quota_rate_limit_notes=f"{source_code} live endpoint reachable.",
                speed_notes=f"{source_code} probe latency sample captured.",
                exchange_coverage_notes=f"{source_code} is macro-only and not listing-oriented.",
                classification_verdict="not_for_universe_loader",
                assigned_role="not_for_universe_loader",
                observed_latency_ms=42,
            )

        def _make_probe(source_code: str):
            return lambda _: _payload_for(source_code)

        fake_registry = {
            "FRED": LiveSourceProbeDefinition(source_code="FRED", probe=_make_probe("FRED")),
            "DBNOMICS": LiveSourceProbeDefinition(source_code="DBNOMICS", probe=_make_probe("DBNOMICS")),
            "IMF": LiveSourceProbeDefinition(source_code="IMF", probe=_make_probe("IMF")),
            "WORLDBANK": LiveSourceProbeDefinition(source_code="WORLDBANK", probe=_make_probe("WORLDBANK")),
        }

        with patch(
            "pokus_backend.validation.source_probes.macro_enrichment.workflow.build_macro_enrichment_probe_registry",
            return_value=fake_registry,
        ):
            run_result = run_macro_enrichment_source_probes(
                self.session,
                validation_run_key="m31-t69-workflow-run",
            )
            self.session.commit()

        self.assertEqual(run_result.succeeded_count, 4)
        self.assertEqual(run_result.failed_count, 0)
        self.assertEqual(run_result.skipped_count, 0)

        rows = list_source_validation_records_for_run(self.session, validation_run_key="m31-t69-workflow-run")
        self.assertEqual([row.source_code for row in rows], ["DBNOMICS", "FRED", "IMF", "WORLDBANK"])
        self.assertTrue(all(row.is_available for row in rows))
        self.assertEqual(
            [row.classification_verdict for row in rows],
            [
                "not_for_universe_loader",
                "not_for_universe_loader",
                "not_for_universe_loader",
                "not_for_universe_loader",
            ],
        )
        self.assertEqual(
            [row.assigned_role for row in rows],
            [
                "not_for_universe_loader",
                "not_for_universe_loader",
                "not_for_universe_loader",
                "not_for_universe_loader",
            ],
        )

    def test_workflow_passes_source_code_context_into_each_probe(self) -> None:
        observed_source_codes: list[str] = []

        def _recording_probe(context: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
            observed_source_codes.append(context.source_code)
            return LiveSourceProbeExecutionPayload(
                is_available=True,
                quota_rate_limit_notes="ok",
                speed_notes="ok",
                exchange_coverage_notes="macro-only",
                classification_verdict="not_for_universe_loader",
                assigned_role="not_for_universe_loader",
            )

        fake_registry = {
            "FRED": LiveSourceProbeDefinition(source_code="FRED", probe=_recording_probe),
            "DBNOMICS": LiveSourceProbeDefinition(source_code="DBNOMICS", probe=_recording_probe),
            "IMF": LiveSourceProbeDefinition(source_code="IMF", probe=_recording_probe),
            "WORLDBANK": LiveSourceProbeDefinition(source_code="WORLDBANK", probe=_recording_probe),
        }

        with patch(
            "pokus_backend.validation.source_probes.macro_enrichment.workflow.build_macro_enrichment_probe_registry",
            return_value=fake_registry,
        ):
            run_macro_enrichment_source_probes(
                self.session,
                validation_run_key="m31-t69-workflow-context",
            )

        self.assertEqual(observed_source_codes, ["FRED", "DBNOMICS", "IMF", "WORLDBANK"])


if __name__ == "__main__":
    unittest.main()
