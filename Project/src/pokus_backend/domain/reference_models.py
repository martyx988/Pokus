from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Exchange(Base):
    __tablename__ = "exchange"
    __table_args__ = (
        CheckConstraint("code = upper(code)", name="ck_exchange_code_upper"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_launch_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activity_priority_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=9999)
    activity_priority_score: Mapped[float] = mapped_column(nullable=False, default=0.0)


class InstrumentType(Base):
    __tablename__ = "instrument_type"
    __table_args__ = (
        CheckConstraint("code = upper(code)", name="ck_instrument_type_code_upper"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_launch_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Provider(Base):
    __tablename__ = "provider"
    __table_args__ = (
        CheckConstraint("code = upper(code)", name="ck_provider_code_upper"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    attempts: Mapped[list["ProviderAttempt"]] = relationship(back_populates="provider")


class ProviderAttempt(Base):
    __tablename__ = "provider_attempt"
    __table_args__ = (
        CheckConstraint("length(trim(attempt_key)) > 0", name="ck_provider_attempt_attempt_key_nonempty"),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_provider_attempt_latency_nonnegative"),
        CheckConstraint(
            "result_status IN ('success','timeout','error','rate_limited')",
            name="ck_provider_attempt_result_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("provider.id"), nullable=False)
    exchange_id: Mapped[int] = mapped_column(ForeignKey("exchange.id"), nullable=False)
    attempt_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    request_purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    load_type: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_limit_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stale_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    missing_values: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    normalized_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSON, nullable=True)

    provider: Mapped[Provider] = relationship(back_populates="attempts")
    exchange: Mapped[Exchange] = relationship()


class ProviderExchangeReliabilityScore(Base):
    __tablename__ = "provider_exchange_reliability_score"
    __table_args__ = (
        CheckConstraint(
            "reliability_score >= 0 AND reliability_score <= 1",
            name="ck_provider_exchange_reliability_score_range",
        ),
        CheckConstraint(
            "observations_count >= 0",
            name="ck_provider_exchange_reliability_observations_nonnegative",
        ),
        CheckConstraint(
            "last_window_key IS NULL OR length(trim(last_window_key)) > 0",
            name="ck_provider_exchange_reliability_last_window_key_nonempty",
        ),
        UniqueConstraint(
            "provider_id",
            "exchange_id",
            name="uq_provider_exchange_reliability_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("provider.id"), nullable=False)
    exchange_id: Mapped[int] = mapped_column(ForeignKey("exchange.id"), nullable=False)
    reliability_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0.5)
    observations_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_window_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    provider: Mapped[Provider] = relationship()
    exchange: Mapped[Exchange] = relationship()


class ValidationRunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ValidationVerdict(StrEnum):
    PENDING = "pending"
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class ValidationRun(Base):
    __tablename__ = "validation_run"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued','running','succeeded','failed')",
            name="ck_validation_run_state",
        ),
        CheckConstraint("length(trim(run_key)) > 0", name="ck_validation_run_run_key_nonempty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default=ValidationRunState.QUEUED.value)
    requested_exchange_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    reports: Mapped[list["ValidationExchangeReport"]] = relationship(back_populates="run")


class ValidationExchangeReport(Base):
    __tablename__ = "validation_exchange_report"
    __table_args__ = (
        CheckConstraint(
            "final_verdict IN ('pending','pass','fail','blocked')",
            name="ck_validation_exchange_report_final_verdict",
        ),
        UniqueConstraint("validation_run_id", "exchange_id", name="uq_validation_exchange_report_run_exchange"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    validation_run_id: Mapped[int] = mapped_column(ForeignKey("validation_run.id"), nullable=False)
    exchange_id: Mapped[int] = mapped_column(ForeignKey("exchange.id"), nullable=False)
    final_verdict: Mapped[str] = mapped_column(String(32), nullable=False, default=ValidationVerdict.PENDING.value)
    result_buckets: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    findings_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run: Mapped[ValidationRun] = relationship(back_populates="reports")
    exchange: Mapped[Exchange] = relationship()
