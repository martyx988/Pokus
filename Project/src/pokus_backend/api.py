from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import psycopg

from pokus_backend.admin.scope_config import set_supported_exchanges, set_supported_instrument_types
from pokus_backend.auth import authorize_path
from pokus_backend.db import check_database_connection
from pokus_backend.observability.health import collect_platform_health
from pokus_backend.observability.logging import log_event
from pokus_backend.observability.metrics import record_api_error
from pokus_backend.settings import load_settings


class HealthHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        settings = load_settings()
        auth = authorize_path(self.path, self.headers, settings)
        if not auth.allowed:
            record_api_error(auth.status)
            log_event("api.request.unauthorized", path=self.path, status=auth.status)
            self._send_json(auth.status, {"error": "unauthorized"})
            return

        try:
            payload = self._read_json_body()
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        try:
            if self.path == "/admin/config/supported-exchanges":
                scope = set_supported_exchanges(settings.database_url, payload.get("codes"))
                self._send_json(HTTPStatus.OK, {"supported_exchanges": list(scope.supported_exchanges)})
                return
            if self.path == "/admin/config/supported-instrument-types":
                scope = set_supported_instrument_types(settings.database_url, payload.get("codes"))
                self._send_json(
                    HTTPStatus.OK,
                    {"supported_instrument_types": list(scope.supported_instrument_types)},
                )
                return
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
        record_api_error(HTTPStatus.NOT_FOUND.value)
        log_event("api.request.not_found", path=self.path, status=HTTPStatus.NOT_FOUND.value)

    def do_GET(self) -> None:  # noqa: N802
        settings = load_settings()
        auth = authorize_path(self.path, self.headers, settings)
        if not auth.allowed:
            record_api_error(auth.status)
            log_event("api.request.unauthorized", path=self.path, status=auth.status)
            self._send_json(auth.status, {"error": "unauthorized"})
            return

        if self.path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {"role": "api", "status": "ok", "environment": settings.environment},
            )
            return
        if self.path == "/operator/health":
            payload = collect_platform_health(
                settings.database_url,
                worker_stale_after_seconds=max(30.0, settings.worker_poll_seconds * 3),
                scheduler_stale_after_seconds=max(60.0, settings.worker_poll_seconds * 6),
            )
            status = HTTPStatus.OK if payload["status"] == "ok" else HTTPStatus.SERVICE_UNAVAILABLE
            payload["role"] = "api"
            payload["environment"] = settings.environment
            self._send_json(status, payload)
            return

        if self.path.startswith("/app/"):
            self._send_json(HTTPStatus.OK, {"boundary": "public_app", "status": "ok"})
            return
        if self.path.startswith("/operator/"):
            self._send_json(HTTPStatus.OK, {"boundary": "operator", "status": "ok"})
            return
        if self.path.startswith("/admin/"):
            self._send_json(HTTPStatus.OK, {"boundary": "admin", "status": "ok"})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
        record_api_error(HTTPStatus.NOT_FOUND.value)
        log_event("api.request.not_found", path=self.path, status=HTTPStatus.NOT_FOUND.value)

    def _send_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def log_message(self, *_args) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Run API/web runtime role.")
    parser.add_argument("--check", action="store_true", help="Validate startup dependencies and exit.")
    args = parser.parse_args()

    settings = load_settings()
    log_event("api.starting", environment=settings.environment, host=settings.api_host, port=settings.api_port)
    if args.check:
        try:
            check_database_connection(settings.database_url)
        except psycopg.OperationalError as exc:
            log_event(
                "api.check.failed",
                environment=settings.environment,
                database_url=settings.database_url,
                error=str(exc),
            )
            print(
                f"api-check-failed env={settings.environment} db={settings.database_url} error={exc}",
                file=sys.stderr,
            )
            return 1
        log_event("api.check.succeeded", environment=settings.environment, database_url=settings.database_url)
        print(f"api-check-ok env={settings.environment} db={settings.database_url}")
        return 0

    server = ThreadingHTTPServer((settings.api_host, settings.api_port), HealthHandler)
    log_event("api.started", environment=settings.environment, host=settings.api_host, port=settings.api_port)
    print(f"api-running host={settings.api_host} port={settings.api_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log_event("api.stopping", reason="keyboard_interrupt")
        return 0
    finally:
        server.server_close()
        log_event("api.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

