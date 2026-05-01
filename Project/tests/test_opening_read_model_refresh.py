from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing, PriceRecord
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad
from pokus_backend.domain.publication_models import QualityCheck
from pokus_backend.jobs.opening_load_outcomes import (
    OpeningLoadOutcomeInput,
    classify_opening_load_outcome,
    decide_and_persist_opening_publication_status,
    evaluate_and_persist_opening_correctness_validation,
    upsert_opening_load_outcome,
)
from pokus_backend.jobs.opening_read_model_refresh import (
    get_current_day_price_read_model,
    get_readiness_read_model,
    refresh_publication_read_models,
)


class OpeningReadModelRefreshTests(unittest.TestCase):
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
                Base.metadata.tables["instrument_load_outcome"],
                Base.metadata.tables["publication_record"],
                QualityCheck.__table__,
                PriceRecord.__table__,
            ],
        )
        self.session = Session(self.engine)
        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.session.add_all([self.exchange, self.instrument_type])
        self.session.flush()
        self.listing = self._create_listing(symbol="EXMP")
        self.exchange_day_load = ExchangeDayLoad(
            exchange_id=self.exchange.id,
            job_id=1,
            trading_date=date(2026, 5, 1),
            load_type="daily_open",
            status="in_progress",
            eligible_instrument_count=1,
            succeeded_count=0,
            failed_count=0,
        )
        self.session.add(self.exchange_day_load)
        self.session.execute(sa.text("INSERT INTO load_jobs (id) VALUES (1)"))
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _create_dependency_tables(self) -> None:
        metadata = Base.metadata
        if "load_jobs" not in metadata.tables:
            sa.Table("load_jobs", metadata, sa.Column("id", sa.BigInteger(), primary_key=True))

    def _create_listing(self, *, symbol: str) -> Listing:
        instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name=f"{symbol} Corp")
        self.session.add(instrument)
        self.session.flush()
        listing = Listing(instrument_id=instrument.id, exchange_id=self.exchange.id, symbol=symbol)
        self.session.add(listing)
        self.session.flush()
        return listing

    def test_refresh_keeps_current_day_prices_unavailable_when_publication_is_blocked(self) -> None:
        decide_and_persist_opening_publication_status(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            decided_at=datetime(2026, 5, 1, 15, 0, tzinfo=timezone.utc),
        )
        self.session.commit()

        readiness = get_readiness_read_model(exchange_day_load_id=self.exchange_day_load.id)
        prices = get_current_day_price_read_model(exchange_day_load_id=self.exchange_day_load.id)
        self.assertIsNotNone(readiness)
        self.assertFalse(readiness.is_ready)
        self.assertEqual(readiness.publication_status, "blocked")
        self.assertEqual(prices, ())

    def test_refresh_exposes_current_day_prices_only_when_publication_is_ready(self) -> None:
        classification = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True))
        upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=self.listing.id,
            job_id=None,
            classification=classification,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        )
        self.session.add(
            PriceRecord(
                listing_id=self.listing.id,
                trading_date=date(2026, 5, 1),
                price_type="current_day_unadjusted_open",
                value=Decimal("123.45"),
                currency="USD",
            )
        )
        evaluate_and_persist_opening_correctness_validation(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            benchmark_compared_count=10,
            benchmark_mismatch_count=0,
        )
        decide_and_persist_opening_publication_status(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            decided_at=datetime(2026, 5, 1, 15, 0, tzinfo=timezone.utc),
        )
        self.session.commit()

        readiness = get_readiness_read_model(exchange_day_load_id=self.exchange_day_load.id)
        prices = get_current_day_price_read_model(exchange_day_load_id=self.exchange_day_load.id)
        self.assertIsNotNone(readiness)
        self.assertTrue(readiness.is_ready)
        self.assertEqual(readiness.publication_status, "ready")
        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0].symbol, "EXMP")
        self.assertEqual(prices[0].value, Decimal("123.45000000"))

    def test_refresh_is_idempotent_for_reruns(self) -> None:
        classification = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True))
        upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=self.listing.id,
            job_id=None,
            classification=classification,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        )
        self.session.add(
            PriceRecord(
                listing_id=self.listing.id,
                trading_date=date(2026, 5, 1),
                price_type="current_day_unadjusted_open",
                value=Decimal("120"),
                currency="USD",
            )
        )
        evaluate_and_persist_opening_correctness_validation(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            benchmark_compared_count=10,
            benchmark_mismatch_count=0,
        )
        decide_and_persist_opening_publication_status(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            decided_at=datetime(2026, 5, 1, 15, 0, tzinfo=timezone.utc),
        )
        self.session.commit()

        first_readiness, first_prices = refresh_publication_read_models(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
        )
        second_readiness, second_prices = refresh_publication_read_models(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
        )

        self.assertEqual(first_readiness, second_readiness)
        self.assertEqual(first_prices, second_prices)
        self.assertEqual(len(second_prices), 1)


if __name__ == "__main__":
    unittest.main()
