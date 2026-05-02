from __future__ import annotations

import unittest

from pokus_backend.validation.source_probes.keyed_b.probes import (
    KEYED_B_SOURCE_CODES,
    build_keyed_b_probe_registry,
    keyed_b_env_with_secret_fallbacks,
)


class KeyedBProbeRegistryTests(unittest.TestCase):
    def test_registry_contains_all_expected_sources_with_required_secret_mode(self) -> None:
        registry = build_keyed_b_probe_registry()
        self.assertEqual(set(registry.keys()), set(KEYED_B_SOURCE_CODES))
        self.assertEqual(KEYED_B_SOURCE_CODES, ("TIINGO", "MARKETSTACK", "POLYGON", "TWELVE_DATA"))

        for source_code in KEYED_B_SOURCE_CODES:
            probe = registry[source_code]
            self.assertEqual(probe.source_code, source_code)
            self.assertEqual(probe.secret_mode, "required")
            self.assertEqual(len(probe.secret_env_vars), 1)

    def test_env_fallbacks_fill_aliases_and_default_placeholders(self) -> None:
        resolved = keyed_b_env_with_secret_fallbacks(
            {
                "SOURCE_PROBE_TIINGO_API_KEY": "t-key",
                "MARKETSTACK_API_KEY": "m-key",
                "SOURCE_PROBE_POLYGON_API_KEY": "p-key",
            }
        )
        self.assertEqual(resolved["TIINGO_API_KEY"], "t-key")
        self.assertEqual(resolved["MARKETSTACK_API_KEY"], "m-key")
        self.assertEqual(resolved["POLYGON_API_KEY"], "p-key")
        self.assertEqual(resolved["TWELVE_DATA_API_KEY"], "MISSING_KEY_LIVE_AUTH_CHECK")


if __name__ == "__main__":
    unittest.main()
