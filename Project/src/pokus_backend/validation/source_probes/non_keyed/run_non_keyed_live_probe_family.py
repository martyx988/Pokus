from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.live_source_probe_runner import run_live_source_probes
from pokus_backend.validation.source_validation_records import list_source_validation_records_for_run

from .probe_registry import build_non_keyed_live_source_probe_registry

_DEFAULT_SOURCE_CODES = ["YFINANCE", "STOOQ", "AKSHARE"]


def execute_non_keyed_live_source_probe_family(
    *,
    database_url: str,
    validation_run_key: str,
    artifact_path: str,
    source_codes: list[str] | None = None,
    ensure_schema: bool = True,
) -> dict[str, object]:
    selected_sources = source_codes if source_codes is not None else list(_DEFAULT_SOURCE_CODES)
    _ensure_sqlite_parent_directory(database_url)
    engine = create_engine(database_url)
    try:
        if ensure_schema:
            Base.metadata.create_all(engine)

        with Session(engine) as session:
            run_result = run_live_source_probes(
                session,
                source_codes=selected_sources,
                validation_run_key=validation_run_key,
                probe_registry=build_non_keyed_live_source_probe_registry(),
            )
            session.commit()
            rows = list_source_validation_records_for_run(session, validation_run_key=run_result.validation_run_key)
    finally:
        engine.dispose()

    payload = {
        "task_id": "T65",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_run_key": run_result.validation_run_key,
        "source_results": [
            {
                "source_code": result.source_code,
                "status": result.status,
                "classification_verdict": result.classification_verdict,
                "record_id": result.persisted_record_id,
            }
            for result in run_result.source_results
        ],
        "persisted_records": [
            {
                "id": row.id,
                "source_code": row.source_code,
                "is_available": row.is_available,
                "auth_required": row.auth_required,
                "quota_rate_limit_notes": row.quota_rate_limit_notes,
                "speed_notes": row.speed_notes,
                "exchange_coverage_notes": row.exchange_coverage_notes,
                "classification_verdict": row.classification_verdict,
                "assigned_role": row.assigned_role,
                "observed_latency_ms": row.observed_latency_ms,
                "recorded_at": row.recorded_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }
            for row in rows
        ],
        "aggregate": {
            "source_count": len(run_result.source_results),
            "succeeded_count": run_result.succeeded_count,
            "skipped_count": run_result.skipped_count,
            "failed_count": run_result.failed_count,
        },
    }

    artifact_target = Path(artifact_path)
    artifact_target.parent.mkdir(parents=True, exist_ok=True)
    artifact_target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _ensure_sqlite_parent_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return
    if ":///" not in database_url:
        return
    path_part = database_url.split(":///", 1)[1]
    if path_part in {"", ":memory:"}:
        return
    local_path = Path(path_part)
    if local_path.name == ":memory:":
        return
    if local_path.is_absolute():
        target = local_path
    else:
        target = Path.cwd() / local_path
    target.parent.mkdir(parents=True, exist_ok=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute T65 non-keyed source live probes and capture evidence.")
    parser.add_argument(
        "--database-url",
        default="sqlite+pysqlite:///./project/.evidence/m31_t65_non_keyed_live_probe.sqlite3",
        help="SQLAlchemy URL used to persist source-validation records.",
    )
    parser.add_argument(
        "--run-key",
        default=f"m3.1-t65-non-keyed-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        help="Validation run key stored with source-validation records.",
    )
    parser.add_argument(
        "--artifact-path",
        default="project/src/pokus_backend/validation/source_probes/non_keyed/artifacts/m3_1_t65_live_probe_results.json",
        help="Repo-tracked JSON artifact path for live run evidence.",
    )
    parser.add_argument(
        "--sources",
        default="YFINANCE,STOOQ,AKSHARE",
        help="Comma-separated source codes for this non-keyed family run.",
    )
    parser.add_argument(
        "--skip-schema-create",
        action="store_true",
        help="Skip SQLAlchemy metadata create-all before probe execution.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    source_codes = [value.strip() for value in args.sources.split(",") if value.strip()]
    payload = execute_non_keyed_live_source_probe_family(
        database_url=args.database_url,
        validation_run_key=args.run_key,
        artifact_path=args.artifact_path,
        source_codes=source_codes,
        ensure_schema=not args.skip_schema_create,
    )
    aggregate = payload["aggregate"]
    print(
        "t65-non-keyed-live-probe-run-ok "
        f"run_key={payload['validation_run_key']} "
        f"sources={aggregate['source_count']} succeeded={aggregate['succeeded_count']} "
        f"skipped={aggregate['skipped_count']} failed={aggregate['failed_count']}"
    )
    for row in payload["persisted_records"]:
        print(
            "t65-non-keyed-live-probe-record "
            f"source={row['source_code']} available={row['is_available']} "
            f"classification={row['classification_verdict']} role={row['assigned_role']} "
            f"latency_ms={row['observed_latency_ms']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
