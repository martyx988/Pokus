from __future__ import annotations

from sqlalchemy import CheckConstraint, Date, ForeignKey, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pokus_backend.domain.reference_models import Base


class SignalEvent(Base):
    __tablename__ = "signal_event"
    __table_args__ = (
        CheckConstraint(
            "signal_outcome IN ('signal','no_signal','insufficient_history')",
            name="ck_signal_event_signal_outcome",
        ),
        CheckConstraint(
            "signal_type IS NULL OR signal_type IN ('Dip','Skyrocket')",
            name="ck_signal_event_signal_type",
        ),
        CheckConstraint(
            "(signal_outcome = 'signal' AND signal_type IS NOT NULL) "
            "OR (signal_outcome IN ('no_signal','insufficient_history') AND signal_type IS NULL)",
            name="ck_signal_event_outcome_signal_type_match",
        ),
        UniqueConstraint(
            "listing_id",
            "trading_date",
            "algorithm_version",
            "signal_type",
            name="uq_signal_event_listing_date_algo_signal_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrument.id"), nullable=False)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"), nullable=False)
    trading_date: Mapped[Date] = mapped_column(Date, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm_context: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    signal_outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    signal_type: Mapped[str | None] = mapped_column(String(32), nullable=True)


class SignalStatistic(Base):
    __tablename__ = "signal_statistic"
    __table_args__ = (
        UniqueConstraint(
            "listing_id",
            "trading_date",
            "algorithm_version",
            "statistic_name",
            name="uq_signal_statistic_listing_date_algo_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrument.id"), nullable=False)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"), nullable=False)
    trading_date: Mapped[Date] = mapped_column(Date, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    statistic_name: Mapped[str] = mapped_column(String(64), nullable=False)
    statistic_value: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    context: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
