from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EntrypointsSmokeTests(unittest.TestCase):
    def _run_module(self, module: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", module, *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_api_entrypoint_check(self) -> None:
        completed = self._run_module("pokus_backend.api", "--check")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("api-check-ok", completed.stdout)

    def test_worker_entrypoint_once(self) -> None:
        completed = self._run_module("pokus_backend.worker", "--once")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("worker-tick", completed.stdout)


if __name__ == "__main__":
    unittest.main()

