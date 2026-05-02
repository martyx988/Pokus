from __future__ import annotations

import unittest

from pokus_backend.validation.source_probes.keyed_a.http_json import SourceProbeHttpError
from pokus_backend.validation.source_probes.keyed_a.probes import (
    KEYED_A_SOURCE_CODES,
    _payload_from_http_error,
    build_keyed_a_probe_registry,
    keyed_a_env_with_secret_aliases,
    normalize_keyed_a_source_codes,
)


class T66KeyedAProbeDefinitionsTests(unittest.TestCase):
    def test_normalize_keyed_a_sources_defaults_and_deduplicates(self) -> None:
        self.assertEqual(normalize_keyed_a_source_codes(None), list(KEYED_A_SOURCE_CODES))
        self.assertEqual(
            normalize_keyed_a_source_codes([" eodhd ", "FMP", "EODHD", "finnhub", "alpha_vantage"]),
            ["EODHD", "FMP", "FINNHUB", "ALPHA_VANTAGE"],
        )

    def test_normalize_keyed_a_sources_rejects_unsupported_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported keyed-a source code"):
            normalize_keyed_a_source_codes(["EODHD", "UNKNOWN"])

    def test_registry_requires_explicit_credentials_for_all_sources(self) -> None:
        registry = build_keyed_a_probe_registry()
        self.assertEqual(set(registry.keys()), set(KEYED_A_SOURCE_CODES))
        for source_code in KEYED_A_SOURCE_CODES:
            definition = registry[source_code]
            self.assertEqual(definition.secret_mode, "required")
            self.assertEqual(len(definition.secret_env_vars), 1)

    def test_secret_aliases_fill_expected_runner_env_vars(self) -> None:
        resolved = keyed_a_env_with_secret_aliases(
            {
                "EODHD_API_TOKEN": "eodhd-key",
                "SOURCE_PROBE_FMP_API_KEY": "fmp-key",
                "SOURCE_PROBE_FINNHUB_API_KEY": "finnhub-key",
                "ALPHAVANTAGE_API_KEY": "alpha-key",
            }
        )
        self.assertEqual(resolved["EODHD_API_KEY"], "eodhd-key")
        self.assertEqual(resolved["FMP_API_KEY"], "fmp-key")
        self.assertEqual(resolved["FINNHUB_API_KEY"], "finnhub-key")
        self.assertEqual(resolved["ALPHA_VANTAGE_API_KEY"], "alpha-key")

    def test_http_error_is_translated_into_validation_only_payload(self) -> None:
        error = SourceProbeHttpError(
            message="http_error:429",
            status_code=429,
            elapsed_ms=321,
            url="https://example.test",
            payload={"message": "limit reached"},
        )
        payload = _payload_from_http_error(source_code="FMP", error=error)
        self.assertFalse(payload.is_available)
        self.assertEqual(payload.classification_verdict, "validation_only")
        self.assertEqual(payload.assigned_role, "validation_only")
        self.assertIn("status=429", payload.quota_rate_limit_notes)
        self.assertEqual(payload.observed_latency_ms, 321)


if __name__ == "__main__":
    unittest.main()

