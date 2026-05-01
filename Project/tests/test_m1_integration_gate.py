from __future__ import annotations

import os
import subprocess
import sys
import unittest
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

import psycopg

from pokus_backend.calendars.result import TradingDayDecision, TradingDayStatus
from pokus_backend.calendars.service import ExchangeCalendarService
from pokus_backend.jobs.load_job import LoadJobState, TERMINAL_LOAD_JOB_STATES
from pokus_backend.jobs.state_transitions import InvalidLoadJobTransition, transition_load_job_state
from pokus_backend.observability.health import collect_platform_health
from pokus_backend.observability.logging import log_admin_command_event, log_job_event


ROOT = Path(__file__).resolve().parents[1]
TEST_DB_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")

@unittest.skipUnless(TEST_DB_URL, "Set TEST_DATABASE_URL or DATABASE_URL for T17 integration gate tests.")
class Milestone1IntegrationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = f"t17_{uuid.uuid4().hex[:12]}"
        self.schema_options = f"-c search_path={self.schema}"
        self.schema_database_url = f"{TEST_DB_URL}?options={quote(self.schema_options, safe='')}"
        with psycopg.connect(TEST_DB_URL, connect_timeout=5, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f'CREATE SCHEMA "{self.schema}"')

    def tearDown(self) -> None:
        with psycopg.connect(TEST_DB_URL, connect_timeout=5, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE')

    def _run_module(self, module: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env["DATABASE_URL"] = self.schema_database_url
        env["PGOPTIONS"] = self.schema_options
        return subprocess.run(
            [sys.executable, "-m", module, *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def test_m1_platform_foundation_integration_gate(self) -> None:
        migrated = self._run_module("pokus_backend.db", "--migrate")
        self.assertEqual(migrated.returncode, 0, msg=migrated.stderr)

        api_check = self._run_module("pokus_backend.api", "--check")
        worker_check = self._run_module("pokus_backend.worker", "--check")
        self.assertEqual(api_check.returncode, 0, msg=api_check.stderr)
        self.assertEqual(worker_check.returncode, 0, msg=worker_check.stderr)

        worker_tick = self._run_module("pokus_backend.worker", "--once")
        self.assertEqual(worker_tick.returncode, 0, msg=worker_tick.stderr)

        with psycopg.connect(TEST_DB_URL, connect_timeout=5, autocommit=True, options=self.schema_options) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema IN (%s, 'public')
                    """,
                    (self.schema,),
                )
                tables = {row[0] for row in cur.fetchall()}

                expected = {
                    "exchange_day_load",
                    "instrument_load_outcome",
                    "provider_attempt",
                    "price_record",
                    "publication_record",
                    "signal_event",
                    "universe_change_record",
                }
                self.assertTrue(expected.issubset(tables), msg=f"missing tables: {expected - tables}")

                cur.execute(
                    """
                    INSERT INTO load_jobs (idempotency_key, state)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (f"m1-gate-job-{uuid.uuid4().hex[:8]}", LoadJobState.QUEUED.value),
                )
                job_id = cur.fetchone()[0]
                self.assertEqual(
                    transition_load_job_state(LoadJobState.QUEUED, LoadJobState.RUNNING),
                    LoadJobState.RUNNING,
                )
                with self.assertRaises(InvalidLoadJobTransition):
                    transition_load_job_state(LoadJobState.SUCCEEDED, LoadJobState.RUNNING)
                self.assertSetEqual(
                    {s.value for s in TERMINAL_LOAD_JOB_STATES},
                    {"succeeded", "failed", "cancelled"},
                )
                with self.assertRaises(psycopg.Error):
                    cur.execute(
                        "INSERT INTO load_jobs (idempotency_key, state) VALUES (%s, %s)",
                        ("bad-job-state", "not_a_state"),
                    )

        class _FakeCalendar:
            calendar_id = "XNYS"

            def is_trading_day(self, local_date: date) -> bool:
                return local_date.weekday() < 5

        class _FakeProvider:
            def get_calendar(self, exchange: str) -> _FakeCalendar | None:
                if exchange.upper() == "NYSE":
                    return _FakeCalendar()
                return None

        calendar = ExchangeCalendarService(provider=_FakeProvider())
        schedule = calendar.evaluate("nyse", date(2026, 1, 5))
        self.assertIsInstance(schedule, TradingDayDecision)
        self.assertEqual(schedule.status, TradingDayStatus.EXPECTED_TRADING_DAY)

        prior_pgoptions = os.environ.get("PGOPTIONS")
        os.environ["PGOPTIONS"] = self.schema_options
        try:
            health = collect_platform_health(TEST_DB_URL or "", 30.0, 60.0)
        finally:
            if prior_pgoptions is None:
                os.environ.pop("PGOPTIONS", None)
            else:
                os.environ["PGOPTIONS"] = prior_pgoptions
        self.assertIn("status", health)
        self.assertIn("checks", health)
        self.assertEqual(set(health["checks"].keys()), {"api", "database", "worker_heartbeat", "scheduler_heartbeat", "queue", "backup"})

        job_event = log_job_event("job.started", job_id=job_id, state="running")
        admin_event = log_admin_command_event(
            "admin.command.recorded",
            command_type="validation_trigger",
            actor_id="admin-1",
        )
        self.assertEqual(job_event["category"], "job_lifecycle")
        self.assertEqual(admin_event["category"], "admin_command")
        self.assertIsNotNone(datetime.fromisoformat(job_event["ts"]).astimezone(UTC))


if __name__ == "__main__":
    unittest.main()
