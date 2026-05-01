from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from alembic import command
from alembic.config import Config

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
    project_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", to_sqlalchemy_url(database_url))
    command.upgrade(alembic_cfg, "head")


def main() -> int:
    parser = argparse.ArgumentParser(description="Database utilities for connectivity and migrations.")
    parser.add_argument("--check", action="store_true", help="Check PostgreSQL connectivity and exit.")
    parser.add_argument("--migrate", action="store_true", help="Apply baseline migrations and exit.")
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

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
