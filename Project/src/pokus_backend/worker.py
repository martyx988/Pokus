from __future__ import annotations

import argparse
import time

from pokus_backend.settings import load_settings


def run_once() -> None:
    settings = load_settings()
    print(
        f"worker-tick env={settings.environment} "
        f"db={settings.database_url} poll={settings.worker_poll_seconds}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run worker/scheduler runtime role.")
    parser.add_argument("--once", action="store_true", help="Run one worker cycle and exit.")
    args = parser.parse_args()

    if args.once:
        run_once()
        return 0

    while True:
        run_once()
        time.sleep(load_settings().worker_poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())

