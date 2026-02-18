#!/usr/bin/env python3
"""Download NYSE historical daily prices and convert to app-ready CSV format.

Input source:
https://raw.githubusercontent.com/ashishpatel26/NYSE-STOCK_MARKET-ANALYSIS-USING-LSTM/master/nyse/prices.csv

Output columns (matching DailyPriceEntity):
  symbol,date,open,high,low,close,volume
"""

from __future__ import annotations

import csv
from pathlib import Path
from urllib.request import urlopen

SOURCE_URL = (
    "https://raw.githubusercontent.com/ashishpatel26/"
    "NYSE-STOCK_MARKET-ANALYSIS-USING-LSTM/master/nyse/prices.csv"
)


def main() -> None:
    out_path = Path("artifacts/nyse_daily_prices_room.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    row_count = 0
    with urlopen(SOURCE_URL, timeout=120) as resp, out_path.open("w", newline="", encoding="utf-8") as out_f:
        reader = csv.DictReader((line.decode("utf-8") for line in resp))
        writer = csv.writer(out_f)
        writer.writerow(["symbol", "date", "open", "high", "low", "close", "volume"])

        for row in reader:
            date = (row.get("date") or "").split(" ")[0]
            symbol = (row.get("symbol") or "").strip()
            if not symbol or not date:
                continue

            try:
                open_p = float(row["open"])
                high_p = float(row["high"])
                low_p = float(row["low"])
                close_p = float(row["close"])
                volume = int(float(row["volume"]))
            except (ValueError, TypeError, KeyError):
                continue

            writer.writerow([
                symbol,
                date,
                f"{open_p:.6f}",
                f"{high_p:.6f}",
                f"{low_p:.6f}",
                f"{close_p:.6f}",
                volume,
            ])
            row_count += 1

    print(f"Wrote {row_count} rows to {out_path}")


if __name__ == "__main__":
    main()
