from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.instrument_models import Listing, SupportedUniverseState, SupportedUniverseStatus
from pokus_backend.domain.reference_models import Exchange, ValidationExchangeReport


@dataclass(frozen=True, slots=True)
class _ListingRow:
    instrument_id: int
    exchange_id: int
    exchange_code: str
    exchange_priority_rank: int
    is_supported: bool


def populate_discovery_listing_metrics(
    session: Session,
    *,
    reports: list[ValidationExchangeReport],
) -> None:
    if not reports:
        return

    exchange_ids = [report.exchange_id for report in reports]
    listing_rows = _load_listing_rows(session=session, exchange_ids=exchange_ids)

    by_exchange_id: dict[int, list[_ListingRow]] = {exchange_id: [] for exchange_id in exchange_ids}
    for row in listing_rows:
        by_exchange_id.setdefault(row.exchange_id, []).append(row)

    grouped_by_instrument: dict[int, list[_ListingRow]] = {}
    for row in listing_rows:
        grouped_by_instrument.setdefault(row.instrument_id, []).append(row)

    multi_exchange_instruments = {
        instrument_id
        for instrument_id, rows in grouped_by_instrument.items()
        if len({row.exchange_id for row in rows}) > 1
    }

    conflicting_supported_instruments = {
        instrument_id: rows
        for instrument_id, rows in grouped_by_instrument.items()
        if sum(1 for row in rows if row.is_supported) > 1
    }

    now = datetime.now(timezone.utc)
    for report in reports:
        exchange_rows = by_exchange_id.get(report.exchange_id, [])
        supported_rows = [row for row in exchange_rows if row.is_supported]
        discovery_listing_count = len(exchange_rows)
        supported_listing_count = len(supported_rows)
        discovery_quality_pass = discovery_listing_count > 0 and supported_listing_count > 0

        selected_priority_violations = 0
        checked_multi_exchange_instrument_count = 0
        conflicting_instruments_for_exchange = 0

        for row in supported_rows:
            peer_rows = grouped_by_instrument.get(row.instrument_id, [])
            if row.instrument_id in conflicting_supported_instruments:
                conflicting_instruments_for_exchange += 1
            if row.instrument_id not in multi_exchange_instruments:
                continue
            checked_multi_exchange_instrument_count += 1
            best_rank = min(peer.exchange_priority_rank for peer in peer_rows)
            if row.exchange_priority_rank > best_rank:
                selected_priority_violations += 1

        primary_listing_pass = (
            conflicting_instruments_for_exchange == 0 and selected_priority_violations == 0
        )

        findings: list[str] = []
        if not discovery_quality_pass:
            findings.append("discovery_quality_threshold_not_met")
        if conflicting_instruments_for_exchange > 0:
            findings.append("multiple_supported_listings_for_same_instrument")
        if selected_priority_violations > 0:
            findings.append("supported_listing_priority_order_violation")

        discovery_listing_bucket = {
            "status": "pass" if discovery_quality_pass and primary_listing_pass else "fail",
            "findings": findings,
            "evidence": {
                "discovery_quality": {
                    "discovered_listing_count": discovery_listing_count,
                    "supported_listing_count": supported_listing_count,
                    "pass": discovery_quality_pass,
                },
                "primary_listing_behavior": {
                    "checked_multi_exchange_instrument_count": checked_multi_exchange_instrument_count,
                    "conflicting_supported_instrument_count": conflicting_instruments_for_exchange,
                    "priority_order_violation_count": selected_priority_violations,
                    "pass": primary_listing_pass,
                },
            },
        }
        report.result_buckets = {**report.result_buckets, "discovery_listing": discovery_listing_bucket}
        report.updated_at = now


def _load_listing_rows(session: Session, *, exchange_ids: list[int]) -> list[_ListingRow]:
    rows = session.execute(
        select(
            Listing.instrument_id,
            Listing.exchange_id,
            Exchange.code,
            Exchange.activity_priority_rank,
            SupportedUniverseState.status,
        )
        .join(Exchange, Exchange.id == Listing.exchange_id)
        .outerjoin(SupportedUniverseState, SupportedUniverseState.listing_id == Listing.id)
        .where(Listing.exchange_id.in_(tuple(exchange_ids)))
    ).all()

    listing_rows: list[_ListingRow] = []
    for instrument_id, exchange_id, exchange_code, exchange_priority_rank, support_status in rows:
        listing_rows.append(
            _ListingRow(
                instrument_id=instrument_id,
                exchange_id=exchange_id,
                exchange_code=exchange_code,
                exchange_priority_rank=exchange_priority_rank,
                is_supported=(support_status == SupportedUniverseStatus.SUPPORTED),
            )
        )
    return listing_rows
