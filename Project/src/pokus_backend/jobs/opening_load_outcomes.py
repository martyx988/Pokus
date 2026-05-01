from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from pokus_backend.domain.publication_models import PublicationRecord, QualityCheck
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad, InstrumentLoadOutcome
from pokus_backend.jobs.opening_read_model_refresh import refresh_publication_read_models


@dataclass(frozen=True, slots=True)
class OpeningLoadOutcomeInput:
    has_selected_price: bool
    missing: bool = False
    stale: bool = False
    halted: bool = False
    suspended: bool = False
    late_open: bool = False
    provider_failed: bool = False


@dataclass(frozen=True, slots=True)
class OpeningLoadOutcomeClassification:
    outcome: str
    outcome_class: str
    is_terminal: bool
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class PublicationTerminalCoveragePrecheck:
    eligible_count: int
    terminal_outcome_count: int
    covered_count: int
    coverage_percent: float
    has_all_terminal_outcomes: bool
    has_gt_99_coverage: bool


@dataclass(frozen=True, slots=True)
class OpeningCorrectnessValidationResult:
    benchmark_compared_count: int
    benchmark_mismatch_count: int
    benchmark_mismatch_percent: float | None
    correctness_result: str
    publication_blocked: bool
    publication_blocked_reason: str | None


@dataclass(frozen=True, slots=True)
class OpeningPublicationDecisionResult:
    publication_status: str
    is_ready: bool
    status_updated_at: datetime
    published_at: datetime | None


def classify_opening_load_outcome(payload: OpeningLoadOutcomeInput) -> OpeningLoadOutcomeClassification:
    if payload.has_selected_price:
        return OpeningLoadOutcomeClassification(
            outcome="succeeded",
            outcome_class="success",
            is_terminal=True,
            failure_reason=None,
        )
    if payload.halted:
        return OpeningLoadOutcomeClassification("pending", "halted", False, "halted")
    if payload.suspended:
        return OpeningLoadOutcomeClassification("pending", "suspended", False, "suspended")
    if payload.late_open:
        return OpeningLoadOutcomeClassification("pending", "late_open", False, "late_open")
    if payload.stale:
        return OpeningLoadOutcomeClassification("failed", "stale", True, "stale")
    if payload.provider_failed:
        return OpeningLoadOutcomeClassification("failed", "provider_failed", True, "provider_failed")
    return OpeningLoadOutcomeClassification("failed", "missing", True, "missing")


def upsert_opening_load_outcome(
    session: Session,
    *,
    exchange_day_load_id: int,
    listing_id: int,
    job_id: int | None,
    classification: OpeningLoadOutcomeClassification,
    occurred_at: datetime | None = None,
) -> InstrumentLoadOutcome:
    existing = session.scalar(
        select(InstrumentLoadOutcome).where(
            InstrumentLoadOutcome.exchange_day_load_id == exchange_day_load_id,
            InstrumentLoadOutcome.listing_id == listing_id,
        )
    )
    if existing is None:
        existing = InstrumentLoadOutcome(
            exchange_day_load_id=exchange_day_load_id,
            listing_id=listing_id,
        )
        session.add(existing)

    existing.job_id = job_id
    existing.outcome = classification.outcome
    existing.outcome_class = classification.outcome_class
    existing.is_terminal = classification.is_terminal
    existing.failure_reason = classification.failure_reason
    existing.updated_at = occurred_at.astimezone(timezone.utc) if occurred_at else datetime.now(timezone.utc)
    session.flush()
    refresh_exchange_day_opening_load_aggregate(
        session,
        exchange_day_load_id=exchange_day_load_id,
        occurred_at=existing.updated_at,
    )
    return existing


def refresh_exchange_day_opening_load_aggregate(
    session: Session,
    *,
    exchange_day_load_id: int,
    occurred_at: datetime | None = None,
) -> ExchangeDayLoad:
    exchange_day_load = session.scalar(
        select(ExchangeDayLoad).where(ExchangeDayLoad.id == exchange_day_load_id)
    )
    if exchange_day_load is None:
        raise ValueError(f"unknown exchange_day_load_id: {exchange_day_load_id}")

    aggregate = session.execute(
        select(
            func.count(InstrumentLoadOutcome.id).label("outcome_count"),
            func.sum(case((InstrumentLoadOutcome.outcome == "succeeded", 1), else_=0)).label("succeeded_count"),
            func.sum(case((InstrumentLoadOutcome.outcome == "failed", 1), else_=0)).label("failed_count"),
            func.min(InstrumentLoadOutcome.updated_at).label("first_outcome_at"),
        ).where(InstrumentLoadOutcome.exchange_day_load_id == exchange_day_load_id)
    ).one()

    outcome_count = int(aggregate.outcome_count or 0)
    succeeded_count = int(aggregate.succeeded_count or 0)
    failed_count = int(aggregate.failed_count or 0)
    first_outcome_at = aggregate.first_outcome_at
    eligible_count = int(exchange_day_load.eligible_instrument_count)
    terminal_count = succeeded_count + failed_count

    if terminal_count == 0 and outcome_count == 0:
        next_status = "not_started"
    elif terminal_count < eligible_count:
        next_status = "in_progress"
    elif failed_count == 0:
        next_status = "ready"
    elif succeeded_count == 0:
        next_status = "failed"
    else:
        next_status = "partial_problematic"

    now_utc = _as_utc(occurred_at) or datetime.now(timezone.utc)

    exchange_day_load.succeeded_count = succeeded_count
    exchange_day_load.failed_count = failed_count
    exchange_day_load.status = next_status

    if next_status == "not_started":
        exchange_day_load.started_at = None
        exchange_day_load.completed_at = None
        exchange_day_load.duration_seconds = None
    else:
        exchange_day_load.started_at = _as_utc(exchange_day_load.started_at) or _as_utc(first_outcome_at) or now_utc
        if next_status in {"ready", "failed", "partial_problematic"}:
            exchange_day_load.completed_at = now_utc
            exchange_day_load.duration_seconds = max(
                0,
                int((exchange_day_load.completed_at - exchange_day_load.started_at).total_seconds()),
            )
        else:
            exchange_day_load.completed_at = None
            exchange_day_load.duration_seconds = None

    session.flush()
    return exchange_day_load


def compute_publication_terminal_coverage_precheck(
    session: Session,
    *,
    exchange_day_load_id: int,
) -> PublicationTerminalCoveragePrecheck:
    exchange_day_load = session.scalar(
        select(ExchangeDayLoad).where(ExchangeDayLoad.id == exchange_day_load_id)
    )
    if exchange_day_load is None:
        raise ValueError(f"unknown exchange_day_load_id: {exchange_day_load_id}")

    eligible_count = int(exchange_day_load.eligible_instrument_count)
    terminal_outcome_count = _count_terminal_outcomes_for_exchange_day(
        session,
        exchange_day_load_id=exchange_day_load_id,
    )
    covered_count = _count_succeeded_outcomes_for_exchange_day(
        session,
        exchange_day_load_id=exchange_day_load_id,
    )
    coverage_percent = _calculate_coverage_percent(
        covered_count=covered_count,
        eligible_count=eligible_count,
    )
    has_all_terminal_outcomes = terminal_outcome_count >= eligible_count
    has_gt_99_coverage = coverage_percent > 99.0

    return PublicationTerminalCoveragePrecheck(
        eligible_count=eligible_count,
        terminal_outcome_count=terminal_outcome_count,
        covered_count=covered_count,
        coverage_percent=coverage_percent,
        has_all_terminal_outcomes=has_all_terminal_outcomes,
        has_gt_99_coverage=has_gt_99_coverage,
    )


def evaluate_and_persist_opening_correctness_validation(
    session: Session,
    *,
    exchange_day_load_id: int,
    benchmark_compared_count: int,
    benchmark_mismatch_count: int,
    validation_delayed: bool = False,
    validation_failed: bool = False,
    checked_at: datetime | None = None,
) -> OpeningCorrectnessValidationResult:
    if benchmark_compared_count < 0:
        raise ValueError("benchmark_compared_count must be >= 0")
    if benchmark_mismatch_count < 0:
        raise ValueError("benchmark_mismatch_count must be >= 0")
    if benchmark_mismatch_count > benchmark_compared_count:
        raise ValueError("benchmark_mismatch_count must be <= benchmark_compared_count")

    precheck = compute_publication_terminal_coverage_precheck(
        session,
        exchange_day_load_id=exchange_day_load_id,
    )
    mismatch_percent = (
        None
        if benchmark_compared_count == 0
        else (float(benchmark_mismatch_count) * 100.0) / float(benchmark_compared_count)
    )

    if validation_delayed:
        correctness_result = "pending"
        publication_blocked = True
        publication_blocked_reason = "correctness_validation_delayed"
    elif validation_failed:
        correctness_result = "failed"
        publication_blocked = True
        publication_blocked_reason = "correctness_validation_failed"
    elif mismatch_percent is None:
        correctness_result = "pending"
        publication_blocked = True
        publication_blocked_reason = "benchmark_sample_missing"
    elif mismatch_percent > 5.0:
        correctness_result = "failed"
        publication_blocked = True
        publication_blocked_reason = "benchmark_mismatch_threshold_exceeded"
    else:
        correctness_result = "passed"
        publication_blocked = False
        publication_blocked_reason = None

    quality_check = _get_or_create_quality_check(
        session,
        exchange_day_load_id=exchange_day_load_id,
        precheck=precheck,
        checked_at=checked_at,
    )
    quality_check.correctness_result = correctness_result
    quality_check.benchmark_mismatch_percent = mismatch_percent
    quality_check.benchmark_mismatch_summary = _build_benchmark_mismatch_summary(
        benchmark_compared_count=benchmark_compared_count,
        benchmark_mismatch_count=benchmark_mismatch_count,
        mismatch_percent=mismatch_percent,
        publication_blocked=publication_blocked,
        publication_blocked_reason=publication_blocked_reason,
    )
    quality_check.publication_blocked = publication_blocked
    quality_check.publication_blocked_reason = publication_blocked_reason
    quality_check.checked_at = _as_utc(checked_at) or datetime.now(timezone.utc)
    session.flush()

    return OpeningCorrectnessValidationResult(
        benchmark_compared_count=benchmark_compared_count,
        benchmark_mismatch_count=benchmark_mismatch_count,
        benchmark_mismatch_percent=mismatch_percent,
        correctness_result=correctness_result,
        publication_blocked=publication_blocked,
        publication_blocked_reason=publication_blocked_reason,
    )


def decide_and_persist_opening_publication_status(
    session: Session,
    *,
    exchange_day_load_id: int,
    decided_at: datetime | None = None,
) -> OpeningPublicationDecisionResult:
    exchange_day_load = session.scalar(
        select(ExchangeDayLoad).where(ExchangeDayLoad.id == exchange_day_load_id)
    )
    if exchange_day_load is None:
        raise ValueError(f"unknown exchange_day_load_id: {exchange_day_load_id}")

    quality_check = session.scalar(
        select(QualityCheck).where(QualityCheck.exchange_day_load_id == exchange_day_load_id)
    )
    precheck = compute_publication_terminal_coverage_precheck(
        session,
        exchange_day_load_id=exchange_day_load_id,
    )
    publication_status = _decide_publication_status(
        aggregate_status=exchange_day_load.status,
        precheck=precheck,
        quality_check=quality_check,
    )
    now_utc = _as_utc(decided_at) or datetime.now(timezone.utc)
    publication_record = _get_or_create_publication_record(
        session,
        exchange_day_load_id=exchange_day_load_id,
    )
    publication_record.status = publication_status
    publication_record.status_updated_at = now_utc
    publication_record.published_at = now_utc if publication_status == "ready" else None
    session.flush()
    refresh_publication_read_models(
        session,
        exchange_day_load_id=exchange_day_load_id,
    )

    return OpeningPublicationDecisionResult(
        publication_status=publication_status,
        is_ready=publication_status == "ready",
        status_updated_at=now_utc,
        published_at=publication_record.published_at,
    )


def _count_terminal_outcomes_for_exchange_day(
    session: Session,
    *,
    exchange_day_load_id: int,
) -> int:
    return int(
        session.scalar(
            select(func.count(InstrumentLoadOutcome.id)).where(
                InstrumentLoadOutcome.exchange_day_load_id == exchange_day_load_id,
                InstrumentLoadOutcome.is_terminal.is_(True),
            )
        )
        or 0
    )


def _count_succeeded_outcomes_for_exchange_day(
    session: Session,
    *,
    exchange_day_load_id: int,
) -> int:
    return int(
        session.scalar(
            select(func.count(InstrumentLoadOutcome.id)).where(
                InstrumentLoadOutcome.exchange_day_load_id == exchange_day_load_id,
                InstrumentLoadOutcome.outcome == "succeeded",
            )
        )
        or 0
    )


def _calculate_coverage_percent(*, covered_count: int, eligible_count: int) -> float:
    if eligible_count <= 0:
        return 0.0
    return (float(covered_count) * 100.0) / float(eligible_count)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_or_create_quality_check(
    session: Session,
    *,
    exchange_day_load_id: int,
    precheck: PublicationTerminalCoveragePrecheck,
    checked_at: datetime | None,
) -> QualityCheck:
    existing = session.scalar(
        select(QualityCheck).where(QualityCheck.exchange_day_load_id == exchange_day_load_id)
    )
    if existing is not None:
        return existing

    quality_check = QualityCheck(
        exchange_day_load_id=exchange_day_load_id,
        eligible_count=precheck.eligible_count,
        succeeded_count=precheck.covered_count,
        failed_count=max(0, precheck.terminal_outcome_count - precheck.covered_count),
        coverage_percent=precheck.coverage_percent,
        correctness_result="pending",
        checked_at=_as_utc(checked_at) or datetime.now(timezone.utc),
    )
    session.add(quality_check)
    session.flush()
    return quality_check


def _get_or_create_publication_record(
    session: Session,
    *,
    exchange_day_load_id: int,
) -> PublicationRecord:
    existing = session.scalar(
        select(PublicationRecord).where(PublicationRecord.exchange_day_load_id == exchange_day_load_id)
    )
    if existing is not None:
        return existing

    record = PublicationRecord(exchange_day_load_id=exchange_day_load_id, status="unpublished")
    session.add(record)
    session.flush()
    return record


def _decide_publication_status(
    *,
    aggregate_status: str,
    precheck: PublicationTerminalCoveragePrecheck,
    quality_check: QualityCheck | None,
) -> str:
    if aggregate_status == "market_closed":
        return "market_closed"
    if aggregate_status == "failed":
        return "failed"

    quality_passed = (
        quality_check is not None
        and quality_check.correctness_result == "passed"
        and not quality_check.publication_blocked
    )
    is_ready = (
        aggregate_status == "ready"
        and precheck.has_all_terminal_outcomes
        and precheck.has_gt_99_coverage
        and quality_passed
    )
    if is_ready:
        return "ready"
    return "blocked"


def _build_benchmark_mismatch_summary(
    *,
    benchmark_compared_count: int,
    benchmark_mismatch_count: int,
    mismatch_percent: float | None,
    publication_blocked: bool,
    publication_blocked_reason: str | None,
) -> str:
    if mismatch_percent is None:
        base = (
            f"Compared {benchmark_compared_count} benchmark instruments; "
            f"mismatches {benchmark_mismatch_count}."
        )
    else:
        base = (
            f"Compared {benchmark_compared_count} benchmark instruments; "
            f"mismatches {benchmark_mismatch_count} ({mismatch_percent:.4f}%)."
        )
    if publication_blocked and publication_blocked_reason:
        return f"{base} Publication blocked: {publication_blocked_reason}."
    return base
