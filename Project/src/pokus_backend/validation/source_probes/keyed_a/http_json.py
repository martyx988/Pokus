from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class JsonHttpResponse:
    url: str
    status_code: int
    elapsed_ms: int
    payload: Any


class SourceProbeHttpError(RuntimeError):
    def __init__(
        self,
        *,
        message: str,
        status_code: int | None,
        elapsed_ms: int,
        url: str,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.elapsed_ms = elapsed_ms
        self.url = url
        self.payload = payload


def fetch_json_http(
    *,
    base_url: str,
    params: Mapping[str, str],
    timeout_seconds: float = 15.0,
) -> JsonHttpResponse:
    query = urlencode(params)
    full_url = f"{base_url}?{query}"
    request = Request(
        full_url,
        headers={
            "User-Agent": "pokus-source-probe/1.0",
            "Accept": "application/json",
        },
    )
    started = perf_counter()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read()
            elapsed_ms = max(0, int((perf_counter() - started) * 1000))
            payload = _decode_json_payload(raw_body)
            return JsonHttpResponse(
                url=full_url,
                status_code=int(getattr(response, "status", 200)),
                elapsed_ms=elapsed_ms,
                payload=payload,
            )
    except HTTPError as exc:
        elapsed_ms = max(0, int((perf_counter() - started) * 1000))
        raw_body = exc.read()
        payload = _decode_json_payload(raw_body)
        raise SourceProbeHttpError(
            message=f"http_error:{exc.code}",
            status_code=exc.code,
            elapsed_ms=elapsed_ms,
            url=full_url,
            payload=payload,
        ) from exc
    except URLError as exc:
        elapsed_ms = max(0, int((perf_counter() - started) * 1000))
        raise SourceProbeHttpError(
            message=f"url_error:{type(exc.reason).__name__}",
            status_code=None,
            elapsed_ms=elapsed_ms,
            url=full_url,
            payload=None,
        ) from exc
    except TimeoutError as exc:
        elapsed_ms = max(0, int((perf_counter() - started) * 1000))
        raise SourceProbeHttpError(
            message="timeout",
            status_code=None,
            elapsed_ms=elapsed_ms,
            url=full_url,
            payload=None,
        ) from exc


def _decode_json_payload(raw_body: bytes) -> Any:
    if not raw_body:
        return None
    text = raw_body.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_body": text}

