# NYSE historical daily dataset prep

This project uses `DailyPriceEntity` with columns:

- `symbol`
- `date` (`YYYY-MM-DD`)
- `open`
- `high`
- `low`
- `close`
- `volume`

## Committed one-day snapshot (short-term bootstrap)

To avoid huge PRs, this repo includes a small one-day snapshot that can be seeded directly into Room:

- `app/src/main/assets/bootstrap/nyse_daily_snapshot_2016-12-30.csv`
- columns: `symbol,date,open,high,low,close,volume`

## Optional full-history generation

```bash
python scripts/prepare_nyse_daily_prices.py
```

The script downloads data from:

- `https://raw.githubusercontent.com/ashishpatel26/NYSE-STOCK_MARKET-ANALYSIS-USING-LSTM/master/nyse/prices.csv`

and writes:

- `artifacts/nyse_daily_prices_room.csv`

If needed, copy generated output for app assets/bootstrap workflows.
