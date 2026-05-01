from __future__ import annotations

import argparse
import sys
import time

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.discovery.exchange_priority import recompute_exchange_activity_priority
from pokus_backend.db import check_database_connection
from pokus_backend.validation.run_orchestrator import orchestrate_launch_exchange_validation_run
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
    parser.add_argument(
        "--recompute-exchange-priority",
        action="store_true",
        help="Recompute exchange activity priority rankings from trailing expected-trading-day values.",
    )
    parser.add_argument(
        "--run-launch-validation",
        action="store_true",
        help="Start a launch exchange validation run and persist report shell records.",
    )
    parser.add_argument(
        "--validation-exchanges",
        default="NYSE,NASDAQ,PSE",
        help="Comma-separated exchange codes for launch validation runs.",
    )
    parser.add_argument(
        "--validation-run-key",
        default=None,
        help="Optional idempotency key for a validation run.",
    )
    parser.add_argument(
        "--validation-fail-reason",
        default=None,
        help="Optional failure reason to mark the validation run as failed.",
    )
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

    if args.recompute_exchange_priority:
        updated_count = recompute_exchange_activity_priority(settings.database_url)
        print(
            f"worker-exchange-priority-recompute-ok env={settings.environment} updated_exchanges={updated_count}"
        )
        log_event(
            "worker.exchange_priority.recompute.succeeded",
            environment=settings.environment,
            updated_exchanges=updated_count,
        )
        return 0

    if args.run_launch_validation:
        target_exchanges = [value.strip() for value in args.validation_exchanges.split(",")]
        engine = create_engine(settings.database_url)
        try:
            with Session(engine) as session:
                run_result = orchestrate_launch_exchange_validation_run(
                    session,
                    target_exchange_codes=target_exchanges,
                    run_key=args.validation_run_key,
                    fail_reason=args.validation_fail_reason,
                )
                session.commit()
        finally:
            engine.dispose()
        print(
            "worker-launch-validation-run-ok "
            f"env={settings.environment} run_key={run_result.run.run_key} state={run_result.run.state} "
            f"exchange_count={len(run_result.reports)}"
        )
        log_event(
            "worker.launch_validation.run.completed",
            environment=settings.environment,
            run_key=run_result.run.run_key,
            run_state=run_result.run.state,
            exchange_count=len(run_result.reports),
        )
        return 0

    while True:
        run_once()
        time.sleep(load_settings().worker_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

