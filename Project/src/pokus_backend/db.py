from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from pokus_backend.domain.instrument_models import Listing  # noqa: F401
from pokus_backend.domain.reference_models import Base
from pokus_backend.domain.source_validation_models import SourceValidationRecord  # noqa: F401
from pokus_backend.domain.reference_baseline import seed_launch_baseline_records
from pokus_backend.settings import load_settings


def to_sqlalchemy_url(database_url: str) -> str:
    parts = urlsplit(database_url)
    if "+" in parts.scheme:
        return database_url
    if parts.scheme == "postgresql":
        return urlunsplit(("postgresql+psycopg", parts.netloc, parts.path, parts.query, parts.fragment))
    return database_url


def check_database_connection(database_url: str) -> None:
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()


def run_migrations(database_url: str) -> None:
    sqlalchemy_url = to_sqlalchemy_url(database_url)
    if sqlalchemy_url.startswith("sqlite"):
        engine = create_engine(sqlalchemy_url)
        try:
            Base.metadata.create_all(engine)
            seed_launch_baseline_records(database_url)
        finally:
            engine.dispose()
        return

    project_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "migrations"))
    sqlalchemy_url = sqlalchemy_url.replace("%", "%%")
    alembic_cfg.set_main_option("sqlalchemy.url", sqlalchemy_url)
    command.upgrade(alembic_cfg, "head")


def main() -> int:
    parser = argparse.ArgumentParser(description="Database utilities for connectivity and migrations.")
    parser.add_argument("--check", action="store_true", help="Check PostgreSQL connectivity and exit.")
    parser.add_argument("--migrate", action="store_true", help="Apply baseline migrations and exit.")
    parser.add_argument(
        "--seed-launch-baseline",
        action="store_true",
        help="Create or update launch exchange and instrument-type baseline records.",
    )
    args = parser.parse_args()
    settings = load_settings()

    if args.check:
        try:
            check_database_connection(settings.database_url)
        except psycopg.OperationalError as exc:
            print(f"database-check-failed db={settings.database_url} error={exc}", file=sys.stderr)
            return 1
        print(f"database-check-ok db={settings.database_url}")
        return 0

    if args.migrate:
        try:
            run_migrations(settings.database_url)
        except Exception as exc:  # noqa: BLE001
            print(f"database-migrate-failed db={settings.database_url} error={exc}", file=sys.stderr)
            return 1
        print(f"database-migrate-ok db={settings.database_url}")
        return 0

    if args.seed_launch_baseline:
        try:
            seed_launch_baseline_records(settings.database_url)
        except Exception as exc:  # noqa: BLE001
            print(f"database-seed-launch-baseline-failed db={settings.database_url} error={exc}", file=sys.stderr)
            return 1
        print(f"database-seed-launch-baseline-ok db={settings.database_url}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
