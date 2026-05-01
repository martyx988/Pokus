from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import psycopg

from pokus_backend.observability.health import collect_platform_health, evaluate_platform_health


class HealthReportingTests(unittest.TestCase):
    def test_evaluate_platform_health_reports_healthy_shape(self) -> None:
        now = datetime.now(UTC)
        payload = evaluate_platform_health(
            now=now,
            worker_heartbeat_at=now - timedelta(seconds=5),
            scheduler_heartbeat_at=now - timedelta(seconds=10),
            queue_depth=1,
            oldest_pending_age_seconds=120.0,
            worker_stale_after_seconds=30.0,
            scheduler_stale_after_seconds=60.0,
        )
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"]["api"]["status"], "ok")
        self.assertEqual(payload["checks"]["database"]["status"], "ok")
        self.assertEqual(payload["checks"]["worker_heartbeat"]["status"], "ok")
        self.assertEqual(payload["checks"]["scheduler_heartbeat"]["status"], "ok")
        self.assertEqual(payload["checks"]["queue"]["status"], "ok")
        self.assertEqual(payload["checks"]["backup"]["status"], "placeholder")

    def test_evaluate_platform_health_reports_missing_and_stale_states(self) -> None:
        now = datetime.now(UTC)
        payload = evaluate_platform_health(
            now=now,
            worker_heartbeat_at=None,
            scheduler_heartbeat_at=now - timedelta(hours=2),
            queue_depth=2,
            oldest_pending_age_seconds=5000.0,
            worker_stale_after_seconds=30.0,
            scheduler_stale_after_seconds=60.0,
        )
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["checks"]["worker_heartbeat"]["status"], "missing")
        self.assertEqual(payload["checks"]["scheduler_heartbeat"]["status"], "stale")
        self.assertEqual(payload["checks"]["queue"]["status"], "stale")

    def test_collect_platform_health_reports_database_unavailable(self) -> None:
        with patch(
            "pokus_backend.observability.health.psycopg.connect",
            side_effect=psycopg.OperationalError("db down"),
        ):
            payload = collect_platform_health(
                "postgresql://127.0.0.1:1/test",
                worker_stale_after_seconds=30.0,
                scheduler_stale_after_seconds=60.0,
            )
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["checks"]["database"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
