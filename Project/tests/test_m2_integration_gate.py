from __future__ import annotations

import json
import tempfile
import threading
import unittest
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
from pokus_backend.admin.scope_config import get_supported_scope
from pokus_backend.discovery.contract import DiscoveryCandidate
from pokus_backend.discovery.persistence import persist_discovery_candidates
from pokus_backend.discovery.ranking import ListingRankingCandidate, select_best_listing
from pokus_backend.discovery.supported_universe import project_supported_universe_state
from pokus_backend.domain import Base, Exchange, InstrumentType, Listing, UniverseChangeRecord
from pokus_backend.domain.universe_change_models import UniverseChangeEventType
from pokus_backend.settings import Settings


class Milestone2IntegrationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmp_dir.name) / "m2-integration-gate.sqlite3"
        cls._db_url = f"sqlite+pysqlite:///{cls._db_path.as_posix()}"

        engine = create_engine(cls._db_url)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(
                Exchange.__table__.insert(),
                [
                    {"code": "NYSE", "name": "New York Stock Exchange", "is_launch_active": False},
                    {"code": "NASDAQ", "name": "Nasdaq", "is_launch_active": False},
                ],
            )
            conn.execute(
                InstrumentType.__table__.insert(),
                [{"code": "STOCK", "name": "Stock", "is_launch_active": False}],
            )
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

    def _post(self, path: str, body: dict[str, object], headers: dict[str, str] | None = None) -> tuple[int, str]:
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def _get(self, path: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        request = Request(f"http://127.0.0.1:{self.port}{path}", headers=headers or {}, method="GET")
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_m2_chain_admin_scope_to_app_supported_universe(self) -> None:
        admin_headers = {"X-Private-Session": "admin-token"}

        status, body = self._post("/admin/config/supported-exchanges", {"codes": ["NYSE", "NASDAQ"]}, admin_headers)
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        status, body = self._post("/admin/config/supported-instrument-types", {"codes": ["STOCK"]}, admin_headers)
        self.assertEqual(status, HTTPStatus.OK, msg=body)

        scope = get_supported_scope(self.settings.database_url)
        self.assertEqual(scope.supported_exchanges, ("NASDAQ", "NYSE"))
        self.assertEqual(scope.supported_instrument_types, ("STOCK",))

        engine = create_engine(self.settings.database_url)
        with Session(engine) as session:
            persisted = persist_discovery_candidates(
                session,
                [
                    DiscoveryCandidate(
                        exchange="NYSE",
                        instrument_type="STOCK",
                        symbol="ALP",
                        name="Alpha Corp",
                        stable_identifiers={"figi": "FIGI-ALPHA-N"},
                    ),
                    DiscoveryCandidate(
                        exchange="NASDAQ",
                        instrument_type="STOCK",
                        symbol="ALP",
                        name="Alpha Corp",
                        stable_identifiers={"figi": "FIGI-ALPHA-Q"},
                    ),
                ],
                provider_code="openfigi",
                effective_day=date(2026, 3, 1),
            )

            by_exchange = {
                exchange_code: listing_id
                for listing_id, exchange_code in session.execute(
                    select(Listing.id, Exchange.code)
                    .join(Exchange, Exchange.id == Listing.exchange_id)
                    .where(Listing.id.in_(persisted.listing_ids))
                )
            }
            self.assertSetEqual(set(by_exchange.keys()), {"NYSE", "NASDAQ"})

            first_selection = select_best_listing(
                [
                    ListingRankingCandidate(
                        listing_id=by_exchange["NYSE"],
                        is_home_exchange=True,
                        turnover=Decimal("1000"),
                        exchange_activity_priority=2,
                    ),
                    ListingRankingCandidate(
                        listing_id=by_exchange["NASDAQ"],
                        is_home_exchange=False,
                        turnover=Decimal("5000"),
                        exchange_activity_priority=1,
                    ),
                ]
            )
            self.assertEqual(first_selection.selected_listing_id, by_exchange["NYSE"])

            first_projection = project_supported_universe_state(
                session,
                selected_listing_ids=[first_selection.selected_listing_id],
                supported_exchange_codes=list(scope.supported_exchanges),
                supported_instrument_type_codes=list(scope.supported_instrument_types),
                effective_day=date(2026, 3, 1),
            )
            self.assertEqual(first_projection.supported_listing_ids, (by_exchange["NYSE"],))

            second_selection = select_best_listing(
                [
                    ListingRankingCandidate(
                        listing_id=by_exchange["NYSE"],
                        is_home_exchange=False,
                        turnover=Decimal("1000"),
                        exchange_activity_priority=2,
                    ),
                    ListingRankingCandidate(
                        listing_id=by_exchange["NASDAQ"],
                        is_home_exchange=False,
                        turnover=Decimal("5000"),
                        exchange_activity_priority=1,
                    ),
                ]
            )
            self.assertEqual(second_selection.selected_listing_id, by_exchange["NASDAQ"])

            second_projection = project_supported_universe_state(
                session,
                selected_listing_ids=[second_selection.selected_listing_id],
                supported_exchange_codes=list(scope.supported_exchanges),
                supported_instrument_type_codes=list(scope.supported_instrument_types),
                effective_day=date(2026, 3, 2),
            )
            self.assertEqual(second_projection.supported_listing_ids, (by_exchange["NASDAQ"],))

            event_types = [
                event_type
                for event_type in session.scalars(
                    select(UniverseChangeRecord.event_type).order_by(UniverseChangeRecord.id.asc())
                )
            ]
            self.assertIn(UniverseChangeEventType.ADDED, event_types)
            self.assertIn(UniverseChangeEventType.EXCLUDED, event_types)
            self.assertIn(UniverseChangeEventType.REMOVED, event_types)

            session.commit()
        engine.dispose()

        status, body = self._get("/app/supported-universe", headers={"X-App-Token": "app-token"})
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        payload = json.loads(body)
        rows = payload["supported_universe"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["exchange"], "NASDAQ")
        self.assertEqual(rows[0]["instrument_type"], "STOCK")
        self.assertEqual(rows[0]["symbol"], "ALP")
        self.assertEqual(rows[0]["support_status"], "supported")
        self.assertTrue(rows[0]["signal_ready"])


if __name__ == "__main__":
    unittest.main()
