from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pokus_backend.settings import load_settings


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        settings = load_settings()
        body = {
            "role": "api",
            "status": "ok",
            "environment": settings.environment,
        }
        encoded = json.dumps(body).encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_args) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Run API/web runtime role.")
    parser.add_argument("--check", action="store_true", help="Validate startup dependencies and exit.")
    args = parser.parse_args()

    settings = load_settings()
    if args.check:
        print(f"api-check-ok env={settings.environment} db={settings.database_url}")
        return 0

    server = ThreadingHTTPServer((settings.api_host, settings.api_port), HealthHandler)
    print(f"api-running host={settings.api_host} port={settings.api_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

