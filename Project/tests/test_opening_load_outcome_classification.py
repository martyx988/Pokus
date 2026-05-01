from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad
from pokus_backend.jobs.opening_load_outcomes import (
    OpeningLoadOutcomeInput,
    classify_opening_load_outcome,
    upsert_opening_load_outcome,
)


class OpeningLoadOutcomeClassificationTests(unittest.TestCase):
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
            ],
        )
        self.session = Session(self.engine)

        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.session.add_all([self.exchange, self.instrument_type])
        self.session.flush()

        self.instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Example Corp")
        self.session.add(self.instrument)
        self.session.flush()

        self.listing = Listing(instrument_id=self.instrument.id, exchange_id=self.exchange.id, symbol="EXMP")
        self.session.add(self.listing)
        self.session.flush()

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
            sa.Table(
                "load_jobs",
                metadata,
                sa.Column("id", sa.BigInteger(), primary_key=True),
            )

    def test_classifies_all_required_m4_outcome_classes(self) -> None:
        cases = [
            (OpeningLoadOutcomeInput(has_selected_price=True), "succeeded", "success", True),
            (OpeningLoadOutcomeInput(has_selected_price=False, missing=True), "failed", "missing", True),
            (OpeningLoadOutcomeInput(has_selected_price=False, stale=True), "failed", "stale", True),
            (OpeningLoadOutcomeInput(has_selected_price=False, halted=True), "pending", "halted", False),
            (OpeningLoadOutcomeInput(has_selected_price=False, suspended=True), "pending", "suspended", False),
            (OpeningLoadOutcomeInput(has_selected_price=False, late_open=True), "pending", "late_open", False),
            (OpeningLoadOutcomeInput(has_selected_price=False, provider_failed=True), "failed", "provider_failed", True),
        ]

        for payload, expected_outcome, expected_class, expected_terminal in cases:
            with self.subTest(payload=payload):
                classified = classify_opening_load_outcome(payload)
                self.assertEqual(classified.outcome, expected_outcome)
                self.assertEqual(classified.outcome_class, expected_class)
                self.assertEqual(classified.is_terminal, expected_terminal)

    def test_upsert_is_stable_for_reruns_of_same_exchange_day_listing(self) -> None:
        first = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=False, provider_failed=True))
        row = upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=self.listing.id,
            job_id=None,
            classification=first,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        )
        self.session.commit()

        second = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True))
        row = upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=self.listing.id,
            job_id=None,
            classification=second,
            occurred_at=datetime(2026, 5, 1, 14, 5, tzinfo=timezone.utc),
        )
        self.session.commit()

        rows = self.session.execute(sa.text("SELECT id, outcome, outcome_class, is_terminal FROM instrument_load_outcome")).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, row.id)
        self.assertEqual(rows[0].outcome, "succeeded")
        self.assertEqual(rows[0].outcome_class, "success")
        self.assertEqual(rows[0].is_terminal, 1)


if __name__ == "__main__":
    unittest.main()
