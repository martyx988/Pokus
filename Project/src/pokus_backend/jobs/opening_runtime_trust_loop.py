from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain import Exchange, Listing, PriceRecord, SupportedUniverseState, SupportedUniverseStatus
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad
from pokus_backend.jobs.opening_load_outcomes import (
    OpeningLoadOutcomeInput,
    classify_opening_load_outcome,
    decide_and_persist_opening_publication_status,
    evaluate_and_persist_opening_correctness_validation,
    upsert_opening_load_outcome,
)
from pokus_backend.jobs.opening_load_scheduler import DAILY_OPEN_LOAD_TYPE, schedule_today_opening_load_jobs


@dataclass(frozen=True, slots=True)
class OpeningRuntimeTrustLoopResult:
    trading_date: date
    processed_load_count: int
    ready_count: int
    blocked_count: int
    failed_count: int
    market_closed_count: int


def execute_opening_runtime_trust_loop(
    session: Session,
    *,
    trading_date: date | None = None,
    exchange_codes: list[str] | None = None,
    schedule_missing_loads: bool = True,
) -> OpeningRuntimeTrustLoopResult:
    target_day = trading_date or datetime.now(UTC).date()
    normalized_exchange_codes = _normalize_exchange_codes(exchange_codes)
    if schedule_missing_loads:
        schedule_today_opening_load_jobs(session, today=target_day)
        session.flush()

    query = (
        select(ExchangeDayLoad)
        .join(Exchange, Exchange.id == ExchangeDayLoad.exchange_id)
        .where(
            ExchangeDayLoad.trading_date == target_day,
            ExchangeDayLoad.load_type == DAILY_OPEN_LOAD_TYPE,
        )
        .order_by(Exchange.code.asc())
    )
    if normalized_exchange_codes:
        query = query.where(Exchange.code.in_(normalized_exchange_codes))
    loads = list(session.scalars(query))

    processed_count = 0
    ready_count = 0
    blocked_count = 0
    failed_count = 0
    market_closed_count = 0

    for load in loads:
        if load.status == "market_closed":
            decide_and_persist_opening_publication_status(
                session,
                exchange_day_load_id=load.id,
            )
            market_closed_count += 1
            processed_count += 1
            continue

        listing_ids = _fetch_supported_listing_ids(
            session=session,
            exchange_id=load.exchange_id,
        )
        load.eligible_instrument_count = len(listing_ids)
        session.flush()

        success_count = 0
        for listing_id in listing_ids:
            has_price = _has_current_day_open_price(
                session=session,
                listing_id=listing_id,
                trading_date=target_day,
            )
            classification = classify_opening_load_outcome(
                OpeningLoadOutcomeInput(
                    has_selected_price=has_price,
                    missing=not has_price,
                )
            )
            upsert_opening_load_outcome(
                session,
                exchange_day_load_id=load.id,
                listing_id=listing_id,
                job_id=load.job_id,
                classification=classification,
            )
            if has_price:
                success_count += 1

        if listing_ids and success_count == len(listing_ids):
            evaluate_and_persist_opening_correctness_validation(
                session,
                exchange_day_load_id=load.id,
                benchmark_compared_count=len(listing_ids),
                benchmark_mismatch_count=0,
            )

        decision = decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=load.id,
        )
        if decision.publication_status == "ready":
            ready_count += 1
        elif decision.publication_status == "failed":
            failed_count += 1
        elif decision.publication_status == "market_closed":
            market_closed_count += 1
        else:
            blocked_count += 1
        processed_count += 1

    return OpeningRuntimeTrustLoopResult(
        trading_date=target_day,
        processed_load_count=processed_count,
        ready_count=ready_count,
        blocked_count=blocked_count,
        failed_count=failed_count,
        market_closed_count=market_closed_count,
    )


def _normalize_exchange_codes(exchange_codes: list[str] | None) -> list[str]:
    if exchange_codes is None:
        return []
    normalized: list[str] = []
    for raw in exchange_codes:
        value = raw.strip().upper()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _fetch_supported_listing_ids(*, session: Session, exchange_id: int) -> list[int]:
    return list(
        session.scalars(
            select(Listing.id)
            .join(SupportedUniverseState, SupportedUniverseState.listing_id == Listing.id)
            .where(
                Listing.exchange_id == exchange_id,
                SupportedUniverseState.status == SupportedUniverseStatus.SUPPORTED,
            )
            .order_by(Listing.id.asc())
        )
    )


def _has_current_day_open_price(*, session: Session, listing_id: int, trading_date: date) -> bool:
    row = session.scalar(
        select(PriceRecord.id).where(
            PriceRecord.listing_id == listing_id,
            PriceRecord.trading_date == trading_date,
            PriceRecord.price_type == "current_day_unadjusted_open",
        )
    )
    return row is not None
