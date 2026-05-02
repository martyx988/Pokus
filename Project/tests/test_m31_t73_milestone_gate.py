from __future__ import annotations

import json
import unittest
from pathlib import Path

from pokus_backend.validation.combined_source_classification import build_combined_source_matrix_from_artifacts


class T73Milestone31IntegrationGateTests(unittest.TestCase):
    def test_m31_gate_covers_all_sources_and_required_verdict_families(self) -> None:
        matrix = build_combined_source_matrix_from_artifacts()
        by_source = {row.source_code: row for row in matrix}

        expected_sources = {
            "YFINANCE",
            "EODHD",
            "FMP",
            "FINNHUB",
            "ALPHA_VANTAGE",
            "STOOQ",
            "TIINGO",
            "MARKETSTACK",
            "POLYGON",
            "NASDAQ_TRADER",
            "NYSE",
            "PSE_PSE_EDGE",
            "TWELVE_DATA",
            "OPENFIGI",
            "NASDAQ_DATA_LINK",
            "FRED",
            "DBNOMICS",
            "IMF",
            "WORLDBANK",
            "AKSHARE",
        }
        self.assertSetEqual(set(by_source.keys()), expected_sources)

        verdicts = {row.milestone_verdict for row in matrix}
        self.assertIn("not_for_universe_loader", verdicts)
        self.assertIn("validation_only", verdicts)
        self.assertTrue({"promote", "fallback_only"} & verdicts)

    def test_m31_gate_validates_rerun_documentation_and_live_execution_evidence(self) -> None:
        readme_text = Path("README.md").read_text(encoding="utf-8")
        dev_runtime_text = Path("DEV_RUNTIME.md").read_text(encoding="utf-8")

        self.assertIn("--run-live-source-probes", readme_text)
        self.assertIn("--run-combined-universe-loader", readme_text)
        self.assertIn("--run-live-source-probes", dev_runtime_text)
        self.assertIn("--run-combined-universe-loader", dev_runtime_text)

        summary_path = Path("src/pokus_backend/validation/artifacts/m3_1_t73_gate_summary.json")
        payload = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["task_id"], "T73")
        self.assertIn("environment_assumptions", payload)
        self.assertIn("live_commands", payload)
        self.assertEqual(len(payload["live_commands"]), 2)
        self.assertEqual(payload["live_commands"][0]["command_type"], "live_source_validation")
        self.assertEqual(payload["live_commands"][1]["command_type"], "combined_loader_runtime")

        for row in payload["live_commands"]:
            self.assertIn(row["status"], {"pass", "fail", "skip"})
            self.assertIn("command", row)
            self.assertIn("observed_on_utc", row)
            self.assertIn("details", row)


if __name__ == "__main__":
    unittest.main()
