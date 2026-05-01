from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pokus_backend.domain.reference_models import Base

load_jobs_table = Table(
    "load_jobs",
    Base.metadata,
    Column("id", BigInteger(), primary_key=True),
    Column("idempotency_key", Text(), nullable=True),
    Column("state", Text(), nullable=True),
    Column("attempt_count", Integer(), nullable=False, server_default=sa.text("0")),
    Column("max_attempts", Integer(), nullable=False, server_default=sa.text("3")),
    Column("request_timeout_seconds", Integer(), nullable=False, server_default=sa.text("30")),
    Column("next_retry_at", DateTime(timezone=True), nullable=True),
    Column("lock_token", Text(), nullable=True),
    Column("lock_acquired_at", DateTime(timezone=True), nullable=True),
    Column("lock_expires_at", DateTime(timezone=True), nullable=True),
    Column("heartbeat_at", DateTime(timezone=True), nullable=True),
    Column("stale_abandoned_at", DateTime(timezone=True), nullable=True),
    Column("last_error", Text(), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    Column("updated_at", DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    CheckConstraint(
        "state IN ('queued','running','retry_wait','succeeded','failed','cancelled','stale_abandoned')",
        name="ck_load_jobs_state",
    ),
    CheckConstraint("attempt_count >= 0", name="ck_load_jobs_attempt_count_nonnegative"),
    CheckConstraint("max_attempts >= 0", name="ck_load_jobs_max_attempts_nonnegative"),
    CheckConstraint(
        "request_timeout_seconds > 0",
        name="ck_load_jobs_request_timeout_positive",
    ),
)


class ExchangeDayLoad(Base):
    __tablename__ = "exchange_day_load"
    __table_args__ = (
        CheckConstraint(
            "load_type IN ('daily_open','historical_close')",
            name="ck_exchange_day_load_load_type",
        ),
        CheckConstraint(
            "status IN ('not_started','in_progress','market_closed','partial_problematic','ready','failed')",
            name="ck_exchange_day_load_status",
        ),
        CheckConstraint(
            "eligible_instrument_count >= 0",
            name="ck_exchange_day_load_eligible_count_nonnegative",
        ),
        CheckConstraint(
            "succeeded_count >= 0",
            name="ck_exchange_day_load_succeeded_count_nonnegative",
        ),
        CheckConstraint(
            "failed_count >= 0",
            name="ck_exchange_day_load_failed_count_nonnegative",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_exchange_day_load_duration_nonnegative",
        ),
        UniqueConstraint(
            "exchange_id",
            "trading_date",
            "load_type",
            name="uq_exchange_day_load_exchange_date_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exchange_id: Mapped[int] = mapped_column(ForeignKey("exchange.id"), nullable=False)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("load_jobs.id"), nullable=True)
    trading_date: Mapped[date] = mapped_column(Date(), nullable=False)
    load_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    eligible_instrument_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    succeeded_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer(), nullable=True)


class InstrumentLoadOutcome(Base):
    __tablename__ = "instrument_load_outcome"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('pending','in_progress','succeeded','failed','cancelled')",
            name="ck_instrument_load_outcome_outcome",
        ),
        CheckConstraint(
            "outcome_class IN ('success','missing','stale','halted','suspended','late_open','provider_failed')",
            name="ck_instrument_load_outcome_outcome_class",
        ),
        UniqueConstraint(
            "exchange_day_load_id",
            "listing_id",
            name="uq_instrument_load_outcome_exchange_day_load_listing",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exchange_day_load_id: Mapped[int] = mapped_column(
        ForeignKey("exchange_day_load.id"),
        nullable=False,
    )
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"), nullable=False)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("load_jobs.id"), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    outcome_class: Mapped[str] = mapped_column(String(32), nullable=False, default="missing")
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
