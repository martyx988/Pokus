from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import create_engine

from pokus_backend import api
from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing, SupportedUniverseState, SupportedUniverseStatus
from pokus_backend.settings import Settings


class AppSupportedUniverseEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmp_dir.name) / "supported-universe.sqlite3"
        cls._db_url = f"sqlite+pysqlite:///{cls._db_path.as_posix()}"
        engine = create_engine(cls._db_url)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(Exchange.__table__.insert(), [{"code": "NYSE", "name": "NYSE", "is_launch_active": True}])
            conn.execute(
                InstrumentType.__table__.insert(),
                [{"code": "STOCK", "name": "Stock", "is_launch_active": True}],
            )
            instrument_ids = conn.execute(
                Instrument.__table__.insert().returning(Instrument.id),
                [
                    {"instrument_type_id": 1, "canonical_name": "Alpha Corp", "is_active": True},
                    {"instrument_type_id": 1, "canonical_name": "Beta Corp", "is_active": True},
                    {"instrument_type_id": 1, "canonical_name": "Gamma Corp", "is_active": True},
                ],
            ).scalars()
            alpha_id, beta_id, gamma_id = list(instrument_ids)
            listing_ids = conn.execute(
                Listing.__table__.insert().returning(Listing.id),
                [
                    {"instrument_id": alpha_id, "exchange_id": 1, "symbol": "ALP"},
                    {"instrument_id": beta_id, "exchange_id": 1, "symbol": "BET"},
                    {"instrument_id": gamma_id, "exchange_id": 1, "symbol": "GAM"},
                ],
            ).scalars()
            alpha_listing_id, beta_listing_id, gamma_listing_id = list(listing_ids)
            conn.execute(
                SupportedUniverseState.__table__.insert(),
                [
                    {"listing_id": alpha_listing_id, "status": SupportedUniverseStatus.SUPPORTED.value},
                    {
                        "listing_id": beta_listing_id,
                        "status": SupportedUniverseStatus.NOT_YET_SIGNAL_ELIGIBLE.value,
                    },
                    {"listing_id": gamma_listing_id, "status": SupportedUniverseStatus.REMOVED.value},
                ],
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

    def _get(self, path: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        request = Request(f"http://127.0.0.1:{self.port}{path}", headers=headers or {}, method="GET")
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_returns_supported_universe_only_with_signal_readiness(self) -> None:
        status, body = self._get("/app/supported-universe", headers={"X-App-Token": "app-token"})
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        payload = json.loads(body)
        rows = payload["supported_universe"]
        self.assertEqual([row["symbol"] for row in rows], ["ALP", "BET"])
        self.assertEqual([row["support_status"] for row in rows], ["supported", "not_yet_signal_eligible"])
        self.assertEqual([row["signal_ready"] for row in rows], [True, False])

    def test_does_not_expose_private_internal_fields(self) -> None:
        status, body = self._get("/app/supported-universe", headers={"X-App-Token": "app-token"})
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        payload = json.loads(body)
        for row in payload["supported_universe"]:
            self.assertNotIn("listing_id", row)
            self.assertNotIn("instrument_id", row)
            self.assertNotIn("note", row)
            self.assertNotIn("effective_from", row)


if __name__ == "__main__":
    unittest.main()
