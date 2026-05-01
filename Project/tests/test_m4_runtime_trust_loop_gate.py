from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import unittest
import uuid
from datetime import date
from decimal import Decimal
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend import api
from pokus_backend.db import to_sqlalchemy_url
from pokus_backend.domain import Instrument, Listing, PriceRecord, SupportedUniverseState, SupportedUniverseStatus
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad, InstrumentLoadOutcome
from pokus_backend.domain.publication_models import PublicationRecord
from pokus_backend.domain.reference_models import Exchange, InstrumentType
from pokus_backend.settings import Settings


ROOT = Path(__file__).resolve().parents[1]
TEST_DB_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
TRADING_DATE = date(2026, 5, 1)


@unittest.skipUnless(TEST_DB_URL, "Set TEST_DATABASE_URL or DATABASE_URL for T61 runtime trust-loop gate.")
class Milestone4RuntimeTrustLoopGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = f"t61_{uuid.uuid4().hex[:12]}"
        self.schema_options = f"-c search_path={self.schema},public"
        self._original_pgoptions = os.environ.get("PGOPTIONS")
        os.environ["PGOPTIONS"] = self.schema_options
        import psycopg

        with psycopg.connect(TEST_DB_URL or "", connect_timeout=5, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f'CREATE SCHEMA "{self.schema}"')
        self._run_module("pokus_backend.db", "--migrate")
        self._run_module("pokus_backend.db", "--seed-launch-baseline")
        self.engine = create_engine(to_sqlalchemy_url(TEST_DB_URL or ""))

    def tearDown(self) -> None:
        self.engine.dispose()
        import psycopg

        with psycopg.connect(TEST_DB_URL or "", connect_timeout=5, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE')
        if self._original_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = self._original_pgoptions

    def _run_module(self, module: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env["DATABASE_URL"] = TEST_DB_URL or ""
        env["PGOPTIONS"] = self.schema_options
        completed = subprocess.run(
            [sys.executable, "-m", module, *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        return completed

    def _get(self, port: int, path: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        request = Request(f"http://127.0.0.1:{port}{path}", headers=headers or {}, method="GET")
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_worker_runtime_trust_loop_marks_publication_ready_and_exposes_app_prices(self) -> None:
        listing_id: int | None = None
        with Session(self.engine) as session:
            nyse = session.scalar(select(Exchange).where(Exchange.code == "NYSE"))
            stock = session.scalar(select(InstrumentType).where(InstrumentType.code == "STOCK"))
            self.assertIsNotNone(nyse)
            self.assertIsNotNone(stock)

            instrument = Instrument(instrument_type_id=stock.id, canonical_name="Trust Loop Corp")
            session.add(instrument)
            session.flush()
            listing = Listing(instrument_id=instrument.id, exchange_id=nyse.id, symbol="TRST")
            session.add(listing)
            session.flush()
            listing_id = listing.id
            session.add(
                SupportedUniverseState(
                    listing_id=listing.id,
                    status=SupportedUniverseStatus.SUPPORTED,
                )
            )
            session.add(
                PriceRecord(
                    listing_id=listing.id,
                    trading_date=TRADING_DATE,
                    price_type="current_day_unadjusted_open",
                    value=Decimal("321.09"),
                    currency="USD",
                )
            )
            session.commit()

        completed = self._run_module(
            "pokus_backend.worker",
            "--run-opening-trust-loop",
            "--trust-loop-date",
            TRADING_DATE.isoformat(),
            "--trust-loop-exchanges",
            "NYSE",
        )
        self.assertIn("worker-opening-trust-loop-ok", completed.stdout)
        self.assertIn("ready=1", completed.stdout)
        self.assertIsNotNone(listing_id)

        with Session(self.engine) as session:
            load = session.scalar(
                select(ExchangeDayLoad).where(
                    ExchangeDayLoad.trading_date == TRADING_DATE,
                    ExchangeDayLoad.load_type == "daily_open",
                )
            )
            self.assertIsNotNone(load)
            self.assertEqual(load.status, "ready")
            self.assertEqual(load.eligible_instrument_count, 1)
            self.assertEqual(load.succeeded_count, 1)
            self.assertEqual(load.failed_count, 0)

            outcome = session.scalar(
                select(InstrumentLoadOutcome).where(
                    InstrumentLoadOutcome.exchange_day_load_id == load.id,
                    InstrumentLoadOutcome.listing_id == listing_id,
                )
            )
            self.assertIsNotNone(outcome)
            self.assertEqual(outcome.outcome, "succeeded")
            self.assertTrue(outcome.is_terminal)

            publication = session.scalar(
                select(PublicationRecord).where(PublicationRecord.exchange_day_load_id == load.id)
            )
            self.assertIsNotNone(publication)
            self.assertEqual(publication.status, "ready")

        settings = Settings(
            environment="test",
            database_url=TEST_DB_URL or "",
            api_host="127.0.0.1",
            api_port=0,
            worker_poll_seconds=1.0,
            app_read_token="app-token",
            operator_session_token="operator-token",
            admin_session_token="admin-token",
        )
        original_load_settings = api.load_settings
        api.load_settings = lambda: settings
        server = ThreadingHTTPServer(("127.0.0.1", 0), api.HealthHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, body = self._get(
                port,
                "/app/exchanges/readiness?exchange=NYSE",
                headers={"X-App-Token": "app-token"},
            )
            self.assertEqual(status, HTTPStatus.OK, msg=body)
            readiness = json.loads(body)["exchange_readiness"][0]
            self.assertEqual(readiness["readiness_state"], "ready")
            self.assertTrue(readiness["publication_available"])

            status, body = self._get(
                port,
                "/app/exchanges/NYSE/prices/current",
                headers={"X-App-Token": "app-token"},
            )
            self.assertEqual(status, HTTPStatus.OK, msg=body)
            prices = json.loads(body)["exchange_current_day_prices"]["current_day_prices"]
            self.assertEqual(len(prices), 1)
            self.assertEqual(prices[0]["symbol"], "TRST")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            api.load_settings = original_load_settings
