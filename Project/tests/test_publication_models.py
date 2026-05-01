from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.domain.load_tracking_models import ExchangeDayLoad
from pokus_backend.domain.publication_models import PublicationRecord, QualityCheck
from pokus_backend.domain.reference_models import Base, Exchange


class PublicationModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = sa.create_engine("sqlite+pysqlite:///:memory:")
        self._create_dependency_tables()
        Base.metadata.create_all(
            self.engine,
            tables=[
                Base.metadata.tables["load_jobs"],
                Exchange.__table__,
                ExchangeDayLoad.__table__,
                PublicationRecord.__table__,
                QualityCheck.__table__,
            ],
        )
        self.session = Session(self.engine)
        self.exchange = Exchange(code="XNYS", name="NYSE", is_launch_active=True)
        self.session.add(self.exchange)
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

    def _create_exchange_day_load(self, trading_date: date, load_type: str) -> ExchangeDayLoad:
        load = ExchangeDayLoad(
            exchange_id=self.exchange.id,
            job_id=1,
            trading_date=trading_date,
            load_type=load_type,
            status="ready",
            eligible_instrument_count=100,
            succeeded_count=100,
            failed_count=0,
        )
        self.session.add(load)
        self.session.flush()
        return load

    def test_publication_status_values_are_enforced(self) -> None:
        valid_statuses = ["unpublished", "ready", "blocked", "failed", "market_closed", "published"]
        for idx, status in enumerate(valid_statuses):
            load = self._create_exchange_day_load(
                trading_date=date(2026, 5, idx + 1),
                load_type="daily_open" if idx % 2 == 0 else "historical_close",
            )
            self.session.add(PublicationRecord(exchange_day_load_id=load.id, status=status))
        self.session.commit()
        self.assertEqual(self.session.query(PublicationRecord).count(), len(valid_statuses))

        load = self._create_exchange_day_load(date(2026, 5, 10), "daily_open")
        self.session.add(PublicationRecord(exchange_day_load_id=load.id, status="done"))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_publication_and_quality_are_unique_per_exchange_day_load(self) -> None:
        load = self._create_exchange_day_load(date(2026, 5, 20), "daily_open")
        self.session.add(PublicationRecord(exchange_day_load_id=load.id, status="unpublished"))
        self.session.add(
            QualityCheck(
                exchange_day_load_id=load.id,
                eligible_count=100,
                succeeded_count=100,
                failed_count=0,
                coverage_percent=100.0,
                correctness_result="passed",
                benchmark_mismatch_percent=0.2,
                benchmark_mismatch_summary="No material mismatches",
                checked_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )
        )
        self.session.commit()

        self.session.add(PublicationRecord(exchange_day_load_id=load.id, status="ready"))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

        self.session.add(
            QualityCheck(
                exchange_day_load_id=load.id,
                eligible_count=100,
                succeeded_count=99,
                failed_count=1,
                coverage_percent=99.0,
                correctness_result="failed",
                checked_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_quality_fields_and_constraints_are_enforced(self) -> None:
        load = self._create_exchange_day_load(date(2026, 5, 25), "daily_open")
        self.session.add(
            QualityCheck(
                exchange_day_load_id=load.id,
                eligible_count=100,
                succeeded_count=99,
                failed_count=1,
                coverage_percent=99.0,
                correctness_result="passed",
                benchmark_mismatch_percent=0.4,
                benchmark_mismatch_summary="2 outliers above threshold",
                checked_at=datetime(2026, 5, 25, tzinfo=timezone.utc),
            )
        )
        self.session.commit()

        load_invalid_coverage = self._create_exchange_day_load(date(2026, 5, 26), "historical_close")
        self.session.add(
            QualityCheck(
                exchange_day_load_id=load_invalid_coverage.id,
                eligible_count=100,
                succeeded_count=99,
                failed_count=1,
                coverage_percent=101.0,
                correctness_result="passed",
                checked_at=datetime(2026, 5, 26, tzinfo=timezone.utc),
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

        load_invalid_result = self._create_exchange_day_load(date(2026, 5, 27), "daily_open")
        self.session.add(
            QualityCheck(
                exchange_day_load_id=load_invalid_result.id,
                eligible_count=100,
                succeeded_count=99,
                failed_count=1,
                coverage_percent=99.0,
                correctness_result="unknown",
                checked_at=datetime(2026, 5, 27, tzinfo=timezone.utc),
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()


if __name__ == "__main__":
    unittest.main()
