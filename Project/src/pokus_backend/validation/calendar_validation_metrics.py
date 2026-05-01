from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.calendars.result import TradingDayStatus
from pokus_backend.calendars.service import build_launch_exchange_calendar_service
from pokus_backend.domain.instrument_models import CandidatePriceValue, Listing
from pokus_backend.domain.reference_models import ValidationExchangeReport


@dataclass(frozen=True, slots=True)
class _CalendarReferenceRow:
    trading_date: date
    expected_is_trading_day: bool
    reference_type: str | None
    reference_source: str | None
    candidate_key: str


def populate_calendar_validation_metrics(
    session: Session,
    *,
    reports: list[ValidationExchangeReport],
) -> None:
    if not reports:
        return

    calendar_service = build_launch_exchange_calendar_service()
    exchange_ids = [report.exchange_id for report in reports]
    refs_by_exchange = _load_calendar_references(session=session, exchange_ids=exchange_ids)

    now = datetime.now(timezone.utc)
    for report in reports:
        refs = refs_by_exchange.get(report.exchange_id, [])
        exchange_code = report.exchange.code
        matches = 0
        mismatches = 0
        unknown_calendar_count = 0
        mismatch_evidence: list[dict[str, object]] = []

        for ref in refs:
            decision = calendar_service.evaluate(exchange=exchange_code, local_date=ref.trading_date)
            if decision.status == TradingDayStatus.UNKNOWN_CALENDAR:
                unknown_calendar_count += 1
                mismatches += 1
                mismatch_evidence.append(
                    {
                        "trading_date": ref.trading_date.isoformat(),
                        "expected_is_trading_day": ref.expected_is_trading_day,
                        "library_is_trading_day": None,
                        "status": decision.status.value,
                        "reference_type": ref.reference_type,
                        "reference_source": ref.reference_source,
                        "candidate_key": ref.candidate_key,
                    }
                )
                continue

            library_is_trading_day = decision.status == TradingDayStatus.EXPECTED_TRADING_DAY
            if library_is_trading_day == ref.expected_is_trading_day:
                matches += 1
                continue

            mismatches += 1
            mismatch_evidence.append(
                {
                    "trading_date": ref.trading_date.isoformat(),
                    "expected_is_trading_day": ref.expected_is_trading_day,
                    "library_is_trading_day": library_is_trading_day,
                    "status": decision.status.value,
                    "calendar_id": decision.calendar_id,
                    "reference_type": ref.reference_type,
                    "reference_source": ref.reference_source,
                    "candidate_key": ref.candidate_key,
                }
            )

        compared_count = matches + mismatches
        decision_state = "library_acceptable" if compared_count > 0 and mismatches == 0 else "custom_adapter_required"

        findings: list[str] = []
        if compared_count == 0:
            findings.append("calendar_reference_inputs_missing")
        if mismatches > 0:
            findings.append("calendar_library_reference_mismatch_detected")
        if unknown_calendar_count > 0:
            findings.append("calendar_library_unavailable")

        validation_window_start = min((ref.trading_date for ref in refs), default=None)
        validation_window_end = max((ref.trading_date for ref in refs), default=None)

        bucket = {
            "status": "pass" if decision_state == "library_acceptable" else "fail",
            "findings": findings,
            "decision": {
                "state": decision_state,
                "custom_adapter_followup_required": decision_state == "custom_adapter_required",
            },
            "evidence": {
                "validation_window": {
                    "start": validation_window_start.isoformat() if validation_window_start is not None else None,
                    "end": validation_window_end.isoformat() if validation_window_end is not None else None,
                    "reference_input_count": len(refs),
                },
                "comparison": {
                    "compared_count": compared_count,
                    "match_count": matches,
                    "mismatch_count": mismatches,
                    "unknown_calendar_count": unknown_calendar_count,
                },
                "mismatch_evidence_refs": mismatch_evidence,
            },
        }
        report.result_buckets = {**report.result_buckets, "calendar_validation": bucket}
        report.updated_at = now


def _load_calendar_references(*, session: Session, exchange_ids: list[int]) -> dict[int, list[_CalendarReferenceRow]]:
    rows = session.execute(
        select(
            Listing.exchange_id,
            CandidatePriceValue.trading_date,
            CandidatePriceValue.audit_metadata,
            CandidatePriceValue.candidate_key,
        )
        .join(Listing, Listing.id == CandidatePriceValue.listing_id)
        .where(Listing.exchange_id.in_(tuple(exchange_ids)))
    ).all()

    refs_by_exchange: dict[int, list[_CalendarReferenceRow]] = {exchange_id: [] for exchange_id in exchange_ids}
    for exchange_id, trading_date, audit_metadata, candidate_key in rows:
        metadata = audit_metadata if isinstance(audit_metadata, dict) else {}
        selection_inputs = metadata.get("selection_inputs")
        if not isinstance(selection_inputs, dict):
            continue
        calendar_reference = selection_inputs.get("calendar_reference")
        if not isinstance(calendar_reference, dict):
            continue

        expected_is_trading_day = calendar_reference.get("expected_is_trading_day")
        if not isinstance(expected_is_trading_day, bool):
            continue

        refs_by_exchange.setdefault(exchange_id, []).append(
            _CalendarReferenceRow(
                trading_date=trading_date,
                expected_is_trading_day=expected_is_trading_day,
                reference_type=(
                    calendar_reference.get("reference_type")
                    if isinstance(calendar_reference.get("reference_type"), str)
                    else None
                ),
                reference_source=(
                    calendar_reference.get("reference_source")
                    if isinstance(calendar_reference.get("reference_source"), str)
                    else None
                ),
                candidate_key=candidate_key,
            )
        )

    return refs_by_exchange
