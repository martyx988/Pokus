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
    compute_publication_terminal_coverage_precheck,
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

    def test_aggregate_state_transitions_and_counters_for_mixed_outcomes(self) -> None:
        second_instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Second Corp")
        self.session.add(second_instrument)
        self.session.flush()
        second_listing = Listing(instrument_id=second_instrument.id, exchange_id=self.exchange.id, symbol="EXMP2")
        self.session.add(second_listing)
        self.session.flush()

        self.exchange_day_load.eligible_instrument_count = 2
        self.session.commit()

        first_outcome = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True))
        upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=self.listing.id,
            job_id=None,
            classification=first_outcome,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        )
        self.session.commit()
        self.session.refresh(self.exchange_day_load)

        self.assertEqual(self.exchange_day_load.status, "in_progress")
        self.assertEqual(self.exchange_day_load.succeeded_count, 1)
        self.assertEqual(self.exchange_day_load.failed_count, 0)
        self.assertEqual(self.exchange_day_load.started_at, datetime(2026, 5, 1, 14, 0))
        self.assertIsNone(self.exchange_day_load.completed_at)
        self.assertIsNone(self.exchange_day_load.duration_seconds)

        second_outcome = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=False, stale=True))
        upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=second_listing.id,
            job_id=None,
            classification=second_outcome,
            occurred_at=datetime(2026, 5, 1, 14, 3, tzinfo=timezone.utc),
        )
        self.session.commit()
        self.session.refresh(self.exchange_day_load)

        self.assertEqual(self.exchange_day_load.status, "partial_problematic")
        self.assertEqual(self.exchange_day_load.succeeded_count, 1)
        self.assertEqual(self.exchange_day_load.failed_count, 1)
        self.assertEqual(self.exchange_day_load.started_at, datetime(2026, 5, 1, 14, 0))
        self.assertEqual(self.exchange_day_load.completed_at, datetime(2026, 5, 1, 14, 3))
        self.assertEqual(self.exchange_day_load.duration_seconds, 180)

    def test_aggregate_transitions_back_to_in_progress_when_terminal_outcome_becomes_pending(self) -> None:
        first = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=False, stale=True))
        upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=self.listing.id,
            job_id=None,
            classification=first,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        )
        self.session.commit()
        self.session.refresh(self.exchange_day_load)

        self.assertEqual(self.exchange_day_load.status, "failed")
        self.assertEqual(self.exchange_day_load.failed_count, 1)
        self.assertIsNotNone(self.exchange_day_load.completed_at)

        second = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=False, halted=True))
        upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=self.listing.id,
            job_id=None,
            classification=second,
            occurred_at=datetime(2026, 5, 1, 14, 5, tzinfo=timezone.utc),
        )
        self.session.commit()
        self.session.refresh(self.exchange_day_load)

        self.assertEqual(self.exchange_day_load.status, "in_progress")
        self.assertEqual(self.exchange_day_load.succeeded_count, 0)
        self.assertEqual(self.exchange_day_load.failed_count, 0)
        self.assertEqual(self.exchange_day_load.started_at, datetime(2026, 5, 1, 14, 0))
        self.assertIsNone(self.exchange_day_load.completed_at)
        self.assertIsNone(self.exchange_day_load.duration_seconds)

    def test_publication_precheck_passes_with_100_percent_coverage(self) -> None:
        result = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True))
        upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=self.listing.id,
            job_id=None,
            classification=result,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        )
        self.session.commit()

        precheck = compute_publication_terminal_coverage_precheck(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
        )
        self.assertEqual(precheck.eligible_count, 1)
        self.assertEqual(precheck.terminal_outcome_count, 1)
        self.assertEqual(precheck.covered_count, 1)
        self.assertEqual(precheck.coverage_percent, 100.0)
        self.assertTrue(precheck.has_all_terminal_outcomes)
        self.assertTrue(precheck.has_gt_99_coverage)

    def test_publication_precheck_passes_when_coverage_is_above_99(self) -> None:
        self._seed_precheck_population(total=200, succeeded=199, failed=1)

        precheck = compute_publication_terminal_coverage_precheck(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
        )

        self.assertEqual(precheck.covered_count, 199)
        self.assertEqual(precheck.coverage_percent, 99.5)
        self.assertTrue(precheck.has_gt_99_coverage)

    def test_publication_precheck_blocks_when_any_eligible_outcome_is_non_terminal(self) -> None:
        second_listing = self._create_listing_for_symbol("WAIT1")
        self.exchange_day_load.eligible_instrument_count = 2
        self.session.commit()

        terminal = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True))
        pending = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=False, halted=True))
        upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=self.listing.id,
            job_id=None,
            classification=terminal,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        )
        upsert_opening_load_outcome(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
            listing_id=second_listing.id,
            job_id=None,
            classification=pending,
            occurred_at=datetime(2026, 5, 1, 14, 1, tzinfo=timezone.utc),
        )
        self.session.commit()

        precheck = compute_publication_terminal_coverage_precheck(
            self.session,
            exchange_day_load_id=self.exchange_day_load.id,
        )

        self.assertEqual(precheck.terminal_outcome_count, 1)
        self.assertFalse(precheck.has_all_terminal_outcomes)
        self.assertEqual(precheck.coverage_percent, 50.0)
        self.assertFalse(precheck.has_gt_99_coverage)

    def _seed_precheck_population(self, *, total: int, succeeded: int, failed: int) -> None:
        self.assertEqual(succeeded + failed, total)
        self.exchange_day_load.eligible_instrument_count = total
        self.session.commit()

        listing_ids = [self.listing.id]
        for index in range(total - 1):
            listing = self._create_listing_for_symbol(f"T{index:03d}")
            listing_ids.append(listing.id)

        for index, listing_id in enumerate(listing_ids):
            is_succeeded = index < succeeded
            payload = OpeningLoadOutcomeInput(has_selected_price=is_succeeded, stale=not is_succeeded)
            classification = classify_opening_load_outcome(payload)
            upsert_opening_load_outcome(
                self.session,
                exchange_day_load_id=self.exchange_day_load.id,
                listing_id=listing_id,
                job_id=None,
                classification=classification,
                occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
            )
        self.session.commit()

    def _create_listing_for_symbol(self, symbol: str) -> Listing:
        instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name=f"{symbol} Corp")
        self.session.add(instrument)
        self.session.flush()
        listing = Listing(instrument_id=instrument.id, exchange_id=self.exchange.id, symbol=symbol)
        self.session.add(listing)
        self.session.flush()
        return listing


if __name__ == "__main__":
    unittest.main()
