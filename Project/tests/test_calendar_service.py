from __future__ import annotations

import unittest
from datetime import date

from pokus_backend.calendars.result import TradingDayStatus
from pokus_backend.calendars.service import ExchangeCalendarService, LaunchExchangeCalendarProvider


class _FakeCalendar:
    def __init__(self, calendar_id: str, trading_days: set[date]) -> None:
        self.calendar_id = calendar_id
        self._trading_days = trading_days

    def is_trading_day(self, local_date: date) -> bool:
        return local_date in self._trading_days


class _FakeProvider:
    def __init__(self, calendars: dict[str, _FakeCalendar]) -> None:
        self._calendars = calendars

    def get_calendar(self, exchange: str) -> _FakeCalendar | None:
        return self._calendars.get(exchange.upper())


class ExchangeCalendarServiceTests(unittest.TestCase):
    def test_expected_trading_day_response(self) -> None:
        provider = _FakeProvider(
            {"NYSE": _FakeCalendar(calendar_id="XNYS", trading_days={date(2026, 5, 1)})}
        )
        service = ExchangeCalendarService(provider=provider)

        result = service.evaluate(exchange="nyse", local_date=date(2026, 5, 1))

        self.assertEqual(result.exchange, "NYSE")
        self.assertEqual(result.local_date, date(2026, 5, 1))
        self.assertEqual(result.status, TradingDayStatus.EXPECTED_TRADING_DAY)
        self.assertTrue(result.is_expected_trading_day)
        self.assertEqual(result.calendar_id, "XNYS")
        self.assertIsNone(result.reason)

    def test_market_closed_response(self) -> None:
        provider = _FakeProvider(
            {"NYSE": _FakeCalendar(calendar_id="XNYS", trading_days={date(2026, 5, 1)})}
        )
        service = ExchangeCalendarService(provider=provider)

        result = service.evaluate(exchange="NYSE", local_date=date(2026, 5, 2))

        self.assertEqual(result.status, TradingDayStatus.MARKET_CLOSED)
        self.assertFalse(result.is_expected_trading_day)
        self.assertEqual(result.calendar_id, "XNYS")

    def test_unknown_calendar_response(self) -> None:
        service = ExchangeCalendarService(provider=_FakeProvider(calendars={}))

        result = service.evaluate(exchange="PSE", local_date=date(2026, 5, 1))

        self.assertEqual(result.exchange, "PSE")
        self.assertEqual(result.status, TradingDayStatus.UNKNOWN_CALENDAR)
        self.assertFalse(result.is_expected_trading_day)
        self.assertIsNone(result.calendar_id)
        self.assertEqual(result.reason, "No calendar configured for exchange.")


class LaunchExchangeCalendarProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ExchangeCalendarService(provider=LaunchExchangeCalendarProvider())

    def test_weekend_is_market_closed_for_each_launch_exchange(self) -> None:
        weekend = date(2026, 5, 2)

        for exchange in ("NYSE", "NASDAQ", "PSE"):
            with self.subTest(exchange=exchange):
                result = self.service.evaluate(exchange=exchange, local_date=weekend)
                self.assertEqual(result.status, TradingDayStatus.MARKET_CLOSED)

    def test_known_holiday_is_market_closed_for_us_launch_exchanges(self) -> None:
        us_holiday = date(2026, 7, 3)  # Observed Independence Day

        for exchange in ("NYSE", "NASDAQ"):
            with self.subTest(exchange=exchange):
                result = self.service.evaluate(exchange=exchange, local_date=us_holiday)
                self.assertEqual(result.status, TradingDayStatus.MARKET_CLOSED)

    def test_known_holiday_is_market_closed_for_pse(self) -> None:
        result = self.service.evaluate(exchange="PSE", local_date=date(2026, 9, 28))

        self.assertEqual(result.status, TradingDayStatus.MARKET_CLOSED)
        self.assertEqual(result.calendar_id, "XPRA")

    def test_normal_weekday_is_expected_trading_day_for_each_launch_exchange(self) -> None:
        weekday = date(2026, 5, 4)

        for exchange in ("NYSE", "NASDAQ", "PSE"):
            with self.subTest(exchange=exchange):
                result = self.service.evaluate(exchange=exchange, local_date=weekday)
                self.assertEqual(result.status, TradingDayStatus.EXPECTED_TRADING_DAY)
                self.assertTrue(result.is_expected_trading_day)


if __name__ == "__main__":
    unittest.main()