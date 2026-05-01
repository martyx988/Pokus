from __future__ import annotations

import datetime as dt
import unittest

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.domain import (
    Base,
    Exchange,
    Instrument,
    InstrumentType,
    Listing,
    PriceRecord,
)
from pokus_backend.domain.reference_models import Provider, ProviderAttempt


class PriceRecordModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = sa.create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                Exchange.__table__,
                InstrumentType.__table__,
                Provider.__table__,
                ProviderAttempt.__table__,
                Instrument.__table__,
                Listing.__table__,
                PriceRecord.__table__,
            ],
        )
        self.session = Session(self.engine)
        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.provider = Provider(code="POLY", name="Polygon", is_active=True)
        self.session.add_all([self.exchange, self.instrument_type, self.provider])
        self.session.flush()
        self.instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Example Corp.")
        self.session.add(self.instrument)
        self.session.flush()
        self.listing = Listing(instrument_id=self.instrument.id, exchange_id=self.exchange.id, symbol="EXMP")
        self.session.add(self.listing)
        self.session.flush()
        self.provider_attempt = ProviderAttempt(
            attempt_key="poly-nyse-pricing-daily-open-1",
            provider_id=self.provider.id,
            exchange_id=self.exchange.id,
            request_purpose="pricing",
            load_type="daily_open",
            requested_at=dt.datetime(2026, 5, 1, tzinfo=dt.timezone.utc),
            result_status="success",
        )
        self.session.add(self.provider_attempt)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_supported_price_types_are_representable(self) -> None:
        self.session.add_all(
            [
                PriceRecord(
                    listing_id=self.listing.id,
                    trading_date=dt.date(2026, 4, 30),
                    price_type="historical_adjusted_close",
                    value=101.25,
                    currency="USD",
                ),
                PriceRecord(
                    listing_id=self.listing.id,
                    trading_date=dt.date(2026, 5, 1),
                    price_type="current_day_unadjusted_open",
                    value=102.75,
                    currency="USD",
                ),
            ]
        )
        self.session.commit()
        self.assertEqual(self.session.query(PriceRecord).count(), 2)

    def test_currency_is_required(self) -> None:
        self.session.add(
            PriceRecord(
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 1),
                price_type="historical_adjusted_close",
                value=99.0,
                currency=None,  # type: ignore[arg-type]
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_duplicate_selected_price_for_listing_date_type_is_rejected(self) -> None:
        self.session.add(
            PriceRecord(
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 1),
                price_type="historical_adjusted_close",
                value=100.0,
                currency="USD",
            )
        )
        self.session.commit()

        self.session.add(
            PriceRecord(
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 1),
                price_type="historical_adjusted_close",
                value=101.0,
                currency="USD",
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_invalid_price_type_is_rejected(self) -> None:
        self.session.add(
            PriceRecord(
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 4),
                price_type="intraday_mid",
                value=106.0,
                currency="USD",
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_provider_attempt_reference_is_optional_and_linkable(self) -> None:
        self.session.add(
            PriceRecord(
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 2),
                price_type="historical_adjusted_close",
                value=105.0,
                currency="USD",
                provider_attempt_id=self.provider_attempt.id,
            )
        )
        self.session.add(
            PriceRecord(
                listing_id=self.listing.id,
                trading_date=dt.date(2026, 5, 3),
                price_type="historical_adjusted_close",
                value=106.0,
                currency="USD",
                provider_attempt_id=None,
            )
        )
        self.session.commit()

        linked = self.session.query(PriceRecord).filter_by(trading_date=dt.date(2026, 5, 2)).one()
        unlinked = self.session.query(PriceRecord).filter_by(trading_date=dt.date(2026, 5, 3)).one()
        self.assertEqual(linked.provider_attempt_id, self.provider_attempt.id)
        self.assertIsNone(unlinked.provider_attempt_id)


if __name__ == "__main__":
    unittest.main()
