from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pokus_backend.domain.source_validation_models import SourceValidationRecord
from pokus_backend.validation.live_source_probe_runner import (
    LiveSourceProbeRunResult,
    LiveSourceProbeSourceResult,
)
from pokus_backend.validation.source_probes.keyed_b.evidence import write_keyed_b_live_probe_artifact


class KeyedBEvidenceArtifactTests(unittest.TestCase):
    def test_writer_persists_expected_summary_and_record_details(self) -> None:
        run_result = LiveSourceProbeRunResult(
            validation_run_key="m31-t67-run",
            source_results=[
                LiveSourceProbeSourceResult(
                    source_code="TIINGO",
                    status="succeeded",
                    persisted_record_id=11,
                    classification_verdict="validation_only",
                    note="probe_completed",
                )
            ],
        )
        now = datetime(2026, 5, 2, 9, 15, tzinfo=timezone.utc)
        records = [
            SourceValidationRecord(
                id=11,
                validation_run_key="m31-t67-run",
                source_code="TIINGO",
                is_available=False,
                auth_required=False,
                quota_rate_limit_notes="auth_required status=403 detail=Please supply a token",
                speed_notes="single_request_latency_ms=122",
                exchange_coverage_notes="US/PSE coverage could not be confirmed under current credentials.",
                observed_latency_ms=122,
                classification_verdict="validation_only",
                assigned_role="validation_only",
                recorded_at=now,
                updated_at=now,
            )
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_path = Path(tmp_dir) / "evidence.json"
            written = write_keyed_b_live_probe_artifact(
                artifact_path=artifact_path,
                command="python -m pokus_backend.validation.source_probes.keyed_b.live_run",
                run_result=run_result,
                records=records,
            )
            payload = json.loads(written.read_text(encoding="utf-8"))

        self.assertEqual(payload["task_id"], "T67")
        self.assertEqual(payload["validation_run_key"], "m31-t67-run")
        self.assertEqual(payload["summary"]["succeeded_count"], 1)
        self.assertEqual(payload["source_results"][0]["source_code"], "TIINGO")
        self.assertEqual(payload["records"][0]["classification_verdict"], "validation_only")
        self.assertIn("auth_required", payload["records"][0]["quota_rate_limit_notes"])


if __name__ == "__main__":
    unittest.main()
