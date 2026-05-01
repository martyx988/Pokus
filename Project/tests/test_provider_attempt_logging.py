from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.domain.reference_models import Base, Exchange, Provider, ProviderAttempt
from pokus_backend.pricing.provider_attempt_logging import (
    ProviderAttemptLogInput,
    get_provider_attempt_by_key,
    log_provider_attempt,
)


class ProviderAttemptLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.session.add_all(
            [
                Provider(code="ALPHA", name="Alpha", is_active=True),
                Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True),
            ]
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_persists_success_attempt_evidence(self) -> None:
        now = datetime.now(timezone.utc)
        created = log_provider_attempt(
            self.session,
            ProviderAttemptLogInput(
                attempt_key="alpha-nyse-aapl-2026-05-01-open-1",
                provider_code="alpha",
                exchange_code="nyse",
                request_purpose="pricing",
                load_type="current_day_open",
                requested_at=now,
                started_at=now + timedelta(milliseconds=10),
                completed_at=now + timedelta(milliseconds=90),
                latency_ms=80,
                result_status="success",
                normalized_metadata={"request_id": "req-1", "instrument_id": "ins-1"},
            ),
        )
        self.session.commit()

        stored = self.session.scalar(select(ProviderAttempt).where(ProviderAttempt.id == created.id))
        assert stored is not None
        self.assertEqual(stored.attempt_key, "alpha-nyse-aapl-2026-05-01-open-1")
        self.assertEqual(stored.result_status, "success")
        self.assertEqual(stored.request_purpose, "pricing")
        self.assertEqual(stored.load_type, "current_day_open")
        self.assertEqual(stored.latency_ms, 80)
        self.assertFalse(stored.rate_limit_hit)
        self.assertFalse(stored.stale_data)
        self.assertFalse(stored.missing_values)
        self.assertEqual(stored.normalized_metadata, {"request_id": "req-1", "instrument_id": "ins-1"})

    def test_persists_failure_and_rate_limit_missing_stale_flags(self) -> None:
        now = datetime.now(timezone.utc)
        log_provider_attempt(
            self.session,
            ProviderAttemptLogInput(
                attempt_key="alpha-nyse-aapl-2026-05-01-close-1",
                provider_code="ALPHA",
                exchange_code="NYSE",
                request_purpose="pricing",
                load_type="historical_close",
                requested_at=now,
                started_at=now + timedelta(milliseconds=5),
                completed_at=now + timedelta(milliseconds=250),
                latency_ms=245,
                result_status="rate_limited",
                error_code="HTTP_429",
                error_detail="Provider throttled request.",
                rate_limit_hit=True,
                stale_data=True,
                missing_values=True,
                normalized_metadata={"retry_after_seconds": 30},
            ),
        )
        self.session.commit()

        stored = get_provider_attempt_by_key(self.session, "alpha-nyse-aapl-2026-05-01-close-1")
        assert stored is not None
        self.assertEqual(stored.result_status, "rate_limited")
        self.assertEqual(stored.error_code, "HTTP_429")
        self.assertTrue(stored.rate_limit_hit)
        self.assertTrue(stored.stale_data)
        self.assertTrue(stored.missing_values)

    def test_repeated_logging_updates_same_attempt_key_without_duplicates(self) -> None:
        now = datetime.now(timezone.utc)
        attempt_key = "alpha-nyse-aapl-2026-05-01-open-2"
        first = log_provider_attempt(
            self.session,
            ProviderAttemptLogInput(
                attempt_key=attempt_key,
                provider_code="ALPHA",
                exchange_code="NYSE",
                request_purpose="pricing",
                load_type="current_day_open",
                requested_at=now,
                started_at=None,
                completed_at=None,
                latency_ms=None,
                result_status="timeout",
                error_code="HTTP_TIMEOUT",
                error_detail="Initial timeout",
            ),
        )
        self.session.commit()

        second = log_provider_attempt(
            self.session,
            ProviderAttemptLogInput(
                attempt_key=attempt_key,
                provider_code="ALPHA",
                exchange_code="NYSE",
                request_purpose="pricing",
                load_type="current_day_open",
                requested_at=now,
                started_at=now + timedelta(milliseconds=20),
                completed_at=now + timedelta(milliseconds=100),
                latency_ms=80,
                result_status="success",
                normalized_metadata={"request_id": "req-retry"},
            ),
        )
        self.session.commit()

        self.assertEqual(first.id, second.id)
        self.assertEqual(self.session.query(ProviderAttempt).count(), 1)
        stored = get_provider_attempt_by_key(self.session, attempt_key)
        assert stored is not None
        self.assertEqual(stored.result_status, "success")
        self.assertEqual(stored.latency_ms, 80)
        self.assertEqual(stored.normalized_metadata, {"request_id": "req-retry"})


if __name__ == "__main__":
    unittest.main()
