from __future__ import annotations

import datetime as dt
import unittest

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing, SignalEvent, SignalStatistic


class SignalModelsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = sa.create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                Exchange.__table__,
                InstrumentType.__table__,
                Instrument.__table__,
                Listing.__table__,
                SignalEvent.__table__,
                SignalStatistic.__table__,
            ],
        )
        self.session = Session(self.engine)
        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.session.add_all([self.exchange, self.instrument_type])
        self.session.flush()
        self.instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Example Corp.")
        self.session.add(self.instrument)
        self.session.flush()
        self.listing = Listing(instrument_id=self.instrument.id, exchange_id=self.exchange.id, symbol="EXMP")
        self.session.add(self.listing)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_signal_type_constraint_allows_only_dip_and_skyrocket_for_signal_outcome(self) -> None:
        self.session.add(
            SignalEvent(
                instrument_id=self.instrument.id,
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 1),
                algorithm_version="v1",
                signal_outcome="signal",
                signal_type="Dip",
            )
        )
        self.session.add(
            SignalEvent(
                instrument_id=self.instrument.id,
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 2),
                algorithm_version="v1",
                signal_outcome="signal",
                signal_type="Skyrocket",
            )
        )
        self.session.commit()

        self.session.add(
            SignalEvent(
                instrument_id=self.instrument.id,
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 3),
                algorithm_version="v1",
                signal_outcome="signal",
                signal_type="Breakout",
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_outcome_and_signal_type_pairing_distinguishes_signal_no_signal_and_unavailable(self) -> None:
        self.session.add_all(
            [
                SignalEvent(
                    instrument_id=self.instrument.id,
                    listing_id=self.listing.id,
                    trading_date=dt.date(2026, 5, 4),
                    algorithm_version="v1",
                    signal_outcome="signal",
                    signal_type="Dip",
                ),
                SignalEvent(
                    instrument_id=self.instrument.id,
                    listing_id=self.listing.id,
                    trading_date=dt.date(2026, 5, 5),
                    algorithm_version="v1",
                    signal_outcome="no_signal",
                    signal_type=None,
                ),
                SignalEvent(
                    instrument_id=self.instrument.id,
                    listing_id=self.listing.id,
                    trading_date=dt.date(2026, 5, 6),
                    algorithm_version="v1",
                    signal_outcome="insufficient_history",
                    signal_type=None,
                ),
            ]
        )
        self.session.commit()

        self.session.add(
            SignalEvent(
                instrument_id=self.instrument.id,
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 7),
                algorithm_version="v1",
                signal_outcome="no_signal",
                signal_type="Dip",
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_duplicate_signal_type_for_same_listing_date_and_algorithm_is_rejected(self) -> None:
        self.session.add(
            SignalEvent(
                instrument_id=self.instrument.id,
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 8),
                algorithm_version="v1",
                signal_outcome="signal",
                signal_type="Skyrocket",
            )
        )
        self.session.commit()

        self.session.add(
            SignalEvent(
                instrument_id=self.instrument.id,
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 8),
                algorithm_version="v1",
                signal_outcome="signal",
                signal_type="Skyrocket",
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_signal_statistic_stores_provenance_context_and_requires_unique_name_per_listing_date_and_algorithm(self) -> None:
        self.session.add(
            SignalStatistic(
                instrument_id=self.instrument.id,
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 1),
                algorithm_version="v1",
                statistic_name="z_score",
                statistic_value=1.2345,
                context={"lookback_days": 30, "volatility": 0.18},
            )
        )
        self.session.commit()

        stored = self.session.query(SignalStatistic).one()
        self.assertEqual(stored.algorithm_version, "v1")
        self.assertEqual(stored.context, {"lookback_days": 30, "volatility": 0.18})

        self.session.add(
            SignalStatistic(
                instrument_id=self.instrument.id,
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 1),
                algorithm_version="v1",
                statistic_name="z_score",
                statistic_value=2.0,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()


if __name__ == "__main__":
    unittest.main()
