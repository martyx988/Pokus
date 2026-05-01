from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
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
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_provider_attempt_latency_nonnegative"),
        CheckConstraint(
            "result_status IN ('success','timeout','error','rate_limited')",
            name="ck_provider_attempt_result_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("provider.id"), nullable=False)
    exchange_id: Mapped[int] = mapped_column(ForeignKey("exchange.id"), nullable=False)
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
