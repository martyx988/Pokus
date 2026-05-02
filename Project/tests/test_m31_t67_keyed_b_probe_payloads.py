from __future__ import annotations

import unittest

from pokus_backend.validation.live_source_probe_runner import LiveSourceProbeExecutionContext
from pokus_backend.validation.source_probes.keyed_b.probe_http import HttpJsonResponse
from pokus_backend.validation.source_probes.keyed_b.probes import (
    probe_marketstack_source,
    probe_polygon_source,
    probe_tiingo_source,
    probe_twelve_data_source,
)


class KeyedBProbePayloadTests(unittest.TestCase):
    def test_tiingo_probe_uses_authorization_header_and_yields_fallback_payload(self) -> None:
        captured_headers: dict[str, str] = {}

        def _fetcher(url: str, *, headers=None):
            self.assertEqual(url, "https://api.tiingo.com/tiingo/daily/aapl")
            captured_headers.update(headers or {})
            return HttpJsonResponse(
                status_code=200,
                payload={"exchangeCode": "NASDAQ"},
                raw_body='{"exchangeCode":"NASDAQ"}',
                latency_ms=143,
            )

        payload = probe_tiingo_source(
            LiveSourceProbeExecutionContext(
                validation_run_key="rk",
                source_code="TIINGO",
                secrets={"TIINGO_API_KEY": "secret-1"},
            ),
            fetcher=_fetcher,
        )

        self.assertEqual(captured_headers.get("Authorization"), "Token secret-1")
        self.assertTrue(payload.is_available)
        self.assertEqual(payload.classification_verdict, "fallback_only")
        self.assertEqual(payload.assigned_role, "fallback_discovery")
        self.assertEqual(payload.observed_latency_ms, 143)
        self.assertIn("NASDAQ", payload.exchange_coverage_notes)

    def test_marketstack_probe_maps_401_into_validation_only_auth_blocked_payload(self) -> None:
        payload = probe_marketstack_source(
            LiveSourceProbeExecutionContext(
                validation_run_key="rk",
                source_code="MARKETSTACK",
                secrets={},
            ),
            fetcher=lambda _url, *, headers=None: HttpJsonResponse(
                status_code=401,
                payload={"error": {"code": "invalid_access_key", "message": "invalid key"}},
                raw_body='{"error":{"code":"invalid_access_key","message":"invalid key"}}',
                latency_ms=401,
            ),
        )

        self.assertFalse(payload.is_available)
        self.assertEqual(payload.classification_verdict, "validation_only")
        self.assertEqual(payload.assigned_role, "validation_only")
        self.assertIn("auth_required", payload.quota_rate_limit_notes)

    def test_polygon_probe_success_marks_fallback_role_and_latency(self) -> None:
        payload = probe_polygon_source(
            LiveSourceProbeExecutionContext(
                validation_run_key="rk",
                source_code="POLYGON",
                secrets={"POLYGON_API_KEY": "polygon-k"},
            ),
            fetcher=lambda _url, *, headers=None: HttpJsonResponse(
                status_code=200,
                payload={"status": "OK", "count": 1, "results": [{"ticker": "AAPL"}]},
                raw_body='{"status":"OK","count":1}',
                latency_ms=89,
            ),
        )
        self.assertTrue(payload.is_available)
        self.assertEqual(payload.classification_verdict, "fallback_only")
        self.assertEqual(payload.assigned_role, "fallback_discovery")
        self.assertEqual(payload.observed_latency_ms, 89)

    def test_twelve_data_probe_maps_embedded_auth_error_code(self) -> None:
        payload = probe_twelve_data_source(
            LiveSourceProbeExecutionContext(
                validation_run_key="rk",
                source_code="TWELVE_DATA",
                secrets={},
            ),
            fetcher=lambda _url, *, headers=None: HttpJsonResponse(
                status_code=200,
                payload={"code": 401, "message": "apikey incorrect"},
                raw_body='{"code":401,"message":"apikey incorrect"}',
                latency_ms=77,
            ),
        )
        self.assertFalse(payload.is_available)
        self.assertEqual(payload.classification_verdict, "validation_only")
        self.assertEqual(payload.assigned_role, "validation_only")
        self.assertIn("apikey incorrect", payload.quota_rate_limit_notes)


if __name__ == "__main__":
    unittest.main()
