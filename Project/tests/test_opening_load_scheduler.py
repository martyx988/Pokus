from __future__ import annotations

import unittest
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from pokus_backend.calendars.result import TradingDayDecision, TradingDayStatus
from pokus_backend.jobs.opening_load_scheduler import (
    build_opening_load_job_idempotency_key,
    schedule_today_opening_load_jobs,
)


class _FakeCalendarService:
    def __init__(self, statuses_by_exchange: dict[str, TradingDayStatus]) -> None:
        self._statuses_by_exchange = statuses_by_exchange

    def evaluate(self, exchange: str, local_date: date) -> TradingDayDecision:
        status = self._statuses_by_exchange[exchange.upper()]
        return TradingDayDecision(exchange=exchange.upper(), local_date=local_date, status=status)


class OpeningLoadSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = sa.create_engine("sqlite+pysqlite:///:memory:")
        self.metadata = sa.MetaData()
        self.exchange_table = sa.Table(
            "exchange",
            self.metadata,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("code", sa.String(16), unique=True, nullable=False),
            sa.Column("is_launch_active", sa.Boolean, nullable=False),
        )
        self.load_jobs_table = sa.Table(
            "load_jobs",
            self.metadata,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("idempotency_key", sa.Text, nullable=False),
            sa.Column("state", sa.Text, nullable=False),
        )
        self.exchange_day_load_table = sa.Table(
            "exchange_day_load",
            self.metadata,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("exchange_id", sa.Integer, nullable=False),
            sa.Column("job_id", sa.Integer, nullable=True),
            sa.Column("trading_date", sa.Date, nullable=False),
            sa.Column("load_type", sa.String(32), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.UniqueConstraint("exchange_id", "trading_date", "load_type"),
        )
        self.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "CREATE UNIQUE INDEX uq_load_jobs_active_idempotency "
                    "ON load_jobs (idempotency_key) "
                    "WHERE state NOT IN ('succeeded','failed','cancelled')"
                )
            )
        self.session = Session(self.engine)
        self.session.execute(
            self.exchange_table.insert(),
            [
                {"code": "NASDAQ", "is_launch_active": True},
                {"code": "NYSE", "is_launch_active": True},
                {"code": "PSE", "is_launch_active": True},
            ],
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_repeated_runs_deduplicate_enqueue_per_exchange_day(self) -> None:
        trading_date = date(2026, 5, 4)
        service = _FakeCalendarService(
            {
                "NASDAQ": TradingDayStatus.EXPECTED_TRADING_DAY,
                "NYSE": TradingDayStatus.EXPECTED_TRADING_DAY,
                "PSE": TradingDayStatus.EXPECTED_TRADING_DAY,
            }
        )

        first = schedule_today_opening_load_jobs(self.session, today=trading_date, calendar_service=service)
        self.session.commit()
        second = schedule_today_opening_load_jobs(self.session, today=trading_date, calendar_service=service)
        self.session.commit()

        self.assertEqual(first.enqueued_count, 3)
        self.assertEqual(second.enqueued_count, 0)
        self.assertEqual(second.skipped_existing_count, 3)
        job_count = self.session.execute(sa.select(sa.func.count()).select_from(self.load_jobs_table)).scalar_one()
        exchange_day_load_count = self.session.execute(
            sa.select(sa.func.count()).select_from(self.exchange_day_load_table)
        ).scalar_one()
        self.assertEqual(job_count, 3)
        self.assertEqual(exchange_day_load_count, 3)

    def test_market_closed_exchange_is_skipped(self) -> None:
        trading_date = date(2026, 5, 2)
        service = _FakeCalendarService(
            {
                "NASDAQ": TradingDayStatus.MARKET_CLOSED,
                "NYSE": TradingDayStatus.EXPECTED_TRADING_DAY,
                "PSE": TradingDayStatus.MARKET_CLOSED,
            }
        )

        result = schedule_today_opening_load_jobs(self.session, today=trading_date, calendar_service=service)
        self.session.commit()

        self.assertEqual(result.enqueued_count, 1)
        self.assertEqual(result.skipped_market_closed_count, 2)
        rows = self.session.execute(
            sa.select(self.exchange_day_load_table.c.exchange_id, self.exchange_day_load_table.c.load_type)
        ).all()
        self.assertEqual(len(rows), 1)

    def test_idempotency_key_is_deterministic(self) -> None:
        trading_date = date(2026, 5, 4)
        key = build_opening_load_job_idempotency_key(exchange_code="nyse", trading_date=trading_date)

        self.assertEqual(key, "opening-load:NYSE:2026-05-04")


if __name__ == "__main__":
    unittest.main()
