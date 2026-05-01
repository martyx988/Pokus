from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class TradingDayStatus(str, Enum):
    EXPECTED_TRADING_DAY = "expected_trading_day"
    MARKET_CLOSED = "market_closed"
    UNKNOWN_CALENDAR = "unknown_calendar"


@dataclass(frozen=True, slots=True)
class TradingDayDecision:
    exchange: str
    local_date: date
    status: TradingDayStatus
    calendar_id: str | None = None
    reason: str | None = None

    @property
    def is_expected_trading_day(self) -> bool:
        return self.status == TradingDayStatus.EXPECTED_TRADING_DAY
