from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pokus_backend.validation.combined_source_classification import (
    SourceEvidenceRecord,
    build_combined_source_matrix_from_artifacts,
    derive_combined_source_matrix,
    persist_combined_matrix_artifact,
)
from pokus_backend.validation.source_role_selector import select_sources_for_runtime_role


class T70CombinedSourceClassificationTests(unittest.TestCase):
    def test_derives_all_required_outcomes_and_roles(self) -> None:
        matrix = derive_combined_source_matrix(
            [
                SourceEvidenceRecord(
                    source_code="primary_src",
                    classification_verdict="promote",
                    assigned_role="primary_discovery",
                    is_available=True,
                    evidence_origin="unit",
                ),
                SourceEvidenceRecord(
                    source_code="fallback_src",
                    classification_verdict="fallback_only",
                    assigned_role="metadata_enrichment",
                    is_available=True,
                    evidence_origin="unit",
                ),
                SourceEvidenceRecord(
                    source_code="validation_src",
                    classification_verdict="validation_only",
                    assigned_role="validation_only",
                    is_available=False,
                    evidence_origin="unit",
                ),
                SourceEvidenceRecord(
                    source_code="macro_src",
                    classification_verdict="not_for_universe_loader",
                    assigned_role="not_for_universe_loader",
                    is_available=True,
                    evidence_origin="unit",
                ),
                SourceEvidenceRecord(
                    source_code="reject_src",
                    classification_verdict="reject",
                    assigned_role=None,
                    is_available=False,
                    evidence_origin="unit",
                ),
            ]
        )
        by_source = {row.source_code: row for row in matrix}

        self.assertEqual(by_source["PRIMARY_SRC"].runtime_role, "primary_discovery")
        self.assertTrue(by_source["PRIMARY_SRC"].selectable_for_loader)
        self.assertEqual(by_source["FALLBACK_SRC"].runtime_role, "fallback_discovery")
        self.assertTrue(by_source["FALLBACK_SRC"].selectable_for_loader)
        self.assertEqual(by_source["VALIDATION_SRC"].runtime_role, "validation_only")
        self.assertFalse(by_source["VALIDATION_SRC"].selectable_for_loader)
        self.assertEqual(by_source["MACRO_SRC"].runtime_role, "not_for_universe_loader")
        self.assertFalse(by_source["MACRO_SRC"].selectable_for_loader)
        self.assertEqual(by_source["REJECT_SRC"].runtime_role, "not_for_universe_loader")
        self.assertFalse(by_source["REJECT_SRC"].selectable_for_loader)

    def test_builds_and_persists_auditable_matrix_from_t65_to_t69_artifacts(self) -> None:
        matrix = build_combined_source_matrix_from_artifacts()
        self.assertGreaterEqual(len(matrix), 20)

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "combined_matrix.json"
            persist_combined_matrix_artifact(matrix, artifact_path=artifact_path)
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["task_id"], "T70")
        self.assertEqual(len(payload["matrix"]), len(matrix))
        self.assertEqual(payload["matrix"][0]["source_code"], sorted(item["source_code"] for item in payload["matrix"])[0])

    def test_selects_only_loader_eligible_sources_for_role(self) -> None:
        matrix = derive_combined_source_matrix(
            [
                SourceEvidenceRecord(
                    source_code="NASDAQ_TRADER",
                    classification_verdict="promote",
                    assigned_role="primary_discovery",
                    is_available=True,
                    evidence_origin="unit",
                ),
                SourceEvidenceRecord(
                    source_code="NYSE",
                    classification_verdict="promote",
                    assigned_role="primary_discovery",
                    is_available=True,
                    evidence_origin="unit",
                ),
                SourceEvidenceRecord(
                    source_code="STOOQ",
                    classification_verdict="validation_only",
                    assigned_role="validation_only",
                    is_available=False,
                    evidence_origin="unit",
                ),
            ]
        )

        selected = select_sources_for_runtime_role(matrix, runtime_role="primary_discovery")
        self.assertEqual(selected, ("NASDAQ_TRADER", "NYSE"))
        self.assertEqual(select_sources_for_runtime_role(matrix, runtime_role="validation_only"), ())


if __name__ == "__main__":
    unittest.main()
