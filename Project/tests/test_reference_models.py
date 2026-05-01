from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.domain.reference_models import Base, Exchange, InstrumentType, Provider, ProviderAttempt


class ReferenceModelsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_exchange_creation_supports_launch_and_future_cry(self) -> None:
        self.session.add_all(
            [
                Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True),
                Exchange(code="CRY", name="Synthetic Crypto Exchange", is_launch_active=False),
            ]
        )
        self.session.commit()

        rows = self.session.query(Exchange).order_by(Exchange.code.asc()).all()
        self.assertEqual([row.code for row in rows], ["CRY", "NYSE"])
        self.assertFalse(rows[0].is_launch_active)
        self.assertTrue(rows[1].is_launch_active)

    def test_duplicate_exchange_code_is_rejected(self) -> None:
        self.session.add(Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True))
        self.session.commit()

        self.session.add(Exchange(code="NASDAQ", name="Another Nasdaq", is_launch_active=False))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_instrument_type_duplicate_code_is_rejected(self) -> None:
        self.session.add(InstrumentType(code="ETF", name="ETF", is_launch_active=True))
        self.session.commit()

        self.session.add(InstrumentType(code="ETF", name="Different ETF", is_launch_active=False))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_crypto_instrument_type_is_representable_without_launch_activation(self) -> None:
        crypto = InstrumentType(code="CRYPTO", name="Crypto", is_launch_active=False)
        self.session.add(crypto)
        self.session.commit()

        stored = self.session.query(InstrumentType).filter_by(code="CRYPTO").one()
        self.assertEqual(stored.name, "Crypto")
        self.assertFalse(stored.is_launch_active)

    def test_provider_duplicate_code_is_rejected(self) -> None:
        self.session.add(Provider(code="YF", name="Yahoo Finance", is_active=True))
        self.session.commit()

        self.session.add(Provider(code="YF", name="Another Yahoo", is_active=False))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_provider_attempt_success_records_timing_and_metadata(self) -> None:
        provider = Provider(code="POLY", name="Polygon", is_active=True, configuration={"tier": "free"})
        exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        now = datetime.now(timezone.utc)
        attempt = ProviderAttempt(
            provider=provider,
            exchange=exchange,
            request_purpose="pricing",
            load_type="daily_close",
            requested_at=now,
            started_at=now + timedelta(milliseconds=30),
            completed_at=now + timedelta(milliseconds=140),
            latency_ms=110,
            result_status="success",
            normalized_metadata={"http_status": 200, "symbol_count": 10},
        )
        self.session.add(attempt)
        self.session.commit()

        stored = self.session.query(ProviderAttempt).one()
        self.assertEqual(stored.result_status, "success")
        self.assertEqual(stored.exchange.code, "NYSE")
        self.assertEqual(stored.normalized_metadata["http_status"], 200)
        self.assertFalse(stored.rate_limit_hit)
        self.assertFalse(stored.stale_data)
        self.assertFalse(stored.missing_values)

    def test_provider_attempt_timeout_records_error_evidence(self) -> None:
        provider = Provider(code="AV", name="Alpha Vantage", is_active=True)
        exchange = Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True)
        attempt = ProviderAttempt(
            provider=provider,
            exchange=exchange,
            request_purpose="pricing",
            load_type="intraday",
            requested_at=datetime.now(timezone.utc),
            result_status="timeout",
            error_code="HTTP_TIMEOUT",
            error_detail="Provider request exceeded timeout threshold.",
        )
        self.session.add(attempt)
        self.session.commit()

        stored = self.session.query(ProviderAttempt).one()
        self.assertEqual(stored.result_status, "timeout")
        self.assertEqual(stored.error_code, "HTTP_TIMEOUT")
        self.assertIn("timeout", stored.error_detail.lower())

    def test_provider_attempt_rate_limit_evidence_is_persisted(self) -> None:
        provider = Provider(code="IEX", name="IEX Cloud", is_active=True)
        exchange = Exchange(code="PSE", name="Prague Stock Exchange", is_launch_active=True)
        attempt = ProviderAttempt(
            provider=provider,
            exchange=exchange,
            request_purpose="pricing",
            load_type="batch",
            requested_at=datetime.now(timezone.utc),
            result_status="rate_limited",
            rate_limit_hit=True,
            stale_data=True,
            missing_values=True,
            normalized_metadata={"retry_after_seconds": 30},
        )
        self.session.add(attempt)
        self.session.commit()

        stored = self.session.query(ProviderAttempt).one()
        self.assertTrue(stored.rate_limit_hit)
        self.assertTrue(stored.stale_data)
        self.assertTrue(stored.missing_values)
        self.assertEqual(stored.normalized_metadata["retry_after_seconds"], 30)


if __name__ == "__main__":
    unittest.main()
