from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.instrument_models import CandidatePriceValue, Listing
from pokus_backend.domain.reference_models import ValidationExchangeReport

_BENCHMARK_MISMATCH_THRESHOLD_PERCENT = Decimal("5")


@dataclass(frozen=True, slots=True)
class _CandidateRow:
    listing_id: int
    trading_date: date
    price_type: str
    value: Decimal
    candidate_key: str
    provider_attempt_id: int | None
    audit_metadata: dict[str, object] | None


def populate_disagreement_benchmark_metrics(
    session: Session,
    *,
    reports: list[ValidationExchangeReport],
) -> None:
    if not reports:
        return

    exchange_ids = [report.exchange_id for report in reports]
    rows_by_exchange = _load_candidates(session=session, exchange_ids=exchange_ids)
    now = datetime.now(timezone.utc)

    for report in reports:
        rows = rows_by_exchange.get(report.exchange_id, [])
        grouped: dict[tuple[int, date, str], list[_CandidateRow]] = {}
        for row in rows:
            grouped.setdefault((row.listing_id, row.trading_date, row.price_type), []).append(row)

        compared_datums = 0
        disagreement_count = 0
        benchmark_compared_count = 0
        benchmark_mismatch_count = 0
        evidence_refs: list[dict[str, object]] = []

        for datum_key, datum_rows in grouped.items():
            distinct_values = {row.value for row in datum_rows}
            if len(datum_rows) > 1:
                compared_datums += 1
                if len(distinct_values) > 1:
                    disagreement_count += 1

            benchmark = _extract_benchmark_value(datum_rows)
            if benchmark is None:
                continue
            benchmark_compared_count += 1
            if benchmark not in distinct_values:
                benchmark_mismatch_count += 1
                listing_id, trading_day, price_type = datum_key
                evidence_refs.append(
                    {
                        "listing_id": listing_id,
                        "trading_date": trading_day.isoformat(),
                        "price_type": price_type,
                        "benchmark_value": str(benchmark),
                        "candidate_values": [str(value) for value in sorted(distinct_values)],
                        "candidate_keys": [row.candidate_key for row in datum_rows],
                        "provider_attempt_ids": [row.provider_attempt_id for row in datum_rows if row.provider_attempt_id is not None],
                    }
                )

        disagreement_rate = _safe_rate(disagreement_count, compared_datums)
        benchmark_mismatch_percent = _safe_percent(benchmark_mismatch_count, benchmark_compared_count)
        benchmark_pass = benchmark_compared_count > 0 and benchmark_mismatch_percent <= _BENCHMARK_MISMATCH_THRESHOLD_PERCENT

        findings: list[str] = []
        if compared_datums == 0:
            findings.append("insufficient_multi_provider_comparisons")
        if disagreement_count > 0:
            findings.append("provider_disagreement_detected")
        if benchmark_compared_count == 0:
            findings.append("benchmark_sample_missing")
        elif not benchmark_pass:
            findings.append("benchmark_mismatch_threshold_not_met")

        bucket = {
            "status": "pass" if benchmark_pass else "fail",
            "findings": findings,
            "evidence": {
                "disagreement_frequency": {
                    "compared_datum_count": compared_datums,
                    "disagreement_count": disagreement_count,
                    "disagreement_rate": disagreement_rate,
                },
                "benchmark_match": {
                    "compared_benchmark_count": benchmark_compared_count,
                    "mismatch_count": benchmark_mismatch_count,
                    "mismatch_percent": float(benchmark_mismatch_percent),
                    "threshold_percent": float(_BENCHMARK_MISMATCH_THRESHOLD_PERCENT),
                    "pass": benchmark_pass,
                    "mismatch_evidence_refs": evidence_refs,
                },
            },
        }
        report.result_buckets = {**report.result_buckets, "disagreement_benchmark": bucket}
        report.updated_at = now


def _load_candidates(*, session: Session, exchange_ids: list[int]) -> dict[int, list[_CandidateRow]]:
    rows = session.execute(
        select(
            Listing.exchange_id,
            CandidatePriceValue.listing_id,
            CandidatePriceValue.trading_date,
            CandidatePriceValue.price_type,
            CandidatePriceValue.value,
            CandidatePriceValue.candidate_key,
            CandidatePriceValue.provider_attempt_id,
            CandidatePriceValue.audit_metadata,
        )
        .join(Listing, Listing.id == CandidatePriceValue.listing_id)
        .where(Listing.exchange_id.in_(tuple(exchange_ids)))
    ).all()

    by_exchange: dict[int, list[_CandidateRow]] = {exchange_id: [] for exchange_id in exchange_ids}
    for exchange_id, listing_id, trading_date, price_type, value, candidate_key, provider_attempt_id, audit_metadata in rows:
        by_exchange.setdefault(exchange_id, []).append(
            _CandidateRow(
                listing_id=listing_id,
                trading_date=trading_date,
                price_type=price_type,
                value=Decimal(str(value)),
                candidate_key=candidate_key,
                provider_attempt_id=provider_attempt_id,
                audit_metadata=audit_metadata if isinstance(audit_metadata, dict) else None,
            )
        )
    return by_exchange


def _extract_benchmark_value(rows: list[_CandidateRow]) -> Decimal | None:
    for row in rows:
        metadata = row.audit_metadata or {}
        selection_inputs = metadata.get("selection_inputs")
        if not isinstance(selection_inputs, dict):
            continue
        raw = selection_inputs.get("benchmark_value")
        if raw is None:
            continue
        try:
            return Decimal(str(raw))
        except (InvalidOperation, ValueError):
            continue
    return None


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _safe_percent(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("100")
    return (Decimal(numerator) * Decimal("100")) / Decimal(denominator)
