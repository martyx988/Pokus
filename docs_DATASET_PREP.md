# NYSE historical daily dataset prep

This project now includes a **small committed bootstrap snapshot** with one trading day for all symbols available in the source dataset.

## Committed one-day snapshot (for short-term bootstrap)

- File in repo: `app/src/main/assets/bootstrap/nyse_daily_snapshot_2016-12-30.csv`
- Columns: `symbol,date,open,high,low,close,volume`

This file is intentionally small enough to keep in Git and can be loaded directly into Room on first bootstrap.

## Optional: regenerate from source

```bash
python scripts/prepare_nyse_daily_prices.py
```

Source used by the script:

- `https://raw.githubusercontent.com/ashishpatel26/NYSE-STOCK_MARKET-ANALYSIS-USING-LSTM/master/nyse/prices.csv`

Generated full-history output:

- `artifacts/nyse_daily_prices_room.csv`
