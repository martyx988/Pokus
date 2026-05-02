from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pokus_backend.domain.reference_models import Base


class SourceValidationVerdict(StrEnum):
    PROMOTE = "promote"
    FALLBACK_ONLY = "fallback_only"
    VALIDATION_ONLY = "validation_only"
    NOT_FOR_UNIVERSE_LOADER = "not_for_universe_loader"
    REJECT = "reject"


class SourceValidationRole(StrEnum):
    PRIMARY_DISCOVERY = "primary_discovery"
    METADATA_ENRICHMENT = "metadata_enrichment"
    SYMBOLOGY_NORMALIZATION = "symbology_normalization"
    FALLBACK_DISCOVERY = "fallback_discovery"
    VALIDATION_ONLY = "validation_only"
    NOT_FOR_UNIVERSE_LOADER = "not_for_universe_loader"


class SourceValidationRecord(Base):
    __tablename__ = "source_validation_record"
    __table_args__ = (
        CheckConstraint("length(trim(validation_run_key)) > 0", name="ck_source_validation_record_run_key_nonempty"),
        CheckConstraint("source_code = upper(source_code)", name="ck_source_validation_record_source_code_upper"),
        CheckConstraint("length(trim(source_code)) > 0", name="ck_source_validation_record_source_code_nonempty"),
        CheckConstraint("length(trim(quota_rate_limit_notes)) > 0", name="ck_source_validation_record_quota_notes_nonempty"),
        CheckConstraint("length(trim(speed_notes)) > 0", name="ck_source_validation_record_speed_notes_nonempty"),
        CheckConstraint(
            "length(trim(exchange_coverage_notes)) > 0",
            name="ck_source_validation_record_exchange_notes_nonempty",
        ),
        CheckConstraint(
            "classification_verdict IN ('promote','fallback_only','validation_only','not_for_universe_loader','reject')",
            name="ck_source_validation_record_classification_verdict",
        ),
        CheckConstraint(
            "assigned_role IS NULL OR assigned_role IN "
            "('primary_discovery','metadata_enrichment','symbology_normalization',"
            "'fallback_discovery','validation_only','not_for_universe_loader')",
            name="ck_source_validation_record_assigned_role",
        ),
        CheckConstraint(
            "observed_latency_ms IS NULL OR observed_latency_ms >= 0",
            name="ck_source_validation_record_latency_nonnegative",
        ),
        UniqueConstraint(
            "validation_run_key",
            "source_code",
            name="uq_source_validation_record_run_source",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    validation_run_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_code: Mapped[str] = mapped_column(String(64), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    auth_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quota_rate_limit_notes: Mapped[str] = mapped_column(Text, nullable=False)
    speed_notes: Mapped[str] = mapped_column(Text, nullable=False)
    exchange_coverage_notes: Mapped[str] = mapped_column(Text, nullable=False)
    observed_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classification_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
