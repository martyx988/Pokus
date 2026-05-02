from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.source_probes.keyed_a.runner import run_keyed_a_source_probes


def main() -> int:
    parser = argparse.ArgumentParser(description="Run T66 keyed-a live source probes and write artifact evidence.")
    parser.add_argument(
        "--run-key",
        required=True,
        help="Validation run key used for source_validation_record persistence.",
    )
    parser.add_argument(
        "--sources",
        default="EODHD,FMP,FINNHUB,ALPHA_VANTAGE",
        help="Comma-separated keyed-a source codes.",
    )
    parser.add_argument(
        "--artifact-path",
        default=None,
        help="Optional artifact output path. Defaults to keyed_a/artifacts/t66_keyed_a_latest.json.",
    )
    parser.add_argument(
        "--sqlite-path",
        default="project/.tmp_t66_source_probes.sqlite",
        help="SQLite file used for evidence record persistence in this run.",
    )
    args = parser.parse_args()

    source_codes = [candidate.strip() for candidate in args.sources.split(",")]
    sqlite_path = Path(args.sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite+pysqlite:///{sqlite_path.as_posix()}")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            run_result, artifact_path = run_keyed_a_source_probes(
                session,
                validation_run_key=args.run_key,
                source_codes=source_codes,
                artifact_output_path=None if args.artifact_path is None else Path(args.artifact_path),
            )
            session.commit()
    finally:
        engine.dispose()

    print(
        "t66-keyed-a-probe-run-ok "
        f"run_key={run_result.validation_run_key} sources={len(run_result.source_results)} "
        f"succeeded={run_result.succeeded_count} skipped={run_result.skipped_count} failed={run_result.failed_count} "
        f"artifact={artifact_path.as_posix()}"
    )
    for source_result in run_result.source_results:
        print(
            "t66-keyed-a-probe-result "
            f"source={source_result.source_code} status={source_result.status} "
            f"classification={source_result.classification_verdict} note={source_result.note} "
            f"record_id={source_result.persisted_record_id}"
        )
    return 0 if run_result.failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

