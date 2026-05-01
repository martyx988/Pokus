from __future__ import annotations

import unittest
from typing import Any, Mapping, Sequence

from pokus_backend.discovery.adapter import (
    DiscoveryAdapter,
    DiscoveryRequest,
    normalize_discovery_payloads,
)
from pokus_backend.discovery.contract import DiscoveryCandidate, candidate_from_payload


class _FakeDiscoveryAdapter(DiscoveryAdapter):
    def __init__(self, payloads: Sequence[Mapping[str, Any]]) -> None:
        self._payloads = payloads

    def discover(self, request: DiscoveryRequest) -> Sequence[DiscoveryCandidate]:
        _ = request
        return normalize_discovery_payloads(self._payloads)


class DiscoveryAdapterContractTests(unittest.TestCase):
    def test_fake_adapter_normalizes_required_fields_and_identifiers(self) -> None:
        adapter = _FakeDiscoveryAdapter(
            payloads=[
                {
                    "exchange": " nyse ",
                    "instrument_type": " equity ",
                    "symbol": " aapl ",
                    "name": "Apple Inc.",
                    "stable_identifiers": {"ISIN": "US0378331005", "figi": "BBG000B9XRY4"},
                }
            ]
        )

        result = adapter.discover(
            DiscoveryRequest(exchange="NYSE", instrument_types=("EQUITY",))
        )

        self.assertEqual(len(result), 1)
        candidate = result[0]
        self.assertEqual(candidate.exchange, "NYSE")
        self.assertEqual(candidate.instrument_type, "EQUITY")
        self.assertEqual(candidate.symbol, "AAPL")
        self.assertEqual(candidate.name, "Apple Inc.")
        self.assertEqual(
            candidate.stable_identifiers,
            {"isin": "US0378331005", "figi": "BBG000B9XRY4"},
        )

    def test_contract_accepts_missing_optional_identifiers(self) -> None:
        candidate = candidate_from_payload(
            {
                "exchange": "PSE",
                "instrument_type": "EQUITY",
                "symbol": "CEZ",
                "name": "CEZ as",
            }
        )

        self.assertEqual(candidate.stable_identifiers, {})

    def test_contract_rejects_invalid_required_fields(self) -> None:
        invalid_payloads = (
            {"exchange": "", "instrument_type": "EQUITY", "symbol": "AAPL", "name": "Apple"},
            {"exchange": "NYSE", "instrument_type": "", "symbol": "AAPL", "name": "Apple"},
            {"exchange": "NYSE", "instrument_type": "EQUITY", "symbol": "", "name": "Apple"},
            {"exchange": "NYSE", "instrument_type": "EQUITY", "symbol": "AAPL", "name": ""},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    candidate_from_payload(payload)

    def test_contract_rejects_invalid_identifier_shape(self) -> None:
        with self.assertRaises(ValueError):
            candidate_from_payload(
                {
                    "exchange": "NYSE",
                    "instrument_type": "EQUITY",
                    "symbol": "AAPL",
                    "name": "Apple",
                    "stable_identifiers": ["US0378331005"],
                }
            )

        with self.assertRaises(ValueError):
            candidate_from_payload(
                {
                    "exchange": "NYSE",
                    "instrument_type": "EQUITY",
                    "symbol": "AAPL",
                    "name": "Apple",
                    "stable_identifiers": {"": "US0378331005"},
                }
            )


if __name__ == "__main__":
    unittest.main()
