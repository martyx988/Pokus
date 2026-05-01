from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from typing import Any, Mapping, Sequence

from pokus_backend.pricing.adapter import (
    PriceCandidateRequest,
    ProviderPriceAdapter,
    normalize_price_candidate_payloads,
)
from pokus_backend.pricing.contract import candidate_from_payload


class _FakeProviderPriceAdapter(ProviderPriceAdapter):
    def __init__(
        self,
        historical_payloads: Sequence[Mapping[str, Any]],
        open_payloads: Sequence[Mapping[str, Any]],
    ) -> None:
        self._historical_payloads = historical_payloads
        self._open_payloads = open_payloads

    def fetch_historical_close_candidates(self, request: PriceCandidateRequest):
        _ = request
        return normalize_price_candidate_payloads(self._historical_payloads)

    def fetch_current_day_open_candidates(self, request: PriceCandidateRequest):
        _ = request
        return normalize_price_candidate_payloads(self._open_payloads)


class PriceAdapterContractTests(unittest.TestCase):
    def test_fake_adapter_normalizes_valid_historical_and_open_candidates(self) -> None:
        adapter = _FakeProviderPriceAdapter(
            historical_payloads=[
                {
                    "instrument_id": "ins_101",
                    "listing_id": "lst_101",
                    "exchange": " nyse ",
                    "trading_day": "2026-04-30",
                    "price_type": "historical_adjusted_close",
                    "value": "189.77",
                    "currency": " usd ",
                    "provider_code": "alpha",
                    "provider_observed_at": "2026-04-30T22:00:00+00:00",
                    "provider_request_id": "req-h-1",
                    "provider_metadata": {"endpoint": "historical", "source": "primary"},
                }
            ],
            open_payloads=[
                {
                    "instrument_id": "ins_101",
                    "listing_id": "lst_101",
                    "exchange": " nyse ",
                    "trading_day": "2026-05-01",
                    "price_type": "current_day_unadjusted_open",
                    "value": "190.01",
                    "currency": " usd ",
                    "provider_code": "alpha",
                    "provider_request_id": "req-o-1",
                    "provider_metadata": {"endpoint": "open"},
                }
            ],
        )

        request = PriceCandidateRequest(
            instrument_id="ins_101",
            listing_id="lst_101",
            exchange="NYSE",
            symbol="AAPL",
            trading_day=date(2026, 5, 1),
        )

        historical = adapter.fetch_historical_close_candidates(request)
        current_open = adapter.fetch_current_day_open_candidates(request)

        self.assertEqual(historical[0].price_type, "historical_adjusted_close")
        self.assertEqual(historical[0].exchange, "NYSE")
        self.assertEqual(historical[0].currency, "USD")
        self.assertEqual(historical[0].value, Decimal("189.77"))
        self.assertEqual(historical[0].provider_metadata, {"endpoint": "historical", "source": "primary"})

        self.assertEqual(current_open[0].price_type, "current_day_unadjusted_open")
        self.assertEqual(current_open[0].trading_day, date(2026, 5, 1))
        self.assertEqual(current_open[0].value, Decimal("190.01"))
        self.assertEqual(current_open[0].provider_metadata, {"endpoint": "open"})

    def test_contract_rejects_invalid_required_payload_fields(self) -> None:
        invalid_payloads = (
            {
                "instrument_id": "",
                "listing_id": "lst_1",
                "exchange": "NYSE",
                "trading_day": "2026-05-01",
                "price_type": "historical_adjusted_close",
                "value": "100",
                "currency": "USD",
                "provider_code": "alpha",
            },
            {
                "instrument_id": "ins_1",
                "listing_id": "lst_1",
                "exchange": "NYSE",
                "trading_day": "bad-date",
                "price_type": "historical_adjusted_close",
                "value": "100",
                "currency": "USD",
                "provider_code": "alpha",
            },
            {
                "instrument_id": "ins_1",
                "listing_id": "lst_1",
                "exchange": "NYSE",
                "trading_day": "2026-05-01",
                "price_type": "invalid_type",
                "value": "100",
                "currency": "USD",
                "provider_code": "alpha",
            },
            {
                "instrument_id": "ins_1",
                "listing_id": "lst_1",
                "exchange": "NYSE",
                "trading_day": "2026-05-01",
                "price_type": "current_day_unadjusted_open",
                "value": "0",
                "currency": "USD",
                "provider_code": "alpha",
            },
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    candidate_from_payload(payload)

    def test_contract_rejects_invalid_provider_metadata_shape(self) -> None:
        with self.assertRaises(ValueError):
            candidate_from_payload(
                {
                    "instrument_id": "ins_1",
                    "listing_id": "lst_1",
                    "exchange": "NYSE",
                    "trading_day": "2026-05-01",
                    "price_type": "historical_adjusted_close",
                    "value": "10.5",
                    "currency": "USD",
                    "provider_code": "alpha",
                    "provider_metadata": ["bad"],
                }
            )

        with self.assertRaises(ValueError):
            candidate_from_payload(
                {
                    "instrument_id": "ins_1",
                    "listing_id": "lst_1",
                    "exchange": "NYSE",
                    "trading_day": "2026-05-01",
                    "price_type": "current_day_unadjusted_open",
                    "value": "10.5",
                    "currency": "USD",
                    "provider_code": "alpha",
                    "provider_metadata": {"": "x"},
                }
            )


if __name__ == "__main__":
    unittest.main()
