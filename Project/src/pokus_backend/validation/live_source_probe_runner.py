from __future__ import annotations

import os
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Mapping
from uuid import uuid4

from sqlalchemy.orm import Session

from pokus_backend.settings import default_source_probe_secret_env_vars
from pokus_backend.validation.source_validation_records import (
    SourceValidationRecordInput,
    persist_source_validation_record,
)

_SECRET_MODE_NONE = "none"
_SECRET_MODE_REQUIRED = "required"
_SECRET_MODE_OPTIONAL = "optional"
_ALLOWED_SECRET_MODES = {
    _SECRET_MODE_NONE,
    _SECRET_MODE_REQUIRED,
    _SECRET_MODE_OPTIONAL,
}


@dataclass(frozen=True, slots=True)
class LiveSourceProbeExecutionContext:
    validation_run_key: str
    source_code: str
    secrets: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class LiveSourceProbeExecutionPayload:
    is_available: bool
    quota_rate_limit_notes: str
    speed_notes: str
    exchange_coverage_notes: str
    classification_verdict: str
    assigned_role: str | None = None
    observed_latency_ms: int | None = None


LiveSourceProbeCallable = Callable[[LiveSourceProbeExecutionContext], LiveSourceProbeExecutionPayload]


@dataclass(frozen=True, slots=True)
class LiveSourceProbeDefinition:
    source_code: str
    probe: LiveSourceProbeCallable
    secret_mode: str = _SECRET_MODE_NONE
    secret_env_vars: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LiveSourceProbeSourceResult:
    source_code: str
    status: str
    persisted_record_id: int
    classification_verdict: str
    note: str


@dataclass(frozen=True, slots=True)
class LiveSourceProbeRunResult:
    validation_run_key: str
    source_results: list[LiveSourceProbeSourceResult]

    @property
    def succeeded_count(self) -> int:
        return len([result for result in self.source_results if result.status == "succeeded"])

    @property
    def skipped_count(self) -> int:
        return len([result for result in self.source_results if result.status.startswith("skipped_")])

    @property
    def failed_count(self) -> int:
        return len([result for result in self.source_results if result.status.startswith("failed_")])


def build_live_source_probe_registry() -> dict[str, LiveSourceProbeDefinition]:
    """Generic boundary only; source-specific registrations are added by later tasks."""
    return {}


def run_live_source_probes(
    session: Session,
    *,
    source_codes: list[str],
    validation_run_key: str | None = None,
    probe_registry: Mapping[str, LiveSourceProbeDefinition] | None = None,
    env: Mapping[str, str] | None = None,
) -> LiveSourceProbeRunResult:
    selected_sources = _normalize_selected_sources(source_codes)
    run_key = _normalize_run_key(validation_run_key)
    registry = _normalize_registry(probe_registry if probe_registry is not None else build_live_source_probe_registry())
    environment = env if env is not None else os.environ
    results: list[LiveSourceProbeSourceResult] = []

    for source_code in selected_sources:
        definition = registry.get(source_code)
        if definition is None:
            record = persist_source_validation_record(
                session,
                SourceValidationRecordInput(
                    validation_run_key=run_key,
                    source_code=source_code,
                    is_available=False,
                    auth_required=False,
                    quota_rate_limit_notes="source_probe_not_registered",
                    speed_notes="probe_not_executed",
                    exchange_coverage_notes="source_probe_not_registered",
                    classification_verdict="reject",
                    assigned_role=None,
                    observed_latency_ms=None,
                ),
            )
            results.append(
                LiveSourceProbeSourceResult(
                    source_code=source_code,
                    status="failed_source_not_registered",
                    persisted_record_id=record.id,
                    classification_verdict=record.classification_verdict,
                    note="source_probe_not_registered",
                )
            )
            continue

        missing_secrets, selected_secrets = _resolve_secrets(definition=definition, env=environment)
        if missing_secrets:
            missing_label = ",".join(missing_secrets)
            status = (
                "skipped_missing_required_secret"
                if definition.secret_mode == _SECRET_MODE_REQUIRED
                else "skipped_missing_optional_secret"
            )
            record = persist_source_validation_record(
                session,
                SourceValidationRecordInput(
                    validation_run_key=run_key,
                    source_code=source_code,
                    is_available=False,
                    auth_required=(definition.secret_mode == _SECRET_MODE_REQUIRED),
                    quota_rate_limit_notes=f"missing_{definition.secret_mode}_secrets:{missing_label}",
                    speed_notes="probe_not_executed",
                    exchange_coverage_notes=f"missing_{definition.secret_mode}_secrets:{missing_label}",
                    classification_verdict="validation_only",
                    assigned_role="validation_only",
                    observed_latency_ms=None,
                ),
            )
            results.append(
                LiveSourceProbeSourceResult(
                    source_code=source_code,
                    status=status,
                    persisted_record_id=record.id,
                    classification_verdict=record.classification_verdict,
                    note=f"missing_{definition.secret_mode}_secrets",
                )
            )
            continue

        started = perf_counter()
        try:
            payload = definition.probe(
                LiveSourceProbeExecutionContext(
                    validation_run_key=run_key,
                    source_code=source_code,
                    secrets=selected_secrets,
                )
            )
        except Exception as exc:
            observed_latency_ms = max(0, int((perf_counter() - started) * 1000))
            error_kind = type(exc).__name__
            record = persist_source_validation_record(
                session,
                SourceValidationRecordInput(
                    validation_run_key=run_key,
                    source_code=source_code,
                    is_available=False,
                    auth_required=(definition.secret_mode == _SECRET_MODE_REQUIRED),
                    quota_rate_limit_notes=f"probe_execution_error:{error_kind}",
                    speed_notes=f"probe_execution_error:{error_kind}",
                    exchange_coverage_notes="probe_execution_failed",
                    classification_verdict="reject",
                    assigned_role=None,
                    observed_latency_ms=observed_latency_ms,
                ),
            )
            results.append(
                LiveSourceProbeSourceResult(
                    source_code=source_code,
                    status="failed_probe_execution",
                    persisted_record_id=record.id,
                    classification_verdict=record.classification_verdict,
                    note=f"probe_execution_error:{error_kind}",
                )
            )
            continue

        resolved_latency_ms = payload.observed_latency_ms
        if resolved_latency_ms is None:
            resolved_latency_ms = max(0, int((perf_counter() - started) * 1000))
        record = persist_source_validation_record(
            session,
            SourceValidationRecordInput(
                validation_run_key=run_key,
                source_code=source_code,
                is_available=payload.is_available,
                auth_required=(definition.secret_mode == _SECRET_MODE_REQUIRED),
                quota_rate_limit_notes=payload.quota_rate_limit_notes,
                speed_notes=payload.speed_notes,
                exchange_coverage_notes=payload.exchange_coverage_notes,
                classification_verdict=payload.classification_verdict,
                assigned_role=payload.assigned_role,
                observed_latency_ms=resolved_latency_ms,
            ),
        )
        results.append(
            LiveSourceProbeSourceResult(
                source_code=source_code,
                status="succeeded",
                persisted_record_id=record.id,
                classification_verdict=record.classification_verdict,
                note="probe_completed",
            )
        )

    session.flush()
    return LiveSourceProbeRunResult(validation_run_key=run_key, source_results=results)


def _normalize_selected_sources(source_codes: list[str]) -> list[str]:
    normalized: list[str] = []
    for source_code in source_codes:
        candidate = source_code.strip().upper()
        if not candidate:
            continue
        if candidate not in normalized:
            normalized.append(candidate)
    if not normalized:
        raise ValueError("source_codes must include at least one source code")
    return normalized


def _normalize_run_key(validation_run_key: str | None) -> str:
    if validation_run_key is None:
        return f"source-probe-run-{uuid4().hex}"
    normalized = validation_run_key.strip()
    if not normalized:
        raise ValueError("validation_run_key must be a non-empty string when provided")
    return normalized


def _normalize_registry(
    probe_registry: Mapping[str, LiveSourceProbeDefinition],
) -> dict[str, LiveSourceProbeDefinition]:
    normalized: dict[str, LiveSourceProbeDefinition] = {}
    for source_code, definition in probe_registry.items():
        normalized_code = source_code.strip().upper()
        if not normalized_code:
            raise ValueError("probe_registry contains an empty source code key")
        if definition.secret_mode not in _ALLOWED_SECRET_MODES:
            raise ValueError(
                f"probe_registry source {normalized_code} uses unsupported secret_mode={definition.secret_mode!r}"
            )
        normalized[normalized_code] = LiveSourceProbeDefinition(
            source_code=normalized_code,
            probe=definition.probe,
            secret_mode=definition.secret_mode,
            secret_env_vars=tuple(value.strip() for value in definition.secret_env_vars if value.strip()),
        )
    return normalized


def _resolve_secrets(
    *,
    definition: LiveSourceProbeDefinition,
    env: Mapping[str, str],
) -> tuple[list[str], dict[str, str]]:
    if definition.secret_mode == _SECRET_MODE_NONE:
        return [], {}

    secret_env_vars = definition.secret_env_vars
    if not secret_env_vars:
        secret_env_vars = default_source_probe_secret_env_vars(definition.source_code)

    missing: list[str] = []
    resolved: dict[str, str] = {}
    for env_var in secret_env_vars:
        value = env.get(env_var)
        if value is None or not value.strip():
            missing.append(env_var)
            continue
        resolved[env_var] = value
    return missing, resolved
