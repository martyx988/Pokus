from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MigrationBaselineRuntimeTests(unittest.TestCase):
    def test_sqlite_migration_succeeds_and_creates_m31_runtime_tables(self) -> None:
        fd, raw_path = tempfile.mkstemp(suffix=".sqlite3", prefix="t74_gate_runtime_")
        os.close(fd)
        db_path = Path(raw_path)
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            env["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"

            migrated = subprocess.run(
                [sys.executable, "-m", "pokus_backend.db", "--migrate"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(migrated.returncode, 0, msg=migrated.stderr)

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            tables = {row[0] for row in rows}
            self.assertIn("listing", tables)
            self.assertIn("source_validation_record", tables)
        finally:
            for _ in range(5):
                try:
                    if db_path.exists():
                        db_path.unlink()
                    break
                except PermissionError:
                    time.sleep(0.1)


if __name__ == "__main__":
    unittest.main()
