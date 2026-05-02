from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_DEFAULT_TIMEOUT_SECONDS = 20
_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "pokus-backend-m31-t67-source-probe/1.0",
}


@dataclass(frozen=True, slots=True)
class HttpJsonResponse:
    status_code: int
    payload: Any | None
    raw_body: str
    latency_ms: int


def fetch_json_response(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> HttpJsonResponse:
    request_headers = dict(_DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)

    request = Request(url, headers=request_headers)
    started = perf_counter()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8", errors="replace")
            status_code = response.status
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        status_code = exc.code
    except URLError as exc:
        raise RuntimeError(f"http_request_failed:{type(exc).__name__}:{exc}") from exc

    latency_ms = max(0, int((perf_counter() - started) * 1000))
    payload: Any | None = None
    if raw_body.strip():
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            payload = None
    return HttpJsonResponse(
        status_code=status_code,
        payload=payload,
        raw_body=raw_body,
        latency_ms=latency_ms,
    )
