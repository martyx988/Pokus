from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class HttpFetchResult:
    url: str
    status_code: int
    body_text: str
    latency_ms: int


def fetch_text(
    url: str,
    *,
    timeout_seconds: float = 20.0,
    user_agent: str = "pokus-backend-m31-t65/1.0",
) -> HttpFetchResult:
    started = perf_counter()
    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            status_code = int(response.getcode() or 0)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status_code = int(exc.code)
    except URLError as exc:
        latency_ms = max(0, int((perf_counter() - started) * 1000))
        raise RuntimeError(f"http_request_failed:{type(exc).__name__}:{exc.reason}") from exc

    latency_ms = max(0, int((perf_counter() - started) * 1000))
    return HttpFetchResult(
        url=url,
        status_code=status_code,
        body_text=body,
        latency_ms=latency_ms,
    )

