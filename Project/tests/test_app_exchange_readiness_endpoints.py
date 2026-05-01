from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import UTC, date, datetime
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from decimal import Decimal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend import api
from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing, PriceRecord
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad
from pokus_backend.domain.publication_models import PublicationRecord
from pokus_backend.jobs import refresh_publication_read_models
from pokus_backend.settings import Settings


class AppExchangeReadinessEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmp_dir.name) / "exchange-readiness.sqlite3"
        cls._db_url = f"sqlite+pysqlite:///{cls._db_path.as_posix()}"
        engine = create_engine(cls._db_url)
        cls._create_dependency_tables()
        Base.metadata.create_all(
            engine,
            tables=[
                Base.metadata.tables["load_jobs"],
                Exchange.__table__,
                InstrumentType.__table__,
                Instrument.__table__,
                Listing.__table__,
                ExchangeDayLoad.__table__,
                PublicationRecord.__table__,
                PriceRecord.__table__,
            ],
        )

        with Session(engine) as session:
            nyse = Exchange(code="NYSE", name="NYSE", is_launch_active=True)
            nasdaq = Exchange(code="NASDAQ", name="NASDAQ", is_launch_active=True)
            pse = Exchange(code="PSE", name="PSE", is_launch_active=True)
            failed = Exchange(code="AMEX", name="AMEX", is_launch_active=True)
            stock = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
            session.add_all([nyse, nasdaq, pse, failed, stock])
            session.flush()

            instrument = Instrument(instrument_type_id=stock.id, canonical_name="Example Corp")
            session.add(instrument)
            session.flush()
            listing = Listing(instrument_id=instrument.id, exchange_id=nyse.id, symbol="EXMP")
            session.add(listing)
            session.flush()
            session.add(
                PriceRecord(
                    listing_id=listing.id,
                    trading_date=date(2026, 5, 1),
                    price_type="current_day_unadjusted_open",
                    value=Decimal("123.45"),
                    currency="USD",
                )
            )

            nyse_load = ExchangeDayLoad(
                exchange_id=nyse.id,
                trading_date=date(2026, 5, 1),
                load_type="daily_open",
                status="ready",
                eligible_instrument_count=5,
                succeeded_count=5,
                failed_count=0,
            )
            nasdaq_load = ExchangeDayLoad(
                exchange_id=nasdaq.id,
                trading_date=date(2026, 5, 1),
                load_type="daily_open",
                status="partial_problematic",
                eligible_instrument_count=5,
                succeeded_count=4,
                failed_count=1,
            )
            pse_load = ExchangeDayLoad(
                exchange_id=pse.id,
                trading_date=date(2026, 5, 1),
                load_type="daily_open",
                status="market_closed",
                eligible_instrument_count=0,
                succeeded_count=0,
                failed_count=0,
            )
            failed_load = ExchangeDayLoad(
                exchange_id=failed.id,
                trading_date=date(2026, 5, 1),
                load_type="daily_open",
                status="failed",
                eligible_instrument_count=1,
                succeeded_count=0,
                failed_count=1,
            )
            session.add_all([nyse_load, nasdaq_load, pse_load, failed_load])
            session.flush()
            session.execute(sa.text("INSERT INTO load_jobs (id) VALUES (1), (2), (3), (4)"))

            now_utc = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
            session.add_all(
                [
                    PublicationRecord(
                        exchange_day_load_id=nyse_load.id,
                        status="ready",
                        status_updated_at=now_utc,
                        published_at=now_utc,
                    ),
                    PublicationRecord(
                        exchange_day_load_id=nasdaq_load.id,
                        status="blocked",
                        status_updated_at=now_utc,
                        published_at=None,
                    ),
                    PublicationRecord(
                        exchange_day_load_id=pse_load.id,
                        status="market_closed",
                        status_updated_at=now_utc,
                        published_at=None,
                    ),
                    PublicationRecord(
                        exchange_day_load_id=failed_load.id,
                        status="failed",
                        status_updated_at=now_utc,
                        published_at=None,
                    ),
                ]
            )
            nyse_load_id = nyse_load.id
            nasdaq_load_id = nasdaq_load.id
            pse_load_id = pse_load.id
            failed_load_id = failed_load.id
            session.commit()

        with Session(engine) as session:
            for exchange_day_load_id in (nyse_load_id, nasdaq_load_id, pse_load_id, failed_load_id):
                refresh_publication_read_models(session, exchange_day_load_id=exchange_day_load_id)
            session.commit()
        engine.dispose()

        cls.settings = Settings(
            environment="test",
            database_url=cls._db_url,
            api_host="127.0.0.1",
            api_port=0,
            worker_poll_seconds=1.0,
            app_read_token="app-token",
            operator_session_token="operator-token",
            admin_session_token="admin-token",
        )
        cls._original_load_settings = api.load_settings
        api.load_settings = lambda: cls.settings
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), api.HealthHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        api.load_settings = cls._original_load_settings
        cls._tmp_dir.cleanup()

    @classmethod
    def _create_dependency_tables(cls) -> None:
        metadata = Base.metadata
        if "load_jobs" not in metadata.tables:
            sa.Table("load_jobs", metadata, sa.Column("id", sa.BigInteger(), primary_key=True))

    def _get(self, path: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        request = Request(f"http://127.0.0.1:{self.port}{path}", headers=headers or {}, method="GET")
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_returns_readiness_for_multiple_exchanges(self) -> None:
        status, body = self._get("/app/exchanges/readiness?exchange=NYSE,NASDAQ", headers={"X-App-Token": "app-token"})
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        payload = json.loads(body)
        rows = payload["exchange_readiness"]
        self.assertEqual([row["exchange"] for row in rows], ["NASDAQ", "NYSE"])
        self.assertEqual([row["readiness_state"] for row in rows], ["not_ready", "ready"])
        self.assertEqual([row["publication_status"] for row in rows], ["blocked", "ready"])
        self.assertEqual([row["publication_available"] for row in rows], [False, True])

    def test_returns_market_closed_state(self) -> None:
        status, body = self._get("/app/exchanges/PSE/readiness/current", headers={"X-App-Token": "app-token"})
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        payload = json.loads(body)["exchange_readiness"]
        self.assertEqual(payload["exchange"], "PSE")
        self.assertEqual(payload["readiness_state"], "market_closed")
        self.assertEqual(payload["publication_status"], "market_closed")
        self.assertFalse(payload["publication_available"])

    def test_returns_current_day_prices_for_ready_exchange(self) -> None:
        status, body = self._get("/app/exchanges/NYSE/prices/current", headers={"X-App-Token": "app-token"})
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        payload = json.loads(body)["exchange_current_day_prices"]
        self.assertEqual(payload["exchange"], "NYSE")
        self.assertEqual(payload["trading_date"], "2026-05-01")
        self.assertEqual(len(payload["current_day_prices"]), 1)
        row = payload["current_day_prices"][0]
        self.assertEqual(row["symbol"], "EXMP")
        self.assertEqual(row["value"], "123.45000000")
        self.assertEqual(row["currency"], "USD")

    def test_rejects_non_ready_current_day_prices(self) -> None:
        for path in (
            "/app/exchanges/NASDAQ/prices/current",
            "/app/exchanges/AMEX/prices/current",
            "/app/exchanges/PSE/prices/current",
        ):
            with self.subTest(path=path):
                status, body = self._get(path, headers={"X-App-Token": "app-token"})
                self.assertEqual(status, HTTPStatus.NOT_FOUND, msg=body)
                payload = json.loads(body)
                self.assertEqual(payload["error"], "No ready current-day opening prices available.")

    def test_rejects_unknown_exchange_code(self) -> None:
        status, body = self._get("/app/exchanges/readiness?exchange=UNKNOWN", headers={"X-App-Token": "app-token"})
        self.assertEqual(status, HTTPStatus.BAD_REQUEST, msg=body)
        payload = json.loads(body)
        self.assertIn("Unknown exchange code", payload["error"])


if __name__ == "__main__":
    unittest.main()
