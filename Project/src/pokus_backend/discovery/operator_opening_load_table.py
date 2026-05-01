from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pokus_backend.db import to_sqlalchemy_url
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad, InstrumentLoadOutcome
from pokus_backend.domain.publication_models import PublicationRecord, QualityCheck
from pokus_backend.domain.reference_models import Exchange


@dataclass(frozen=True, slots=True)
class OperatorTodayOpeningLoadRow:
    exchange: str
    trading_date: date
    status: str
    publication_status: str
    publication_available: bool
    start_time: datetime | None
    finish_time: datetime | None
    eligible_count: int
    success_count: int
    failure_count: int
    coverage_percent: float
    quality_result: str
    degraded: bool
    exception_count: int


def fetch_operator_today_opening_load_table(
    database_url: str,
    *,
    trading_date: date | None = None,
) -> list[OperatorTodayOpeningLoadRow]:
    target_date = trading_date or datetime.now(UTC).date()
    engine = create_engine(to_sqlalchemy_url(database_url))
    try:
        with Session(engine) as session:
            failure_exception_counts = (
                select(
                    InstrumentLoadOutcome.exchange_day_load_id.label("exchange_day_load_id"),
                    func.count(InstrumentLoadOutcome.id).label("failure_exception_count"),
                )
                .where(InstrumentLoadOutcome.failure_reason.is_not(None))
                .group_by(InstrumentLoadOutcome.exchange_day_load_id)
                .subquery()
            )

            rows = session.execute(
                select(
                    Exchange.code.label("exchange"),
                    ExchangeDayLoad.trading_date,
                    ExchangeDayLoad.status,
                    ExchangeDayLoad.started_at,
                    ExchangeDayLoad.completed_at,
                    ExchangeDayLoad.eligible_instrument_count,
                    ExchangeDayLoad.succeeded_count,
                    ExchangeDayLoad.failed_count,
                    PublicationRecord.status.label("publication_status"),
                    QualityCheck.correctness_result,
                    QualityCheck.coverage_percent,
                    QualityCheck.publication_blocked_reason,
                    func.coalesce(failure_exception_counts.c.failure_exception_count, 0).label(
                        "failure_exception_count"
                    ),
                )
                .select_from(ExchangeDayLoad)
                .join(Exchange, Exchange.id == ExchangeDayLoad.exchange_id)
                .outerjoin(
                    PublicationRecord,
                    PublicationRecord.exchange_day_load_id == ExchangeDayLoad.id,
                )
                .outerjoin(
                    QualityCheck,
                    QualityCheck.exchange_day_load_id == ExchangeDayLoad.id,
                )
                .outerjoin(
                    failure_exception_counts,
                    failure_exception_counts.c.exchange_day_load_id == ExchangeDayLoad.id,
                )
                .where(
                    ExchangeDayLoad.load_type == "daily_open",
                    ExchangeDayLoad.trading_date == target_date,
                )
                .order_by(Exchange.code.asc())
            ).all()

        return [
            OperatorTodayOpeningLoadRow(
                exchange=str(row.exchange),
                trading_date=row.trading_date,
                status=str(row.status),
                publication_status=str(row.publication_status or "unpublished"),
                publication_available=row.publication_status == "ready",
                start_time=row.started_at,
                finish_time=row.completed_at,
                eligible_count=int(row.eligible_instrument_count or 0),
                success_count=int(row.succeeded_count or 0),
                failure_count=int(row.failed_count or 0),
                coverage_percent=_resolve_coverage_percent(
                    coverage_percent=row.coverage_percent,
                    success_count=int(row.succeeded_count or 0),
                    eligible_count=int(row.eligible_instrument_count or 0),
                    publication_status=str(row.publication_status or "unpublished"),
                ),
                quality_result=_resolve_quality_result(
                    correctness_result=row.correctness_result,
                    status=str(row.status),
                    publication_status=str(row.publication_status or "unpublished"),
                ),
                degraded=str(row.status) == "partial_problematic",
                exception_count=int(row.failure_exception_count or 0)
                + (1 if row.publication_blocked_reason else 0),
            )
            for row in rows
        ]
    finally:
        engine.dispose()


def _resolve_coverage_percent(
    *,
    coverage_percent: float | None,
    success_count: int,
    eligible_count: int,
    publication_status: str,
) -> float:
    if coverage_percent is not None:
        return float(coverage_percent)
    if publication_status == "market_closed" or eligible_count <= 0:
        return 0.0
    return (float(success_count) * 100.0) / float(eligible_count)


def _resolve_quality_result(
    *,
    correctness_result: str | None,
    status: str,
    publication_status: str,
) -> str:
    if correctness_result:
        return str(correctness_result)
    if publication_status == "market_closed":
        return "not_applicable"
    if status == "failed":
        return "failed"
    return "pending"
