from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pokus_backend.domain.source_validation_models import SourceValidationRecord
from pokus_backend.validation.live_source_probe_runner import LiveSourceProbeRunResult


def write_keyed_b_live_probe_artifact(
    *,
    artifact_path: Path,
    command: str,
    run_result: LiveSourceProbeRunResult,
    records: list[SourceValidationRecord],
) -> Path:
    normalized_path = artifact_path.resolve()
    normalized_path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "task_id": "T67",
        "command": command,
        "validation_run_key": run_result.validation_run_key,
        "summary": {
            "source_count": len(run_result.source_results),
            "succeeded_count": run_result.succeeded_count,
            "skipped_count": run_result.skipped_count,
            "failed_count": run_result.failed_count,
        },
        "source_results": [
            {
                "source_code": row.source_code,
                "status": row.status,
                "classification_verdict": row.classification_verdict,
                "note": row.note,
                "persisted_record_id": row.persisted_record_id,
            }
            for row in run_result.source_results
        ],
        "records": [
            {
                "id": record.id,
                "source_code": record.source_code,
                "is_available": record.is_available,
                "auth_required": record.auth_required,
                "quota_rate_limit_notes": record.quota_rate_limit_notes,
                "speed_notes": record.speed_notes,
                "exchange_coverage_notes": record.exchange_coverage_notes,
                "observed_latency_ms": record.observed_latency_ms,
                "classification_verdict": record.classification_verdict,
                "assigned_role": record.assigned_role,
                "recorded_at": record.recorded_at.isoformat(),
                "updated_at": record.updated_at.isoformat(),
            }
            for record in records
        ],
    }
    normalized_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return normalized_path
