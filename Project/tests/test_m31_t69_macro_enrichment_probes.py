from __future__ import annotations

import unittest
from unittest.mock import patch

from pokus_backend.validation.live_source_probe_runner import LiveSourceProbeExecutionContext
from pokus_backend.validation.source_probes.macro_enrichment import probes


class MacroEnrichmentProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = LiveSourceProbeExecutionContext(
            validation_run_key="m31-t69-probe-test",
            source_code="FRED",
            secrets={},
        )

    def test_build_registry_contains_expected_source_codes(self) -> None:
        registry = probes.build_macro_enrichment_probe_registry()
        self.assertEqual(set(registry.keys()), {"FRED", "DBNOMICS", "IMF", "WORLDBANK"})

    def test_fred_probe_returns_not_for_universe_loader_verdict(self) -> None:
        with patch.object(
            probes,
            "_http_get",
            return_value=probes._HttpPayload(
                text="observation_date,GDP\n2025-10-01,31320.000\n",
                status_code=200,
                elapsed_ms=41,
            ),
        ):
            payload = probes.probe_fred(self.context)

        self.assertTrue(payload.is_available)
        self.assertEqual(payload.classification_verdict, "not_for_universe_loader")
        self.assertEqual(payload.assigned_role, "not_for_universe_loader")
        self.assertEqual(payload.observed_latency_ms, 41)

    def test_dbnomics_probe_returns_not_for_universe_loader_verdict(self) -> None:
        with patch.object(
            probes,
            "_http_get",
            return_value=probes._HttpPayload(
                text=(
                    '{"datasets":{"docs":[{"code":"BOP"},{"code":"DOT"},{"code":"CPI"}]}}'
                ),
                status_code=200,
                elapsed_ms=52,
            ),
        ):
            payload = probes.probe_dbnomics(self.context)

        self.assertTrue(payload.is_available)
        self.assertEqual(payload.classification_verdict, "not_for_universe_loader")
        self.assertIn("sample IMF codes: BOP,DOT,CPI", payload.exchange_coverage_notes)
        self.assertEqual(payload.observed_latency_ms, 52)

    def test_imf_probe_returns_not_for_universe_loader_verdict(self) -> None:
        with patch.object(
            probes,
            "_http_get",
            return_value=probes._HttpPayload(
                text='{"indicators":{"NGDP_RPCH":{"label":"Real GDP growth"},"PCPIPCH":{"label":"Inflation"}}}',
                status_code=200,
                elapsed_ms=63,
            ),
        ):
            payload = probes.probe_imf(self.context)

        self.assertTrue(payload.is_available)
        self.assertEqual(payload.classification_verdict, "not_for_universe_loader")
        self.assertIn("contains NGDP_RPCH=True", payload.exchange_coverage_notes)
        self.assertEqual(payload.observed_latency_ms, 63)

    def test_world_bank_probe_returns_not_for_universe_loader_verdict(self) -> None:
        with patch.object(
            probes,
            "_http_get",
            return_value=probes._HttpPayload(
                text=(
                    '[{"page":1},['
                    '{"date":"2025","value":null},'
                    '{"date":"2024","value":29184890000000}'
                    "]]"
                ),
                status_code=200,
                elapsed_ms=74,
            ),
        ):
            payload = probes.probe_world_bank(self.context)

        self.assertTrue(payload.is_available)
        self.assertEqual(payload.classification_verdict, "not_for_universe_loader")
        self.assertIn("latest non-null 2024=29184890000000", payload.exchange_coverage_notes)
        self.assertEqual(payload.observed_latency_ms, 74)


if __name__ == "__main__":
    unittest.main()
