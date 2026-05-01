from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Protocol

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


class _RuleBasedExchangeCalendar:
    def __init__(self, calendar_id: str, holiday_resolver: Callable[[int], set[date]]) -> None:
        self.calendar_id = calendar_id
        self._holiday_resolver = holiday_resolver

    def is_trading_day(self, local_date: date) -> bool:
        if local_date.weekday() >= 5:
            return False
        return local_date not in self._holiday_resolver(local_date.year)


class LaunchExchangeCalendarProvider:
    """Launch exchange provider for expected trading day resolution (T23)."""

    def __init__(self) -> None:
        self._calendars: dict[str, _RuleBasedExchangeCalendar] = {
            "NYSE": _RuleBasedExchangeCalendar("XNYS", _us_market_holidays),
            "NASDAQ": _RuleBasedExchangeCalendar("XNAS", _us_market_holidays),
            "PSE": _RuleBasedExchangeCalendar("XPRA", _czech_market_holidays),
        }

    def get_calendar(self, exchange: str) -> _RuleBasedExchangeCalendar | None:
        return self._calendars.get(exchange.upper())


def build_launch_exchange_calendar_service() -> ExchangeCalendarService:
    return ExchangeCalendarService(provider=LaunchExchangeCalendarProvider())


def _us_market_holidays(year: int) -> set[date]:
    new_year = _observed_date(date(year, 1, 1))
    mlk_day = _nth_weekday_of_month(year, 1, weekday=0, n=3)
    presidents_day = _nth_weekday_of_month(year, 2, weekday=0, n=3)
    good_friday = _easter_sunday(year) - timedelta(days=2)
    memorial_day = _last_weekday_of_month(year, 5, weekday=0)
    juneteenth = _observed_date(date(year, 6, 19))
    independence_day = _observed_date(date(year, 7, 4))
    labor_day = _nth_weekday_of_month(year, 9, weekday=0, n=1)
    thanksgiving = _nth_weekday_of_month(year, 11, weekday=3, n=4)
    christmas = _observed_date(date(year, 12, 25))

    return {
        new_year,
        mlk_day,
        presidents_day,
        good_friday,
        memorial_day,
        juneteenth,
        independence_day,
        labor_day,
        thanksgiving,
        christmas,
    }


def _czech_market_holidays(year: int) -> set[date]:
    easter = _easter_sunday(year)
    good_friday = easter - timedelta(days=2)
    easter_monday = easter + timedelta(days=1)
    return {
        date(year, 1, 1),
        good_friday,
        easter_monday,
        date(year, 5, 1),
        date(year, 5, 8),
        date(year, 7, 5),
        date(year, 7, 6),
        date(year, 9, 28),
        date(year, 10, 28),
        date(year, 11, 17),
        date(year, 12, 24),
        date(year, 12, 25),
        date(year, 12, 26),
    }


def _observed_date(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    next_month = date(year + (month // 12), (month % 12) + 1, 1)
    current = next_month - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _easter_sunday(year: int) -> date:
    # Gregorian Computus
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)
