from __future__ import annotations

import unittest
from unittest.mock import patch

from pokus_backend.settings import Settings
from pokus_backend.validation.live_source_probe_runner import LiveSourceProbeRunResult, LiveSourceProbeSourceResult
from pokus_backend.worker import main


class _FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __enter__(self) -> _FakeSession:
        return self._session

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class WorkerLiveSourceProbeCommandTests(unittest.TestCase):
    def test_worker_live_source_probe_command_dispatches_runner_with_selected_sources(self) -> None:
        settings = Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            api_host="127.0.0.1",
            api_port=8000,
            worker_poll_seconds=0.1,
            app_read_token="app-token",
            operator_session_token="op-token",
            admin_session_token="admin-token",
        )
        fake_engine = _FakeEngine()
        fake_session = _FakeSession()
        fake_result = LiveSourceProbeRunResult(
            validation_run_key="source-probe-run-1",
            source_results=[
                LiveSourceProbeSourceResult(
                    source_code="YF",
                    status="succeeded",
                    persisted_record_id=101,
                    classification_verdict="validation_only",
                    note="probe_completed",
                )
            ],
        )

        with (
            patch("sys.argv", ["worker", "--run-live-source-probes", "--source-probe-sources", " YF , FMP "]),
            patch("pokus_backend.worker.load_settings", return_value=settings),
            patch("pokus_backend.worker.to_sqlalchemy_url", return_value="sqlite+pysqlite:///:memory:"),
            patch("pokus_backend.worker.create_engine", return_value=fake_engine),
            patch("pokus_backend.worker.Session", side_effect=lambda _: _FakeSessionContext(fake_session)),
            patch("pokus_backend.worker.run_live_source_probes", return_value=fake_result) as run_live_source_probes_mock,
        ):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertTrue(fake_session.committed)
        self.assertTrue(fake_engine.disposed)
        self.assertEqual(run_live_source_probes_mock.call_count, 1)
        self.assertEqual(run_live_source_probes_mock.call_args.kwargs["source_codes"], ["YF", "FMP"])
        self.assertEqual(
            run_live_source_probes_mock.call_args.kwargs["validation_run_key"],
            None,
        )


if __name__ == "__main__":
    unittest.main()
