from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.reference_models import (
    Exchange,
    ValidationExchangeReport,
    ValidationRun,
    ValidationRunState,
    ValidationVerdict,
)
from pokus_backend.validation.calendar_validation_metrics import populate_calendar_validation_metrics
from pokus_backend.validation.completeness_timeliness_metrics import populate_completeness_timeliness_metrics
from pokus_backend.validation.disagreement_benchmark_metrics import populate_disagreement_benchmark_metrics
from pokus_backend.validation.discovery_listing_metrics import populate_discovery_listing_metrics

_VALIDATION_BUCKET_KEYS = (
    "discovery_listing",
    "completeness_timeliness",
    "disagreement_benchmark",
    "calendar_validation",
)


@dataclass(frozen=True, slots=True)
class ValidationRunExecutionResult:
    run: ValidationRun
    reports: list[ValidationExchangeReport]


def orchestrate_launch_exchange_validation_run(
    session: Session,
    *,
    target_exchange_codes: list[str],
    run_key: str | None = None,
    fail_reason: str | None = None,
) -> ValidationRunExecutionResult:
    run, reports = _create_or_get_run_shell(
        session=session,
        target_exchange_codes=target_exchange_codes,
        run_key=run_key,
    )
    if run.state in {ValidationRunState.SUCCEEDED.value, ValidationRunState.FAILED.value}:
        return ValidationRunExecutionResult(run=run, reports=reports)

    now = datetime.now(timezone.utc)
    run.state = ValidationRunState.RUNNING.value
    run.started_at = now
    run.updated_at = now
    session.flush()

    terminal_time = datetime.now(timezone.utc)
    if fail_reason is not None:
        run.state = ValidationRunState.FAILED.value
        run.failure_reason = fail_reason.strip() or "validation run failed"
    else:
        populate_discovery_listing_metrics(session, reports=reports)
        populate_completeness_timeliness_metrics(session, reports=reports)
        populate_disagreement_benchmark_metrics(session, reports=reports)
        populate_calendar_validation_metrics(session, reports=reports)
        _finalize_exchange_report_verdicts(reports)
        run.state = ValidationRunState.SUCCEEDED.value
        run.failure_reason = None
    run.finished_at = terminal_time
    run.updated_at = terminal_time
    session.flush()
    return ValidationRunExecutionResult(run=run, reports=reports)


def _create_or_get_run_shell(
    *,
    session: Session,
    target_exchange_codes: list[str],
    run_key: str | None,
) -> tuple[ValidationRun, list[ValidationExchangeReport]]:
    normalized_exchange_codes = _normalize_exchange_codes(target_exchange_codes)
    normalized_run_key = (run_key.strip() if run_key is not None else f"validation-run-{uuid4().hex}")
    if not normalized_run_key:
        raise ValueError("run_key must be a non-empty string")

    existing = session.scalar(select(ValidationRun).where(ValidationRun.run_key == normalized_run_key))
    if existing is not None:
        reports = list(
            session.scalars(
                select(ValidationExchangeReport).where(ValidationExchangeReport.validation_run_id == existing.id)
            )
        )
        return existing, reports

    exchanges = _get_exchanges_by_codes(session=session, exchange_codes=normalized_exchange_codes)
    now = datetime.now(timezone.utc)
    run = ValidationRun(
        run_key=normalized_run_key,
        state=ValidationRunState.QUEUED.value,
        requested_exchange_codes=normalized_exchange_codes,
        started_at=None,
        finished_at=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    session.flush()

    reports: list[ValidationExchangeReport] = []
    for exchange in exchanges:
        report = ValidationExchangeReport(
            validation_run_id=run.id,
            exchange_id=exchange.id,
            final_verdict=ValidationVerdict.PENDING.value,
            result_buckets=_build_result_bucket_shell(),
            findings_summary=None,
            created_at=now,
            updated_at=now,
        )
        session.add(report)
        reports.append(report)
    session.flush()
    return run, reports


def _normalize_exchange_codes(exchange_codes: list[str]) -> list[str]:
    normalized: list[str] = []
    for code in exchange_codes:
        value = code.strip().upper()
        if not value:
            continue
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("target_exchange_codes must include at least one exchange code")
    return normalized


def _get_exchanges_by_codes(*, session: Session, exchange_codes: list[str]) -> list[Exchange]:
    exchanges = list(session.scalars(select(Exchange).where(Exchange.code.in_(exchange_codes))))
    exchange_ids_by_code = {exchange.code: exchange for exchange in exchanges}
    missing = [code for code in exchange_codes if code not in exchange_ids_by_code]
    if missing:
        raise ValueError(f"unknown exchange code(s): {', '.join(missing)}")
    return [exchange_ids_by_code[code] for code in exchange_codes]


def _build_result_bucket_shell() -> dict[str, object]:
    return {
        "discovery_listing": {"status": "pending", "findings": []},
        "completeness_timeliness": {"status": "pending", "findings": []},
        "disagreement_benchmark": {"status": "pending", "findings": []},
        "calendar_validation": {"status": "pending", "findings": []},
    }


def _finalize_exchange_report_verdicts(reports: list[ValidationExchangeReport]) -> None:
    for report in reports:
        failed_buckets: list[str] = []
        findings: list[str] = []
        for bucket_key in _VALIDATION_BUCKET_KEYS:
            bucket = report.result_buckets.get(bucket_key, {})
            if bucket.get("status") != "pass":
                failed_buckets.append(bucket_key)
                bucket_findings = bucket.get("findings", [])
                if isinstance(bucket_findings, list):
                    findings.extend(str(finding) for finding in bucket_findings)

        if not failed_buckets:
            report.final_verdict = ValidationVerdict.PASS.value
            report.findings_summary = "All launch-validation buckets passed."
            continue

        unique_findings = sorted({finding for finding in findings if finding})
        failed_list = ", ".join(failed_buckets)
        finding_list = ", ".join(unique_findings) if unique_findings else "no explicit finding codes"
        if report.exchange.code == "PSE":
            report.final_verdict = ValidationVerdict.BLOCKED.value
            report.findings_summary = (
                "PSE launch validation blocked; PSE must remain in launch scope. "
                f"Failed buckets: {failed_list}. Findings: {finding_list}. "
                "Action: iterate on source discovery, provider combination, adapter behavior, or validation strategy."
            )
            continue

        report.final_verdict = ValidationVerdict.FAIL.value
        report.findings_summary = (
            f"Launch validation failed for {report.exchange.code}. "
            f"Failed buckets: {failed_list}. Findings: {finding_list}."
        )
