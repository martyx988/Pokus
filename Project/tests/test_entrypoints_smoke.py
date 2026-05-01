from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EntrypointsSmokeTests(unittest.TestCase):
    def _run_module(
        self,
        module: str,
        *args: str,
        env_overrides: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        if env_overrides:
            env.update(env_overrides)
        return subprocess.run(
            [sys.executable, "-m", module, *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_api_entrypoint_check_fails_clearly_when_database_unavailable(self) -> None:
        completed = self._run_module(
            "pokus_backend.api",
            "--check",
            env_overrides={"DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:1/pokus"},
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("api-check-failed", completed.stderr)

    def test_worker_entrypoint_once(self) -> None:
        completed = self._run_module("pokus_backend.worker", "--once")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("worker-tick", completed.stdout)

    def test_api_check_fails_when_database_unavailable(self) -> None:
        completed = self._run_module(
            "pokus_backend.api",
            "--check",
            env_overrides={"DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:1/pokus"},
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("api-check-failed", completed.stderr)

    def test_worker_check_fails_when_database_unavailable(self) -> None:
        completed = self._run_module(
            "pokus_backend.worker",
            "--check",
            env_overrides={"DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:1/pokus"},
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("worker-check-failed", completed.stderr)

    def test_database_migrate_fails_when_database_unavailable(self) -> None:
        completed = self._run_module(
            "pokus_backend.db",
            "--migrate",
            env_overrides={
                "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:1/pokus?connect_timeout=2"
            },
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("database-migrate-failed", completed.stderr)


if __name__ == "__main__":
    unittest.main()

