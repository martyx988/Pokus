from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.source_validation_models import (
    SourceValidationRecord,
    SourceValidationRole,
    SourceValidationVerdict,
)


@dataclass(frozen=True, slots=True)
class SourceValidationRecordInput:
    validation_run_key: str
    source_code: str
    is_available: bool
    auth_required: bool
    quota_rate_limit_notes: str
    speed_notes: str
    exchange_coverage_notes: str
    classification_verdict: str
    assigned_role: str | None = None
    observed_latency_ms: int | None = None


def persist_source_validation_record(session: Session, payload: SourceValidationRecordInput) -> SourceValidationRecord:
    run_key = _required_text(payload.validation_run_key, field_name="validation_run_key", upper=False)
    source_code = _required_text(payload.source_code, field_name="source_code", upper=True)
    quota_notes = _required_text(payload.quota_rate_limit_notes, field_name="quota_rate_limit_notes", upper=False)
    speed_notes = _required_text(payload.speed_notes, field_name="speed_notes", upper=False)
    exchange_notes = _required_text(payload.exchange_coverage_notes, field_name="exchange_coverage_notes", upper=False)
    verdict = _validated_verdict(payload.classification_verdict)
    role = _validated_role(payload.assigned_role)

    if payload.observed_latency_ms is not None and payload.observed_latency_ms < 0:
        raise ValueError("observed_latency_ms must be >= 0 when provided")

    now = datetime.now(timezone.utc)
    existing = session.scalar(
        select(SourceValidationRecord).where(
            SourceValidationRecord.validation_run_key == run_key,
            SourceValidationRecord.source_code == source_code,
        )
    )
    if existing is None:
        existing = SourceValidationRecord(
            validation_run_key=run_key,
            source_code=source_code,
            is_available=payload.is_available,
            auth_required=payload.auth_required,
            quota_rate_limit_notes=quota_notes,
            speed_notes=speed_notes,
            exchange_coverage_notes=exchange_notes,
            observed_latency_ms=payload.observed_latency_ms,
            classification_verdict=verdict,
            assigned_role=role,
            recorded_at=now,
            updated_at=now,
        )
        session.add(existing)
    else:
        existing.is_available = payload.is_available
        existing.auth_required = payload.auth_required
        existing.quota_rate_limit_notes = quota_notes
        existing.speed_notes = speed_notes
        existing.exchange_coverage_notes = exchange_notes
        existing.observed_latency_ms = payload.observed_latency_ms
        existing.classification_verdict = verdict
        existing.assigned_role = role
        existing.updated_at = now

    session.flush()
    return existing


def get_source_validation_record(
    session: Session,
    *,
    validation_run_key: str,
    source_code: str,
) -> SourceValidationRecord | None:
    run_key = _required_text(validation_run_key, field_name="validation_run_key", upper=False)
    normalized_source_code = _required_text(source_code, field_name="source_code", upper=True)
    return session.scalar(
        select(SourceValidationRecord).where(
            SourceValidationRecord.validation_run_key == run_key,
            SourceValidationRecord.source_code == normalized_source_code,
        )
    )


def list_source_validation_records_for_run(session: Session, *, validation_run_key: str) -> list[SourceValidationRecord]:
    run_key = _required_text(validation_run_key, field_name="validation_run_key", upper=False)
    return list(
        session.scalars(
            select(SourceValidationRecord)
            .where(SourceValidationRecord.validation_run_key == run_key)
            .order_by(SourceValidationRecord.source_code.asc())
        )
    )


def _required_text(value: str, *, field_name: str, upper: bool) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    if upper:
        return normalized.upper()
    return normalized


def _validated_verdict(value: str) -> str:
    normalized = _required_text(value, field_name="classification_verdict", upper=False).lower()
    allowed = {member.value for member in SourceValidationVerdict}
    if normalized not in allowed:
        raise ValueError(f"classification_verdict must be one of: {sorted(allowed)}")
    return normalized


def _validated_role(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _required_text(value, field_name="assigned_role", upper=False).lower()
    allowed = {member.value for member in SourceValidationRole}
    if normalized not in allowed:
        raise ValueError(f"assigned_role must be one of: {sorted(allowed)}")
    return normalized
