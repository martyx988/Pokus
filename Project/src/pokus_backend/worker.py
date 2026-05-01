from __future__ import annotations

import argparse
import sys
import time

import psycopg

from pokus_backend.db import check_database_connection
from pokus_backend.observability.health import upsert_runtime_heartbeat
from pokus_backend.observability.logging import log_event
from pokus_backend.settings import load_settings


def run_once() -> None:
    settings = load_settings()
    log_event(
        "worker.tick.started",
        environment=settings.environment,
        worker_poll_seconds=settings.worker_poll_seconds,
    )
    print(
        f"worker-tick env={settings.environment} "
        f"db={settings.database_url} poll={settings.worker_poll_seconds}"
    )
    try:
        upsert_runtime_heartbeat(settings.database_url, "worker")
        upsert_runtime_heartbeat(settings.database_url, "scheduler")
    except psycopg.Error:
        # Heartbeats are best-effort so local/dev ticks can run without a database.
        log_event("worker.heartbeat.failed", environment=settings.environment)
    else:
        log_event("worker.heartbeat.updated", environment=settings.environment)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run worker/scheduler runtime role.")
    parser.add_argument("--check", action="store_true", help="Validate startup dependencies and exit.")
    parser.add_argument("--once", action="store_true", help="Run one worker cycle and exit.")
    args = parser.parse_args()
    settings = load_settings()
    log_event("worker.starting", environment=settings.environment, poll_seconds=settings.worker_poll_seconds)

    if args.check:
        try:
            check_database_connection(settings.database_url)
        except psycopg.OperationalError as exc:
            log_event(
                "worker.check.failed",
                environment=settings.environment,
                database_url=settings.database_url,
                error=str(exc),
            )
            print(
                f"worker-check-failed env={settings.environment} db={settings.database_url} error={exc}",
                file=sys.stderr,
            )
            return 1
        log_event("worker.check.succeeded", environment=settings.environment, database_url=settings.database_url)
        print(f"worker-check-ok env={settings.environment} db={settings.database_url}")
        return 0

    if args.once:
        run_once()
        log_event("worker.stopped", mode="once")
        return 0

    while True:
        run_once()
        time.sleep(load_settings().worker_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

