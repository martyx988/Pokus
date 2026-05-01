from __future__ import annotations

import argparse
import sys
import time

import psycopg

from pokus_backend.db import check_database_connection
from pokus_backend.observability.health import upsert_runtime_heartbeat
from pokus_backend.settings import load_settings


def run_once() -> None:
    settings = load_settings()
    print(
        f"worker-tick env={settings.environment} "
        f"db={settings.database_url} poll={settings.worker_poll_seconds}"
    )
    try:
        upsert_runtime_heartbeat(settings.database_url, "worker")
        upsert_runtime_heartbeat(settings.database_url, "scheduler")
    except psycopg.Error:
        # Heartbeats are best-effort so local/dev ticks can run without a database.
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Run worker/scheduler runtime role.")
    parser.add_argument("--check", action="store_true", help="Validate startup dependencies and exit.")
    parser.add_argument("--once", action="store_true", help="Run one worker cycle and exit.")
    args = parser.parse_args()
    settings = load_settings()

    if args.check:
        try:
            check_database_connection(settings.database_url)
        except psycopg.OperationalError as exc:
            print(
                f"worker-check-failed env={settings.environment} db={settings.database_url} error={exc}",
                file=sys.stderr,
            )
            return 1
        print(f"worker-check-ok env={settings.environment} db={settings.database_url}")
        return 0

    if args.once:
        run_once()
        return 0

    while True:
        run_once()
        time.sleep(load_settings().worker_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

