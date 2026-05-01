from __future__ import annotations

import unittest
from unittest.mock import patch

import psycopg

from pokus_backend.domain.admin_audit import AdminCommand, AdminCommandType
from pokus_backend.jobs.load_job import LoadJobState
from pokus_backend.jobs.state_transitions import transition_load_job_state
from pokus_backend.observability.health import collect_platform_health
from pokus_backend.observability.logging import log_event
from pokus_backend.observability.metrics import (
    STORE,
    record_api_error,
    record_database_connectivity,
    record_job_state_count,
    record_pending_job_age,
    record_queue_depth,
)


class StructuredLoggingTests(unittest.TestCase):
    def test_log_event_redacts_secrets(self) -> None:
        payload = log_event(
            "health.check.failed",
            token="abc",
            nested={"authorization": "Bearer secret"},
            reason="db down",
        )
        self.assertEqual(payload["event"], "health.check.failed")
        self.assertEqual(payload["token"], "***")
        self.assertEqual(payload["nested"]["authorization"], "***")
        self.assertEqual(payload["reason"], "db down")

    def test_job_lifecycle_event_is_emitted_for_representative_transition(self) -> None:
        with patch("pokus_backend.jobs.state_transitions.log_job_event") as log_job_event_mock:
            transition_load_job_state(LoadJobState.QUEUED, LoadJobState.RUNNING)
        log_job_event_mock.assert_called_once()
        event_name = log_job_event_mock.call_args.args[0]
        self.assertEqual(event_name, "job.started")

    def test_admin_command_event_is_emitted(self) -> None:
        with patch("pokus_backend.domain.admin_audit.log_admin_command_event") as log_admin_event_mock:
            AdminCommand(
                id=12,
                command_type=AdminCommandType.VALIDATION_TRIGGER,
                actor_id="admin-1",
                actor_type="admin",
            )
        log_admin_event_mock.assert_called_once()
        self.assertEqual(log_admin_event_mock.call_args.args[0], "admin.command.recorded")


class MetricsHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        STORE.reset()

    def test_basic_metric_helpers_emit_expected_values(self) -> None:
        record_database_connectivity(True)
        record_queue_depth(7)
        record_pending_job_age(12.5)
        record_job_state_count("queued", 4)
        record_api_error(503)
        self.assertEqual(STORE.gauges["database.connectivity"], 1.0)
        self.assertEqual(STORE.gauges["queue.depth"], 7.0)
        self.assertEqual(STORE.gauges["queue.oldest_pending_age_seconds"], 12.5)
        self.assertEqual(STORE.gauges["jobs.state_count.queued"], 4.0)
        self.assertEqual(STORE.counters["api.errors"], 1.0)
        self.assertEqual(STORE.counters["api.errors.503"], 1.0)

    def test_health_failure_logs_without_secret_values(self) -> None:
        with (
            patch(
                "pokus_backend.observability.health.psycopg.connect",
                side_effect=psycopg.OperationalError("database offline"),
            ),
            patch("pokus_backend.observability.health.log_event") as log_event_mock,
        ):
            payload = collect_platform_health("postgresql://u:p@localhost:1/db", 30.0, 60.0)
        self.assertEqual(payload["status"], "error")
        log_event_mock.assert_called_once()
        self.assertEqual(log_event_mock.call_args.args[0], "health.check.failed")
        self.assertNotIn("postgresql://u:p@localhost:1/db", str(log_event_mock.call_args))


if __name__ == "__main__":
    unittest.main()
