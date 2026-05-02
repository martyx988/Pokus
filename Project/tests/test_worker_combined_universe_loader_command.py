from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from pokus_backend.discovery.combined_loader import CombinedUniverseLoaderResult
from pokus_backend.settings import Settings
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


class WorkerCombinedUniverseLoaderCommandTests(unittest.TestCase):
    def test_worker_combined_loader_dispatches_runtime_loader(self) -> None:
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
        fake_result = CombinedUniverseLoaderResult(
            effective_day=date(2026, 5, 2),
            selected_sources=("NYSE", "NASDAQ_TRADER", "OPENFIGI"),
            selected_listing_ids=(1, 2),
            persisted_candidate_count=3,
            projected_supported_listing_count=2,
        )
        with (
            patch("sys.argv", ["worker", "--run-combined-universe-loader"]),
            patch("pokus_backend.worker.load_settings", return_value=settings),
            patch("pokus_backend.worker.to_sqlalchemy_url", return_value="sqlite+pysqlite:///:memory:"),
            patch("pokus_backend.worker.create_engine", return_value=fake_engine),
            patch("pokus_backend.worker.Session", side_effect=lambda _: _FakeSessionContext(fake_session)),
            patch("pokus_backend.worker.execute_combined_universe_loader", return_value=fake_result) as loader_mock,
        ):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertTrue(fake_session.committed)
        self.assertTrue(fake_engine.disposed)
        self.assertEqual(loader_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
