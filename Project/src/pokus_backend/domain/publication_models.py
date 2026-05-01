from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pokus_backend.domain.reference_models import Base


class PublicationRecord(Base):
    __tablename__ = "publication_record"
    __table_args__ = (
        CheckConstraint(
            "status IN ('unpublished','ready','blocked','failed','market_closed','published')",
            name="ck_publication_record_status",
        ),
        UniqueConstraint("exchange_day_load_id", name="uq_publication_record_exchange_day_load"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exchange_day_load_id: Mapped[int] = mapped_column(ForeignKey("exchange_day_load.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unpublished")
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QualityCheck(Base):
    __tablename__ = "quality_check"
    __table_args__ = (
        CheckConstraint(
            "coverage_percent >= 0 AND coverage_percent <= 100",
            name="ck_quality_check_coverage_percent_range",
        ),
        CheckConstraint(
            "eligible_count >= 0",
            name="ck_quality_check_eligible_count_nonnegative",
        ),
        CheckConstraint(
            "succeeded_count >= 0",
            name="ck_quality_check_succeeded_count_nonnegative",
        ),
        CheckConstraint(
            "failed_count >= 0",
            name="ck_quality_check_failed_count_nonnegative",
        ),
        CheckConstraint(
            "correctness_result IN ('pending','passed','failed')",
            name="ck_quality_check_correctness_result",
        ),
        CheckConstraint(
            "benchmark_mismatch_percent IS NULL OR "
            "(benchmark_mismatch_percent >= 0 AND benchmark_mismatch_percent <= 100)",
            name="ck_quality_check_benchmark_mismatch_percent_range",
        ),
        UniqueConstraint("exchange_day_load_id", name="uq_quality_check_exchange_day_load"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exchange_day_load_id: Mapped[int] = mapped_column(ForeignKey("exchange_day_load.id"), nullable=False)
    eligible_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    succeeded_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    coverage_percent: Mapped[float] = mapped_column(Float(), nullable=False)
    correctness_result: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    benchmark_mismatch_percent: Mapped[float | None] = mapped_column(Float(), nullable=True)
    benchmark_mismatch_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
