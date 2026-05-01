from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from pokus_backend.jobs.load_job import LoadJob, LoadJobState, TERMINAL_LOAD_JOB_STATES, is_terminal_load_job_state
from pokus_backend.jobs.state_transitions import (
    ALLOWED_LOAD_JOB_STATE_TRANSITIONS,
    InvalidLoadJobTransition,
    can_transition_load_job_state,
    transition_load_job_state,
)


class LoadJobStateTransitionTests(unittest.TestCase):
    def test_all_allowed_transitions_are_permitted(self) -> None:
        for source_state, targets in ALLOWED_LOAD_JOB_STATE_TRANSITIONS.items():
            for target_state in targets:
                self.assertTrue(can_transition_load_job_state(source_state, target_state))
                self.assertEqual(transition_load_job_state(source_state, target_state), target_state)

    def test_representative_forbidden_transitions_fail(self) -> None:
        with self.assertRaises(InvalidLoadJobTransition):
            transition_load_job_state(LoadJobState.QUEUED, LoadJobState.SUCCEEDED)
        with self.assertRaises(InvalidLoadJobTransition):
            transition_load_job_state(LoadJobState.SUCCEEDED, LoadJobState.RUNNING)
        with self.assertRaises(InvalidLoadJobTransition):
            transition_load_job_state(LoadJobState.CANCELLED, LoadJobState.QUEUED)

    def test_terminal_states_are_exact_and_detected(self) -> None:
        self.assertEqual(
            TERMINAL_LOAD_JOB_STATES,
            frozenset({LoadJobState.SUCCEEDED, LoadJobState.FAILED, LoadJobState.CANCELLED}),
        )
        for state in LoadJobState:
            expected = state in TERMINAL_LOAD_JOB_STATES
            self.assertEqual(is_terminal_load_job_state(state), expected)


class LoadJobStorageConstraintTests(unittest.TestCase):
    def _create_test_table(self, metadata: sa.MetaData) -> sa.Table:
        return sa.Table(
            "load_jobs",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("idempotency_key", sa.Text, nullable=False),
            sa.Column("state", sa.Text, nullable=False),
            sa.Column("lock_token", sa.Text, nullable=True),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        )

    def test_idempotency_key_unique_for_non_terminal_states(self) -> None:
        engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
        metadata = sa.MetaData()
        load_jobs = self._create_test_table(metadata)
        metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "CREATE UNIQUE INDEX uq_load_jobs_active_idempotency "
                    "ON load_jobs (idempotency_key) "
                    "WHERE state NOT IN ('succeeded','failed','cancelled')"
                )
            )
            conn.execute(
                load_jobs.insert().values(idempotency_key="same-key", state=LoadJobState.QUEUED.value)
            )
            with self.assertRaises(IntegrityError):
                conn.execute(
                    load_jobs.insert().values(idempotency_key="same-key", state=LoadJobState.RUNNING.value)
                )

    def test_idempotency_key_can_repeat_after_terminal_state(self) -> None:
        engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
        metadata = sa.MetaData()
        load_jobs = self._create_test_table(metadata)
        metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "CREATE UNIQUE INDEX uq_load_jobs_active_idempotency "
                    "ON load_jobs (idempotency_key) "
                    "WHERE state NOT IN ('succeeded','failed','cancelled')"
                )
            )
            conn.execute(
                load_jobs.insert().values(idempotency_key="same-key", state=LoadJobState.SUCCEEDED.value)
            )
            conn.execute(
                load_jobs.insert().values(idempotency_key="same-key", state=LoadJobState.QUEUED.value)
            )

    def test_lock_and_heartbeat_fields_hold_worker_recovery_metadata(self) -> None:
        now = datetime.now(timezone.utc)
        job = LoadJob(
            id=123,
            idempotency_key="x",
            lock_token="token-1",
            lock_acquired_at=now,
            lock_expires_at=now + timedelta(minutes=5),
            heartbeat_at=now + timedelta(seconds=10),
            stale_abandoned_at=now + timedelta(minutes=6),
        )
        self.assertEqual(job.lock_token, "token-1")
        self.assertGreater(job.lock_expires_at, job.lock_acquired_at)
        self.assertGreater(job.heartbeat_at, job.lock_acquired_at)
        self.assertIsNotNone(job.stale_abandoned_at)


if __name__ == "__main__":
    unittest.main()

