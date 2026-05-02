from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pokus_backend.validation.live_source_probe_runner import LiveSourceProbeRunResult
from pokus_backend.validation.source_validation_records import list_source_validation_records_for_run


def write_keyed_a_validation_artifact(
    *,
    output_path: Path,
    run_result: LiveSourceProbeRunResult,
    source_records: list[Any],
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_records = []
    for record in source_records:
        serialized_records.append(
            {
                "source_code": record.source_code,
                "is_available": record.is_available,
                "auth_required": record.auth_required,
                "quota_rate_limit_notes": record.quota_rate_limit_notes,
                "speed_notes": record.speed_notes,
                "exchange_coverage_notes": record.exchange_coverage_notes,
                "observed_latency_ms": record.observed_latency_ms,
                "classification_verdict": record.classification_verdict,
                "assigned_role": record.assigned_role,
            }
        )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_run_key": run_result.validation_run_key,
        "summary": {
            "source_count": len(run_result.source_results),
            "succeeded_count": run_result.succeeded_count,
            "skipped_count": run_result.skipped_count,
            "failed_count": run_result.failed_count,
        },
        "source_results": [
            {
                "source_code": source_result.source_code,
                "status": source_result.status,
                "classification_verdict": source_result.classification_verdict,
                "note": source_result.note,
                "persisted_record_id": source_result.persisted_record_id,
            }
            for source_result in run_result.source_results
        ],
        "source_validation_records": serialized_records,
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def default_keyed_a_artifact_path() -> Path:
    return Path(__file__).with_name("artifacts").joinpath("t66_keyed_a_latest.json")


def collect_keyed_a_records_for_run(session: Any, *, run_key: str) -> list[Any]:
    return list_source_validation_records_for_run(session, validation_run_key=run_key)

