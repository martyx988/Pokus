from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.discovery.exchange_priority import recompute_exchange_activity_priority
from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing, PriceRecord


class ExchangePriorityRecomputeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "priority.db"
        self.database_url = f"sqlite+pysqlite:///{self.db_path.as_posix()}"
        self.engine = sa.create_engine(self.database_url)
        Base.metadata.create_all(
            self.engine,
            tables=[
                Exchange.__table__,
                InstrumentType.__table__,
                Instrument.__table__,
                Listing.__table__,
                PriceRecord.__table__,
            ],
        )

    def tearDown(self) -> None:
        self.engine.dispose()
        self._tmpdir.cleanup()

    def test_recompute_orders_exchanges_by_trailing_average_and_normalizes_scores(self) -> None:
        with Session(self.engine) as session:
            nyse = Exchange(code="NYSE", name="NYSE", is_launch_active=True)
            nasdaq = Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True)
            session.add_all([nyse, nasdaq, InstrumentType(code="STOCK", name="Stock", is_launch_active=True)])
            session.flush()

            instrument_type_id = session.scalar(select(InstrumentType.id).where(InstrumentType.code == "STOCK"))
            assert instrument_type_id is not None

            nyse_listing = self._create_listing(session, instrument_type_id, nyse.id, "NYS")
            nasdaq_listing = self._create_listing(session, instrument_type_id, nasdaq.id, "NAS")

            for i in range(65):
                day = dt.date(2026, 1, 1) + dt.timedelta(days=i)
                session.add(
                    PriceRecord(
                        listing_id=nyse_listing.id,
                        trading_date=day,
                        price_type="historical_adjusted_close",
                        value=100,
                        currency="USD",
                    )
                )
                session.add(
                    PriceRecord(
                        listing_id=nasdaq_listing.id,
                        trading_date=day,
                        price_type="historical_adjusted_close",
                        value=200,
                        currency="USD",
                    )
                )
            session.commit()

        updated = recompute_exchange_activity_priority(self.database_url)
        self.assertEqual(updated, 2)

        with Session(self.engine) as session:
            exchanges = session.scalars(select(Exchange).order_by(Exchange.code.asc())).all()
            by_code = {row.code: row for row in exchanges}
            self.assertEqual(by_code["NASDAQ"].activity_priority_rank, 1)
            self.assertEqual(by_code["NYSE"].activity_priority_rank, 2)
            self.assertAlmostEqual(by_code["NASDAQ"].activity_priority_score, 1.0)
            self.assertAlmostEqual(by_code["NYSE"].activity_priority_score, 0.5)

    def test_recompute_is_repeatable_without_inconsistent_duplicates(self) -> None:
        with Session(self.engine) as session:
            exchange = Exchange(code="PSE", name="PSE", is_launch_active=True)
            session.add_all([exchange, InstrumentType(code="STOCK", name="Stock", is_launch_active=True)])
            session.flush()
            instrument_type_id = session.scalar(select(InstrumentType.id).where(InstrumentType.code == "STOCK"))
            assert instrument_type_id is not None
            listing = self._create_listing(session, instrument_type_id, exchange.id, "PSE1")

            for i in range(70):
                day = dt.date(2026, 1, 1) + dt.timedelta(days=i)
                session.add(
                    PriceRecord(
                        listing_id=listing.id,
                        trading_date=day,
                        price_type="historical_adjusted_close",
                        value=50,
                        currency="CZK",
                    )
                )
            session.commit()

        first = recompute_exchange_activity_priority(self.database_url)
        second = recompute_exchange_activity_priority(self.database_url)
        self.assertEqual(first, 1)
        self.assertEqual(second, 1)

        with Session(self.engine) as session:
            stored = session.scalar(select(Exchange).where(Exchange.code == "PSE"))
            assert stored is not None
            self.assertEqual(stored.activity_priority_rank, 1)
            self.assertAlmostEqual(stored.activity_priority_score, 1.0)

    def _create_listing(self, session: Session, instrument_type_id: int, exchange_id: int, symbol: str) -> Listing:
        instrument = Instrument(instrument_type_id=instrument_type_id, canonical_name=f"Instrument {symbol}")
        session.add(instrument)
        session.flush()
        listing = Listing(instrument_id=instrument.id, exchange_id=exchange_id, symbol=symbol)
        session.add(listing)
        session.flush()
        return listing


if __name__ == "__main__":
    unittest.main()
