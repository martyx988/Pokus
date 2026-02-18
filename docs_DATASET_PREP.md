# NYSE historical daily dataset prep

This project uses `DailyPriceEntity` with the columns:

- `symbol`
- `date` (`YYYY-MM-DD`)
- `open`
- `high`
- `low`
- `close`
- `volume`

Use the helper script below to download and convert a public NYSE dataset into this app-ready format.

## Generate the file

```bash
python scripts/prepare_nyse_daily_prices.py
```

The script downloads data from:

- `https://raw.githubusercontent.com/ashishpatel26/NYSE-STOCK_MARKET-ANALYSIS-USING-LSTM/master/nyse/prices.csv`

and writes:

- `artifacts/nyse_daily_prices_room.csv`

## Where to place the converted file in this repo

Copy the converted file to:

- `app/src/main/assets/bootstrap/nyse_daily_prices_room.csv`

This keeps the file in a conventional Android assets location for future offline/bootstrap ingestion.
