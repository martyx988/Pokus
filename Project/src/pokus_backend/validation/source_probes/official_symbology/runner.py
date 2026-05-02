from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.live_source_probe_runner import LiveSourceProbeRunResult, run_live_source_probes
from pokus_backend.validation.source_probes.official_symbology.artifacts import (
    collect_official_symbology_records_for_run,
    default_official_symbology_artifact_path,
    write_official_symbology_validation_artifact,
)
from pokus_backend.validation.source_probes.official_symbology.probes import (
    build_official_symbology_probe_registry,
    normalize_official_symbology_source_codes,
)


def run_official_symbology_source_probes(
    session: Session,
    *,
    validation_run_key: str | None = None,
    source_codes: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    artifact_output_path: Path | None = None,
) -> tuple[LiveSourceProbeRunResult, Path]:
    selected_sources = normalize_official_symbology_source_codes(source_codes)
    probe_registry = build_official_symbology_probe_registry()
    run_result = run_live_source_probes(
        session,
        source_codes=selected_sources,
        validation_run_key=validation_run_key,
        probe_registry=probe_registry,
        env=(env if env is not None else os.environ),
    )
    records = collect_official_symbology_records_for_run(session, run_key=run_result.validation_run_key)
    artifact_path = write_official_symbology_validation_artifact(
        output_path=(
            artifact_output_path
            if artifact_output_path is not None
            else default_official_symbology_artifact_path()
        ),
        run_result=run_result,
        source_records=records,
    )
    return run_result, artifact_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute T68 official and symbology live probes and persist evidence artifact."
    )
    parser.add_argument(
        "--database-url",
        default="sqlite+pysqlite:///./project/.evidence/m31_t68_official_symbology.sqlite3",
        help="SQLAlchemy URL used to persist source-validation records.",
    )
    parser.add_argument(
        "--run-key",
        default=f"m3.1-t68-official-symbology-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        help="Validation run key stored with source-validation records.",
    )
    parser.add_argument(
        "--artifact-path",
        default=str(default_official_symbology_artifact_path()),
        help="Repo-tracked JSON artifact path for live run evidence.",
    )
    parser.add_argument(
        "--sources",
        default="NASDAQ_TRADER,NYSE,PSE_PSE_EDGE,OPENFIGI,NASDAQ_DATA_LINK",
        help="Comma-separated source codes for this official/symbology family run.",
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
    engine = create_engine(args.database_url)
    try:
        if not args.skip_schema_create:
            Base.metadata.create_all(engine)

        with Session(engine) as session:
            run_result, artifact_path = run_official_symbology_source_probes(
                session,
                validation_run_key=args.run_key,
                source_codes=source_codes,
                artifact_output_path=Path(args.artifact_path),
            )
            session.commit()
    finally:
        engine.dispose()

    print(
        "t68-official-symbology-live-probe-run-ok "
        f"run_key={run_result.validation_run_key} "
        f"sources={len(run_result.source_results)} "
        f"succeeded={run_result.succeeded_count} skipped={run_result.skipped_count} failed={run_result.failed_count}"
    )
    for source_result in run_result.source_results:
        print(
            "t68-official-symbology-live-probe-result "
            f"source={source_result.source_code} status={source_result.status} "
            f"classification={source_result.classification_verdict} "
            f"record_id={source_result.persisted_record_id}"
        )
    print(f"t68-official-symbology-artifact-path {artifact_path}")
    return 0 if run_result.failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())