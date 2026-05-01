from __future__ import annotations

import json
import threading
import unittest
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pokus_backend import api
from pokus_backend.settings import Settings


class AuthBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = Settings(
            environment="test",
            database_url="postgresql://redacted",
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

    def _request(
        self,
        path: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        request = Request(f"http://127.0.0.1:{self.port}{path}", headers=headers or {}, method="GET")
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_app_boundary_requires_token(self) -> None:
        status, _ = self._request("/app/ping")
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)

        status, _ = self._request("/app/ping", headers={"X-App-Token": "bad-token"})
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

        status, body = self._request("/app/ping", headers={"X-App-Token": "app-token"})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(json.loads(body)["boundary"], "public_app")

    def test_private_boundaries_require_private_session_with_role_checks(self) -> None:
        status, _ = self._request("/operator/ping")
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)

        status, body = self._request("/operator/ping", headers={"X-Private-Session": "operator-token"})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(json.loads(body)["boundary"], "operator")

        status, body = self._request("/admin/ping", headers={"X-Private-Session": "admin-token"})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(json.loads(body)["boundary"], "admin")

        status, _ = self._request("/admin/ping", headers={"X-Private-Session": "operator-token"})
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    def test_auth_errors_do_not_echo_secret_tokens(self) -> None:
        leaked_token = "token-never-echo-this"
        status, body = self._request("/admin/ping", headers={"X-Private-Session": leaked_token})
        self.assertEqual(status, HTTPStatus.FORBIDDEN)
        self.assertNotIn(leaked_token, body)


if __name__ == "__main__":
    unittest.main()
