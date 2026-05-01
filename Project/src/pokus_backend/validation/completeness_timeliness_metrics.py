from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.instrument_models import CandidatePriceValue, Listing, SupportedUniverseState, SupportedUniverseStatus
from pokus_backend.domain.reference_models import ProviderAttempt, ValidationExchangeReport

_COMPLETENESS_THRESHOLD = 0.99
_TIMELINESS_TARGET_MS = 30 * 60 * 1000


@dataclass(frozen=True, slots=True)
class _AttemptRow:
    requested_at: datetime
    result_status: str
    latency_ms: int | None
    rate_limit_hit: bool
    stale_data: bool
    missing_values: bool


def populate_completeness_timeliness_metrics(
    session: Session,
    *,
    reports: list[ValidationExchangeReport],
) -> None:
    if not reports:
        return

    exchange_ids = [report.exchange_id for report in reports]
    supported_listing_ids_by_exchange = _load_supported_listing_ids(session=session, exchange_ids=exchange_ids)
    daily_listing_ids_by_exchange = _load_candidate_listing_ids(
        session=session,
        exchange_ids=exchange_ids,
        price_type="current_day_unadjusted_open",
    )
    historical_listing_ids_by_exchange = _load_candidate_listing_ids(
        session=session,
        exchange_ids=exchange_ids,
        price_type="historical_adjusted_close",
    )
    attempts_by_exchange = _load_attempts(session=session, exchange_ids=exchange_ids)

    now = datetime.now(timezone.utc)
    for report in reports:
        supported_listing_ids = supported_listing_ids_by_exchange.get(report.exchange_id, set())
        supported_count = len(supported_listing_ids)

        daily_covered_count = len(supported_listing_ids.intersection(daily_listing_ids_by_exchange.get(report.exchange_id, set())))
        historical_covered_count = len(
            supported_listing_ids.intersection(historical_listing_ids_by_exchange.get(report.exchange_id, set()))
        )

        daily_completeness_rate = _safe_rate(numerator=daily_covered_count, denominator=supported_count)
        historical_completeness_rate = _safe_rate(numerator=historical_covered_count, denominator=supported_count)
        daily_completeness_pass = supported_count > 0 and daily_completeness_rate > _COMPLETENESS_THRESHOLD
        historical_completeness_pass = supported_count > 0 and historical_completeness_rate > _COMPLETENESS_THRESHOLD

        attempts = attempts_by_exchange.get(report.exchange_id, [])
        sorted_attempts = sorted(attempts, key=lambda row: row.requested_at, reverse=True)
        recent_five_attempts = sorted_attempts[:5]
        timeliness_miss_count = sum(
            1
            for row in recent_five_attempts
            if row.result_status != "success" or row.latency_ms is None or row.latency_ms > _TIMELINESS_TARGET_MS
        )
        timeliness_pass = len(recent_five_attempts) > 0 and timeliness_miss_count < 3

        stale_or_missing_count = sum(1 for row in attempts if row.stale_data or row.missing_values)
        rate_limit_count = sum(1 for row in attempts if row.rate_limit_hit or row.result_status == "rate_limited")
        stale_missing_pass = stale_or_missing_count == 0
        rate_limit_pass = rate_limit_count == 0

        findings: list[str] = []
        if not daily_completeness_pass:
            findings.append("daily_completeness_threshold_not_met")
        if not historical_completeness_pass:
            findings.append("historical_completeness_threshold_not_met")
        if not timeliness_pass:
            findings.append("timeliness_threshold_not_met")
        if not stale_missing_pass:
            findings.append("stale_or_missing_data_detected")
        if not rate_limit_pass:
            findings.append("rate_limit_behavior_detected")

        bucket = {
            "status": (
                "pass"
                if daily_completeness_pass
                and historical_completeness_pass
                and timeliness_pass
                and stale_missing_pass
                and rate_limit_pass
                else "fail"
            ),
            "findings": findings,
            "evidence": {
                "daily_completeness": {
                    "supported_listing_count": supported_count,
                    "covered_listing_count": daily_covered_count,
                    "coverage_rate": daily_completeness_rate,
                    "threshold": _COMPLETENESS_THRESHOLD,
                    "pass": daily_completeness_pass,
                },
                "historical_completeness": {
                    "supported_listing_count": supported_count,
                    "covered_listing_count": historical_covered_count,
                    "coverage_rate": historical_completeness_rate,
                    "threshold": _COMPLETENESS_THRESHOLD,
                    "pass": historical_completeness_pass,
                },
                "timeliness": {
                    "target_minutes": 30,
                    "evaluated_attempt_count": len(recent_five_attempts),
                    "miss_count": timeliness_miss_count,
                    "degrade_threshold_misses_in_last_5": 3,
                    "pass": timeliness_pass,
                },
                "stale_missing_behavior": {
                    "attempt_count": len(attempts),
                    "stale_or_missing_count": stale_or_missing_count,
                    "pass": stale_missing_pass,
                },
                "rate_limit_behavior": {
                    "attempt_count": len(attempts),
                    "rate_limit_count": rate_limit_count,
                    "pass": rate_limit_pass,
                },
            },
        }
        report.result_buckets = {**report.result_buckets, "completeness_timeliness": bucket}
        report.updated_at = now


def _load_supported_listing_ids(*, session: Session, exchange_ids: list[int]) -> dict[int, set[int]]:
    rows = session.execute(
        select(Listing.exchange_id, Listing.id)
        .join(SupportedUniverseState, SupportedUniverseState.listing_id == Listing.id)
        .where(
            Listing.exchange_id.in_(tuple(exchange_ids)),
            SupportedUniverseState.status == SupportedUniverseStatus.SUPPORTED,
        )
    ).all()
    by_exchange: dict[int, set[int]] = {exchange_id: set() for exchange_id in exchange_ids}
    for exchange_id, listing_id in rows:
        by_exchange.setdefault(exchange_id, set()).add(listing_id)
    return by_exchange


def _load_candidate_listing_ids(*, session: Session, exchange_ids: list[int], price_type: str) -> dict[int, set[int]]:
    rows = session.execute(
        select(Listing.exchange_id, CandidatePriceValue.listing_id)
        .join(Listing, Listing.id == CandidatePriceValue.listing_id)
        .where(Listing.exchange_id.in_(tuple(exchange_ids)), CandidatePriceValue.price_type == price_type)
    ).all()
    by_exchange: dict[int, set[int]] = {exchange_id: set() for exchange_id in exchange_ids}
    for exchange_id, listing_id in rows:
        by_exchange.setdefault(exchange_id, set()).add(listing_id)
    return by_exchange


def _load_attempts(*, session: Session, exchange_ids: list[int]) -> dict[int, list[_AttemptRow]]:
    rows = session.execute(
        select(
            ProviderAttempt.exchange_id,
            ProviderAttempt.requested_at,
            ProviderAttempt.result_status,
            ProviderAttempt.latency_ms,
            ProviderAttempt.rate_limit_hit,
            ProviderAttempt.stale_data,
            ProviderAttempt.missing_values,
        ).where(ProviderAttempt.exchange_id.in_(tuple(exchange_ids)))
    ).all()
    by_exchange: dict[int, list[_AttemptRow]] = {exchange_id: [] for exchange_id in exchange_ids}
    for exchange_id, requested_at, result_status, latency_ms, rate_limit_hit, stale_data, missing_values in rows:
        by_exchange.setdefault(exchange_id, []).append(
            _AttemptRow(
                requested_at=requested_at,
                result_status=result_status,
                latency_ms=latency_ms,
                rate_limit_hit=rate_limit_hit,
                stale_data=stale_data,
                missing_values=missing_values,
            )
        )
    return by_exchange


def _safe_rate(*, numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
