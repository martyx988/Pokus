from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.live_source_probe_runner import (
    LiveSourceProbeRunResult,
    run_live_source_probes,
)
from pokus_backend.validation.source_validation_records import list_source_validation_records_for_run

from .evidence import write_keyed_b_live_probe_artifact
from .probes import KEYED_B_SOURCE_CODES, build_keyed_b_probe_registry, keyed_b_env_with_secret_fallbacks

_MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = _MODULE_DIR / "artifacts" / "t67_keyed_b_live_probe.sqlite3"
DEFAULT_ARTIFACT_PATH = _MODULE_DIR / "artifacts" / "t67_keyed_b_live_probe_evidence.json"


@dataclass(frozen=True, slots=True)
class KeyedBLiveProbeExecutionResult:
    run_result: LiveSourceProbeRunResult
    artifact_path: Path
    sqlite_path: Path


def run_keyed_b_live_probe_family(
    *,
    validation_run_key: str | None,
    command: str,
    source_codes: list[str],
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
    env: Mapping[str, str] | None = None,
) -> KeyedBLiveProbeExecutionResult:
    normalized_sqlite_path = sqlite_path.resolve()
    normalized_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite+pysqlite:///{normalized_sqlite_path.as_posix()}"
    engine = create_engine(database_url)

    try:
        Base.metadata.create_all(engine)
        effective_env = keyed_b_env_with_secret_fallbacks(env if env is not None else os.environ)
        with Session(engine) as session:
            run_result = run_live_source_probes(
                session,
                source_codes=source_codes,
                validation_run_key=validation_run_key,
                probe_registry=build_keyed_b_probe_registry(),
                env=effective_env,
            )
            session.commit()
            records = list_source_validation_records_for_run(
                session,
                validation_run_key=run_result.validation_run_key,
            )
        written_path = write_keyed_b_live_probe_artifact(
            artifact_path=artifact_path,
            command=command,
            run_result=run_result,
            records=records,
        )
        return KeyedBLiveProbeExecutionResult(
            run_result=run_result,
            artifact_path=written_path,
            sqlite_path=normalized_sqlite_path,
        )
    finally:
        engine.dispose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run T67 keyed-B live source probes and persist evidence artifacts.")
    parser.add_argument(
        "--validation-run-key",
        default=None,
        help="Optional idempotency key for this keyed-B source probe run.",
    )
    parser.add_argument(
        "--sources",
        default=",".join(KEYED_B_SOURCE_CODES),
        help="Comma-separated keyed-B source codes to execute.",
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(DEFAULT_SQLITE_PATH),
        help="SQLite file path used to persist source validation records for this run.",
    )
    parser.add_argument(
        "--artifact-path",
        default=str(DEFAULT_ARTIFACT_PATH),
        help="JSON artifact path for persisted keyed-B evidence summary.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    target_sources = [value.strip() for value in args.sources.split(",") if value.strip()]
    command = (
        "python -m pokus_backend.validation.source_probes.keyed_b.live_run "
        f"--validation-run-key {args.validation_run_key or '<auto>'} "
        f"--sources {','.join(target_sources)} "
        f"--sqlite-path {args.sqlite_path} "
        f"--artifact-path {args.artifact_path}"
    )
    result = run_keyed_b_live_probe_family(
        validation_run_key=args.validation_run_key,
        command=command,
        source_codes=target_sources,
        sqlite_path=Path(args.sqlite_path),
        artifact_path=Path(args.artifact_path),
    )

    print(
        "t67-keyed-b-live-probe-run-ok "
        f"run_key={result.run_result.validation_run_key} "
        f"sources={len(result.run_result.source_results)} "
        f"succeeded={result.run_result.succeeded_count} "
        f"skipped={result.run_result.skipped_count} "
        f"failed={result.run_result.failed_count}"
    )
    for source_result in result.run_result.source_results:
        print(
            "t67-keyed-b-live-probe-result "
            f"source={source_result.source_code} status={source_result.status} "
            f"classification={source_result.classification_verdict} record_id={source_result.persisted_record_id}"
        )
    print(f"t67-keyed-b-live-probe-artifact {result.artifact_path}")
    print(f"t67-keyed-b-live-probe-sqlite {result.sqlite_path}")
    return 0 if result.run_result.failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
