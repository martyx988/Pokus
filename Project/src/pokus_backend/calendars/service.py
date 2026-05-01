from __future__ import annotations

from datetime import date
from typing import Protocol

from pokus_backend.calendars.result import TradingDayDecision, TradingDayStatus


class ExchangeCalendar(Protocol):
    calendar_id: str

    def is_trading_day(self, local_date: date) -> bool:
        ...


class CalendarProvider(Protocol):
    def get_calendar(self, exchange: str) -> ExchangeCalendar | None:
        ...


class ExchangeCalendarService:
    def __init__(self, provider: CalendarProvider) -> None:
        self._provider = provider

    def evaluate(self, exchange: str, local_date: date) -> TradingDayDecision:
        calendar = self._provider.get_calendar(exchange)
        normalized_exchange = exchange.upper()
        if calendar is None:
            return TradingDayDecision(
                exchange=normalized_exchange,
                local_date=local_date,
                status=TradingDayStatus.UNKNOWN_CALENDAR,
                reason="No calendar configured for exchange.",
            )

        is_trading_day = calendar.is_trading_day(local_date)
        status = (
            TradingDayStatus.EXPECTED_TRADING_DAY
            if is_trading_day
            else TradingDayStatus.MARKET_CLOSED
        )
        return TradingDayDecision(
            exchange=normalized_exchange,
            local_date=local_date,
            status=status,
            calendar_id=calendar.calendar_id,
        )
