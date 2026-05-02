from __future__ import annotations

import unittest
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.discovery.combined_loader import execute_combined_universe_loader
from pokus_backend.discovery.contract import DiscoveryCandidate
from pokus_backend.domain import Base, Exchange, IdentifierRecord, InstrumentType, Listing, SupportedUniverseState


class CombinedUniverseLoaderIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.session.add_all(
            [
                Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True),
                Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True),
                Exchange(code="PSE", name="Prague Stock Exchange", is_launch_active=True),
                InstrumentType(code="STOCK", name="Stock", is_launch_active=True),
            ]
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_combined_loader_merges_selected_sources_and_projects_supported_universe(self) -> None:
        source_registry = {
            "NYSE": lambda *_: [
                DiscoveryCandidate(
                    exchange="NYSE",
                    instrument_type="STOCK",
                    symbol="AAPL",
                    name="Apple Inc.",
                    stable_identifiers={"ticker": "AAPL"},
                )
            ],
            "NASDAQ_TRADER": lambda *_: [
                DiscoveryCandidate(
                    exchange="NASDAQ",
                    instrument_type="STOCK",
                    symbol="MSFT",
                    name="Microsoft Corp",
                    stable_identifiers={"ticker": "MSFT"},
                )
            ],
            "YFINANCE": lambda *_: [
                DiscoveryCandidate(
                    exchange="NYSE",
                    instrument_type="STOCK",
                    symbol="AAPL",
                    name="Apple Duplicate",
                    stable_identifiers={"cusip": "037833100"},
                )
            ],
            "OPENFIGI": lambda *_: [
                DiscoveryCandidate(
                    exchange="NYSE",
                    instrument_type="STOCK",
                    symbol="AAPL",
                    name="Apple Inc.",
                    stable_identifiers={"figi": "BBG000B9XRY4"},
                )
            ],
            "AKSHARE": lambda *_: [],
        }

        result = execute_combined_universe_loader(
            self.session,
            source_registry=source_registry,
            effective_day=date(2026, 5, 2),
        )
        self.session.commit()

        symbols = self.session.scalars(select(Listing.symbol).order_by(Listing.symbol.asc())).all()
        supported_listing_ids = self.session.scalars(
            select(SupportedUniverseState.listing_id).order_by(SupportedUniverseState.listing_id.asc())
        ).all()
        identifiers = self.session.scalars(
            select(IdentifierRecord).where(IdentifierRecord.provider_code == "OPENFIGI")
        ).all()

        self.assertEqual(symbols, ["AAPL", "MSFT"])
        self.assertEqual(len(supported_listing_ids), 2)
        self.assertEqual(len(result.selected_listing_ids), 2)
        self.assertEqual(result.projected_supported_listing_count, 2)
        self.assertGreaterEqual(result.persisted_candidate_count, 3)
        self.assertIn("NASDAQ_TRADER", result.selected_sources)
        self.assertIn("NYSE", result.selected_sources)
        self.assertIn("OPENFIGI", result.selected_sources)
        self.assertTrue(any(record.identifier_type == "FIGI" for record in identifiers))


if __name__ == "__main__":
    unittest.main()
