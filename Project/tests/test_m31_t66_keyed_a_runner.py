from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.source_validation_records import list_source_validation_records_for_run
from pokus_backend.validation.source_probes.keyed_a.probes import KEYED_A_SOURCE_CODES
from pokus_backend.validation.source_probes.keyed_a.runner import run_keyed_a_source_probes


class T66KeyedARunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_runner_marks_missing_required_secrets_for_all_keyed_a_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "t66-keyed-a.json"
            run_result, created_artifact_path = run_keyed_a_source_probes(
                self.session,
                validation_run_key="m3.1-t66-missing-secret-check",
                source_codes=list(KEYED_A_SOURCE_CODES),
                env={},
                artifact_output_path=artifact_path,
            )
            self.session.commit()

            self.assertEqual(run_result.validation_run_key, "m3.1-t66-missing-secret-check")
            self.assertEqual(len(run_result.source_results), 4)
            self.assertEqual(run_result.succeeded_count, 0)
            self.assertEqual(run_result.failed_count, 0)
            self.assertEqual(run_result.skipped_count, 4)
            for source_result in run_result.source_results:
                self.assertEqual(source_result.status, "skipped_missing_required_secret")
                self.assertEqual(source_result.classification_verdict, "validation_only")

            rows = list_source_validation_records_for_run(
                self.session,
                validation_run_key="m3.1-t66-missing-secret-check",
            )
            self.assertEqual(len(rows), 4)
            for row in rows:
                self.assertTrue(row.auth_required)
                self.assertEqual(row.classification_verdict, "validation_only")
                self.assertEqual(row.assigned_role, "validation_only")
                self.assertIn("missing_required_secrets:", row.quota_rate_limit_notes)

            self.assertEqual(created_artifact_path, artifact_path)
            self.assertTrue(artifact_path.exists())
            artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact_payload["validation_run_key"], "m3.1-t66-missing-secret-check")
            self.assertEqual(artifact_payload["summary"]["skipped_count"], 4)
            self.assertEqual(len(artifact_payload["source_results"]), 4)
            self.assertEqual(len(artifact_payload["source_validation_records"]), 4)


if __name__ == "__main__":
    unittest.main()

