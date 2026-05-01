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
from pokus_backend.admin.scope_config import get_supported_scope
from pokus_backend.domain.reference_models import Base, Exchange, InstrumentType
from pokus_backend.settings import Settings


class AdminScopeConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmp_dir.name) / "scope.sqlite3"
        cls._db_url = f"sqlite+pysqlite:///{cls._db_path.as_posix()}"
        engine = create_engine(cls._db_url)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(Exchange.__table__.insert(), [{"code": "NYSE", "name": "NYSE", "is_launch_active": False}])
            conn.execute(Exchange.__table__.insert(), [{"code": "NASDAQ", "name": "Nasdaq", "is_launch_active": False}])
            conn.execute(
                InstrumentType.__table__.insert(),
                [{"code": "STOCK", "name": "Stock", "is_launch_active": False}],
            )
            conn.execute(
                InstrumentType.__table__.insert(),
                [{"code": "ETF", "name": "ETF", "is_launch_active": False}],
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

    def test_admin_scope_mutations_require_admin_token(self) -> None:
        status, _ = self._post("/admin/config/supported-exchanges", {"codes": ["NYSE"]})
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)

        status, _ = self._post(
            "/admin/config/supported-exchanges",
            {"codes": ["NYSE"]},
            headers={"X-Private-Session": "operator-token"},
        )
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    def test_rejects_unsupported_exchange_and_instrument_type_identifiers(self) -> None:
        status, body = self._post(
            "/admin/config/supported-exchanges",
            {"codes": ["NYSE", "DOES_NOT_EXIST"]},
            headers={"X-Private-Session": "admin-token"},
        )
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertIn("Unsupported exchange code", body)

        status, body = self._post(
            "/admin/config/supported-instrument-types",
            {"codes": ["UNKNOWN"]},
            headers={"X-Private-Session": "admin-token"},
        )
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertIn("Unsupported instrument_type code", body)

    def test_scope_persists_and_is_readable_for_worker_side_components(self) -> None:
        status, body = self._post(
            "/admin/config/supported-exchanges",
            {"codes": ["NYSE"]},
            headers={"X-Private-Session": "admin-token"},
        )
        self.assertEqual(status, HTTPStatus.OK, msg=body)

        status, body = self._post(
            "/admin/config/supported-instrument-types",
            {"codes": ["ETF"]},
            headers={"X-Private-Session": "admin-token"},
        )
        self.assertEqual(status, HTTPStatus.OK, msg=body)

        scope = get_supported_scope(self.settings.database_url)
        self.assertEqual(scope.supported_exchanges, ("NYSE",))
        self.assertEqual(scope.supported_instrument_types, ("ETF",))


if __name__ == "__main__":
    unittest.main()
