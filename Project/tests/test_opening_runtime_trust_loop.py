from __future__ import annotations

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.discovery.app_current_day_prices import fetch_current_app_exchange_current_day_prices
from pokus_backend.discovery.app_exchange_readiness import fetch_app_exchange_readiness
from pokus_backend.domain import Base, Instrument, Listing, PriceRecord, SupportedUniverseState, SupportedUniverseStatus
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad, InstrumentLoadOutcome
from pokus_backend.domain.publication_models import PublicationRecord
from pokus_backend.domain.reference_models import Exchange, InstrumentType
from pokus_backend.jobs.opening_runtime_trust_loop import execute_opening_runtime_trust_loop


class OpeningRuntimeTrustLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "trust-loop.sqlite3"
        self.db_url = f"sqlite+pysqlite:///{self.db_path.as_posix()}"
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.tmp_dir.cleanup()

    def test_executes_opening_runtime_loop_and_populates_read_models(self) -> None:
        trading_date = date(2026, 5, 1)
        with Session(self.engine) as session:
            nyse = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
            stock = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
            session.add_all([nyse, stock])
            session.flush()
            instrument = Instrument(instrument_type_id=stock.id, canonical_name="Trust Loop Local")
            session.add(instrument)
            session.flush()
            listing = Listing(instrument_id=instrument.id, exchange_id=nyse.id, symbol="TLCL")
            session.add(listing)
            session.flush()
            session.add(SupportedUniverseState(listing_id=listing.id, status=SupportedUniverseStatus.SUPPORTED))
            session.add(
                PriceRecord(
                    listing_id=listing.id,
                    trading_date=trading_date,
                    price_type="current_day_unadjusted_open",
                    value=Decimal("100.25"),
                    currency="USD",
                )
            )
            session.add(
                ExchangeDayLoad(
                    exchange_id=nyse.id,
                    job_id=None,
                    trading_date=trading_date,
                    load_type="daily_open",
                    status="not_started",
                )
            )

            result = execute_opening_runtime_trust_loop(
                session,
                trading_date=trading_date,
                exchange_codes=["NYSE"],
                schedule_missing_loads=False,
            )
            session.commit()
            self.assertEqual(result.processed_load_count, 1)
            self.assertEqual(result.ready_count, 1)

            load = session.scalar(select(ExchangeDayLoad))
            self.assertIsNotNone(load)
            self.assertEqual(load.status, "ready")

            outcome = session.scalar(select(InstrumentLoadOutcome))
            self.assertIsNotNone(outcome)
            self.assertEqual(outcome.outcome, "succeeded")

            publication = session.scalar(select(PublicationRecord))
            self.assertIsNotNone(publication)
            self.assertEqual(publication.status, "ready")

        readiness_items = fetch_app_exchange_readiness(self.db_url, exchange_codes=("NYSE",))
        self.assertEqual(len(readiness_items), 1)
        self.assertEqual(readiness_items[0].readiness_state, "ready")
        self.assertTrue(readiness_items[0].publication_available)

        prices = fetch_current_app_exchange_current_day_prices(self.db_url, exchange_code="NYSE")
        self.assertIsNotNone(prices)
        assert prices is not None
        self.assertEqual(prices.exchange, "NYSE")
        self.assertEqual(len(prices.current_day_prices), 1)
        self.assertEqual(prices.current_day_prices[0].symbol, "TLCL")
