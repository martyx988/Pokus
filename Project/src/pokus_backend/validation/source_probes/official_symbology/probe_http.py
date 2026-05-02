from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_DEFAULT_TIMEOUT_SECONDS = 25
_DEFAULT_HEADERS = {
    "Accept": "application/json,text/plain,text/html,*/*",
    "User-Agent": "pokus-backend-m31-t68-official-symbology/1.0",
}


@dataclass(frozen=True, slots=True)
class HttpProbeResponse:
    status_code: int
    headers: dict[str, str]
    body_text: str
    latency_ms: int


def fetch_http_response(
    url: str,
    *,
    method: str = "GET",
    body: str | None = None,
    headers: Mapping[str, str] | None = None,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> HttpProbeResponse:
    request_headers = dict(_DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)

    payload = None if body is None else body.encode("utf-8")
    request = Request(url=url, method=method.upper(), headers=request_headers, data=payload)
    started = perf_counter()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8", errors="replace")
            status_code = int(response.getcode() or 0)
            response_headers = {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        status_code = int(exc.code)
        response_headers = {key.lower(): value for key, value in exc.headers.items()} if exc.headers else {}
    except URLError as exc:
        raise RuntimeError(f"http_request_failed:{type(exc).__name__}:{exc.reason}") from exc

    latency_ms = max(0, int((perf_counter() - started) * 1000))
    return HttpProbeResponse(
        status_code=status_code,
        headers=response_headers,
        body_text=raw_body,
        latency_ms=latency_ms,
    )