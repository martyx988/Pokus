from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
