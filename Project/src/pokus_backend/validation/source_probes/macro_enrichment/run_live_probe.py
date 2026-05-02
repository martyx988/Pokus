from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.source_probes.macro_enrichment.workflow import (
    run_macro_enrichment_source_probes,
)
from pokus_backend.validation.source_validation_records import list_source_validation_records_for_run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run live macro/enrichment probes (FRED, DBnomics, IMF, World Bank) and persist evidence records.",
    )
    parser.add_argument(
        "--database-url",
        default="sqlite+pysqlite:///./macro_enrichment_probe.sqlite",
        help="SQLAlchemy database URL used for storing source validation records.",
    )
    parser.add_argument(
        "--run-key",
        required=True,
        help="Validation run key for idempotent evidence persistence.",
    )
    parser.add_argument(
        "--evidence-json",
        default=None,
        help="Optional JSON output file path for a structured evidence snapshot.",
    )
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            run_result = run_macro_enrichment_source_probes(
                session,
                validation_run_key=args.run_key,
            )
            session.commit()
            persisted = list_source_validation_records_for_run(session, validation_run_key=run_result.validation_run_key)
    finally:
        engine.dispose()

    print(
        "macro-enrichment-probe-run-ok "
        f"run_key={run_result.validation_run_key} "
        f"sources={len(run_result.source_results)} "
        f"succeeded={run_result.succeeded_count} skipped={run_result.skipped_count} failed={run_result.failed_count}"
    )
    for item in run_result.source_results:
        print(
            "macro-enrichment-probe-result "
            f"source={item.source_code} status={item.status} "
            f"classification={item.classification_verdict} record_id={item.persisted_record_id}"
        )

    if args.evidence_json:
        payload = {
            "run_key": run_result.validation_run_key,
            "summary": {
                "sources": len(run_result.source_results),
                "succeeded": run_result.succeeded_count,
                "skipped": run_result.skipped_count,
                "failed": run_result.failed_count,
            },
            "records": [
                {
                    "source_code": row.source_code,
                    "is_available": row.is_available,
                    "auth_required": row.auth_required,
                    "classification_verdict": row.classification_verdict,
                    "assigned_role": row.assigned_role,
                    "quota_rate_limit_notes": row.quota_rate_limit_notes,
                    "speed_notes": row.speed_notes,
                    "exchange_coverage_notes": row.exchange_coverage_notes,
                    "observed_latency_ms": row.observed_latency_ms,
                }
                for row in persisted
            ],
        }
        output_path = Path(args.evidence_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"macro-enrichment-probe-evidence-json {output_path.as_posix()}")

    return 0 if run_result.failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
