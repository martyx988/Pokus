from __future__ import annotations

import json
import re
from typing import Sequence

from pokus_backend.discovery.contract import DiscoveryCandidate
from pokus_backend.validation.source_probes.non_keyed.http_fetch import fetch_text
from pokus_backend.validation.source_probes.official_symbology.probe_http import fetch_http_response


def build_default_source_registry():
    return {
        "NASDAQ_TRADER": _load_nasdaq_trader_candidates,
        "NYSE": _load_nyse_candidates,
        "YFINANCE": _load_yfinance_candidates,
        "AKSHARE": _load_akshare_candidates,
        "OPENFIGI": _load_openfigi_candidates,
    }


def _load_nasdaq_trader_candidates(
    exchange_codes: Sequence[str],
    instrument_type_codes: Sequence[str],
) -> list[DiscoveryCandidate]:
    if "NASDAQ" not in exchange_codes or "STOCK" not in instrument_type_codes:
        return []
    response = fetch_http_response("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt")
    rows = [line.strip().split("|") for line in response.body_text.splitlines() if line.strip()]
    if not rows:
        return []
    result: list[DiscoveryCandidate] = []
    for row in rows[1:]:
        if row[0].upper().startswith("FILE CREATION TIME"):
            break
        if len(row) < 2:
            continue
        symbol = row[0].strip().upper()
        name = row[1].strip()
        if not symbol or symbol == "SYMBOL" or not name:
            continue
        result.append(
            DiscoveryCandidate(
                exchange="NASDAQ",
                instrument_type="STOCK",
                symbol=symbol,
                name=name,
                stable_identifiers={"ticker": symbol},
            )
        )
        if len(result) >= 500:
            break
    return result


def _load_nyse_candidates(
    exchange_codes: Sequence[str],
    instrument_type_codes: Sequence[str],
) -> list[DiscoveryCandidate]:
    if "NYSE" not in exchange_codes or "STOCK" not in instrument_type_codes:
        return []
    index = fetch_http_response("https://ftp.nyse.com/NYSESymbolMapping/")
    latest = _latest_nyse_filename(index.body_text)
    if latest is None:
        return []
    mapping = fetch_http_response(f"https://ftp.nyse.com/NYSESymbolMapping/{latest}")
    lines = [line.strip() for line in mapping.body_text.splitlines() if line.strip()]
    result: list[DiscoveryCandidate] = []
    for line in lines:
        parts = line.split("|")
        if len(parts) < 2 or parts[0].upper() == "SYMBOL":
            continue
        symbol = parts[0].strip().upper()
        name = parts[1].strip() or symbol
        result.append(
            DiscoveryCandidate(
                exchange="NYSE",
                instrument_type="STOCK",
                symbol=symbol,
                name=name,
                stable_identifiers={"ticker": symbol},
            )
        )
        if len(result) >= 500:
            break
    return result


def _load_yfinance_candidates(
    exchange_codes: Sequence[str],
    instrument_type_codes: Sequence[str],
) -> list[DiscoveryCandidate]:
    if "STOCK" not in instrument_type_codes:
        return []
    samples = [("NYSE", "AAPL"), ("NASDAQ", "MSFT"), ("PSE", "CEZ.PR")]
    result: list[DiscoveryCandidate] = []
    for exchange_code, symbol in samples:
        if exchange_code not in exchange_codes:
            continue
        payload = fetch_text(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
        ).body_text
        parsed = json.loads(payload)
        chart = parsed.get("chart", {})
        if chart.get("error") or not chart.get("result"):
            continue
        result.append(
            DiscoveryCandidate(
                exchange=exchange_code,
                instrument_type="STOCK",
                symbol=symbol.upper(),
                name=symbol.upper(),
                stable_identifiers={"ticker": symbol.upper()},
            )
        )
    return result


def _load_akshare_candidates(
    exchange_codes: Sequence[str],
    instrument_type_codes: Sequence[str],
) -> list[DiscoveryCandidate]:
    if "STOCK" not in instrument_type_codes:
        return []
    if not set(exchange_codes).intersection({"NYSE", "NASDAQ"}):
        return []
    payload = fetch_text(
        "https://72.push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fid=f3&fs=m:105,m:106,m:107&fields=f12,f14"
    ).body_text
    parsed = json.loads(payload)
    rows = parsed.get("data", {}).get("diff", [])
    result: list[DiscoveryCandidate] = []
    for row in rows if isinstance(rows, list) else []:
        symbol = str(row.get("f12", "")).strip().upper()
        name = str(row.get("f14", "")).strip() or symbol
        if not symbol:
            continue
        exchange = "NYSE" if symbol[:1].isalpha() and symbol[0] < "N" else "NASDAQ"
        if exchange not in exchange_codes:
            continue
        result.append(
            DiscoveryCandidate(
                exchange=exchange,
                instrument_type="STOCK",
                symbol=symbol,
                name=name,
                stable_identifiers={"ticker": symbol},
            )
        )
    return result


def _load_openfigi_candidates(
    exchange_codes: Sequence[str],
    instrument_type_codes: Sequence[str],
) -> list[DiscoveryCandidate]:
    if "STOCK" not in instrument_type_codes:
        return []
    request_body = '[{"idType":"TICKER","idValue":"IBM","exchCode":"US"}]'
    response = fetch_http_response(
        "https://api.openfigi.com/v3/mapping",
        method="POST",
        headers={"Content-Type": "application/json"},
        body=request_body,
    )
    parsed = json.loads(response.body_text)
    data_rows = parsed[0].get("data", []) if isinstance(parsed, list) and parsed else []
    result: list[DiscoveryCandidate] = []
    for row in data_rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        figi = str(row.get("figi", "")).strip()
        if not ticker or not figi:
            continue
        preferred_exchange = "NYSE" if "NYSE" in exchange_codes else ("NASDAQ" if "NASDAQ" in exchange_codes else None)
        if preferred_exchange is None:
            continue
        result.append(
            DiscoveryCandidate(
                exchange=preferred_exchange,
                instrument_type="STOCK",
                symbol=ticker,
                name=str(row.get("name", "")).strip() or ticker,
                stable_identifiers={"figi": figi},
            )
        )
    return result


def _latest_nyse_filename(body_text: str) -> str | None:
    matches = re.findall(r"NYSESymbolMapping_(\d{8})\.txt", body_text)
    if not matches:
        return None
    return f"NYSESymbolMapping_{max(matches)}.txt"
