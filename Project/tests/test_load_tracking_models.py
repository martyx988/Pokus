from __future__ import annotations

import unittest
from datetime import date

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.domain.instrument_models import Instrument, Listing
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad, InstrumentLoadOutcome
from pokus_backend.domain.reference_models import Base, Exchange, InstrumentType


class LoadTrackingModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = sa.create_engine("sqlite+pysqlite:///:memory:")
        self._create_dependency_tables()
        Base.metadata.create_all(
            self.engine,
            tables=[
                Base.metadata.tables["load_jobs"],
                InstrumentType.__table__,
                Instrument.__table__,
                Listing.__table__,
                Exchange.__table__,
                ExchangeDayLoad.__table__,
                InstrumentLoadOutcome.__table__,
            ],
        )
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _create_dependency_tables(self) -> None:
        metadata = Base.metadata
        if "load_jobs" not in metadata.tables:
            sa.Table(
                "load_jobs",
                metadata,
                sa.Column("id", sa.BigInteger(), primary_key=True),
            )
    def _seed_dependencies(self) -> tuple[int, int, int]:
        self.session.add(InstrumentType(code="STOCK", name="Stock", is_launch_active=True))
        self.session.add(Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True))
        self.session.flush()
        instrument_type_id = self.session.execute(select(InstrumentType.id)).scalar_one()
        exchange_id = self.session.execute(select(Exchange.id)).scalar_one()
        instrument = Instrument(instrument_type_id=instrument_type_id, canonical_name="Example Corp", is_active=True)
        self.session.add(instrument)
        self.session.flush()
        listing = Listing(instrument_id=instrument.id, exchange_id=exchange_id, symbol="EXMPL")
        self.session.add(listing)
        self.session.flush()
        self.session.execute(sa.text("INSERT INTO load_jobs (id) VALUES (1)"))
        self.session.flush()
        return exchange_id, 1, listing.id

    def test_valid_load_types_and_statuses_are_accepted(self) -> None:
        exchange_id, job_id, _ = self._seed_dependencies()
        valid_statuses = [
            "not_started",
            "in_progress",
            "market_closed",
            "partial_problematic",
            "ready",
            "failed",
        ]
        for idx, status in enumerate(valid_statuses):
            self.session.add(
                ExchangeDayLoad(
                    exchange_id=exchange_id,
                    job_id=job_id,
                    trading_date=date(2026, 5, idx + 1),
                    load_type="daily_open" if idx % 2 == 0 else "historical_close",
                    status=status,
                    eligible_instrument_count=10,
                    succeeded_count=8,
                    failed_count=2,
                )
            )
        self.session.commit()
        self.assertEqual(self.session.query(ExchangeDayLoad).count(), len(valid_statuses))

    def test_invalid_load_type_is_rejected(self) -> None:
        exchange_id, _, _ = self._seed_dependencies()
        self.session.add(
            ExchangeDayLoad(
                exchange_id=exchange_id,
                trading_date=date(2026, 5, 2),
                load_type="intraday",
                status="not_started",
                eligible_instrument_count=1,
                succeeded_count=0,
                failed_count=0,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_invalid_status_is_rejected(self) -> None:
        exchange_id, _, _ = self._seed_dependencies()
        self.session.add(
            ExchangeDayLoad(
                exchange_id=exchange_id,
                trading_date=date(2026, 5, 3),
                load_type="daily_open",
                status="completed",
                eligible_instrument_count=1,
                succeeded_count=1,
                failed_count=0,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_outcome_uniqueness_prevents_duplicate_listing_per_exchange_day_load(self) -> None:
        exchange_id, job_id, listing_id = self._seed_dependencies()
        exchange_day_load = ExchangeDayLoad(
            exchange_id=exchange_id,
            job_id=job_id,
            trading_date=date(2026, 5, 4),
            load_type="daily_open",
            status="in_progress",
            eligible_instrument_count=2,
            succeeded_count=0,
            failed_count=0,
        )
        self.session.add(exchange_day_load)
        self.session.flush()

        self.session.add(
            InstrumentLoadOutcome(
                exchange_day_load_id=exchange_day_load.id,
                listing_id=listing_id,
                job_id=job_id,
                outcome="pending",
            )
        )
        self.session.flush()
        self.session.add(
            InstrumentLoadOutcome(
                exchange_day_load_id=exchange_day_load.id,
                listing_id=listing_id,
                job_id=job_id,
                outcome="failed",
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_valid_outcomes_are_accepted(self) -> None:
        exchange_id, job_id, listing_id = self._seed_dependencies()
        instrument_type_id = self.session.execute(select(InstrumentType.id)).scalar_one()
        exchange_day_load = ExchangeDayLoad(
            exchange_id=exchange_id,
            job_id=job_id,
            trading_date=date(2026, 5, 5),
            load_type="historical_close",
            status="in_progress",
            eligible_instrument_count=5,
            succeeded_count=1,
            failed_count=0,
        )
        self.session.add(exchange_day_load)
        self.session.flush()

        for idx, outcome in enumerate(["pending", "in_progress", "succeeded", "failed", "cancelled"]):
            if idx > 0:
                instrument = Instrument(
                    instrument_type_id=instrument_type_id,
                    canonical_name=f"Example Corp {idx}",
                    is_active=True,
                )
                self.session.add(instrument)
                self.session.flush()
                listing = Listing(
                    instrument_id=instrument.id,
                    exchange_id=exchange_id,
                    symbol=f"EXM{idx}",
                )
                self.session.add(listing)
                self.session.flush()
                current_listing_id = listing.id
            else:
                current_listing_id = listing_id
            self.session.add(
                InstrumentLoadOutcome(
                    exchange_day_load_id=exchange_day_load.id,
                    listing_id=current_listing_id,
                    job_id=job_id,
                    outcome=outcome,
                )
            )
        self.session.commit()
        self.assertEqual(self.session.query(InstrumentLoadOutcome).count(), 5)


if __name__ == "__main__":
    unittest.main()
