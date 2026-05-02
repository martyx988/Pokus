from __future__ import annotations

import unittest

from pokus_backend.validation.live_source_probe_runner import LiveSourceProbeExecutionContext
from pokus_backend.validation.source_probes.official_symbology.probe_http import HttpProbeResponse
from pokus_backend.validation.source_probes.official_symbology.probes import (
    NASDAQ_DATA_LINK_SOURCE_CODE,
    NASDAQ_TRADER_SOURCE_CODE,
    NYSE_SOURCE_CODE,
    OPENFIGI_SOURCE_CODE,
    PSE_PSE_EDGE_SOURCE_CODE,
    build_official_symbology_probe_registry,
    normalize_official_symbology_source_codes,
)


class M31T68OfficialSymbologyNormalizationTests(unittest.TestCase):
    def test_normalize_source_codes_accepts_expected_aliases(self) -> None:
        normalized = normalize_official_symbology_source_codes(
            ["nasdaq trader", "nyse", "pse edge", "open_figi", "nasdaq datalink"]
        )

        self.assertEqual(
            normalized,
            [
                NASDAQ_TRADER_SOURCE_CODE,
                NYSE_SOURCE_CODE,
                PSE_PSE_EDGE_SOURCE_CODE,
                OPENFIGI_SOURCE_CODE,
                NASDAQ_DATA_LINK_SOURCE_CODE,
            ],
        )

    def test_normalize_source_codes_rejects_unknown_source(self) -> None:
        with self.assertRaises(ValueError):
            normalize_official_symbology_source_codes(["UNKNOWN_SOURCE"])

    def test_probe_registry_returns_validation_only_for_nasdaq_data_link_key_error(self) -> None:
        def _fake_fetcher(url: str, **_: object) -> HttpProbeResponse:
            self.assertIn("data.nasdaq.com", url)
            return HttpProbeResponse(
                status_code=403,
                headers={"content-type": "application/json"},
                body_text=(
                    '{"quandl_error":{"code":"QEPx04","message":"A valid API key is required to retrieve data."}}'
                ),
                latency_ms=47,
            )

        registry = build_official_symbology_probe_registry(fetcher=_fake_fetcher)
        payload = registry[NASDAQ_DATA_LINK_SOURCE_CODE].probe(
            LiveSourceProbeExecutionContext(
                validation_run_key="m31-t68-key-error",
                source_code=NASDAQ_DATA_LINK_SOURCE_CODE,
                secrets={},
            )
        )

        self.assertFalse(payload.is_available)
        self.assertEqual(payload.classification_verdict, "validation_only")
        self.assertEqual(payload.assigned_role, "validation_only")
        self.assertIn("api_key_required", payload.quota_rate_limit_notes)


if __name__ == "__main__":
    unittest.main()