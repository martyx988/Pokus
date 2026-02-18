# NYSE Stock Alert Android App

A Kotlin + Jetpack Compose Android app that monitors NYSE stock prices every 15 minutes, stores data locally, displays charts, and triggers local notifications when alert rules are met.

## Features

- Free market data provider integration via **Alpha Vantage** (free tier).
- Automatic background refresh every 15 minutes using **WorkManager**.
- Local persistence with **Room**:
  - `stocks`
  - `daily_prices`
  - `intraday_prices`
  - (extra) `alerts`
- Stock search by ticker/company name.
- Stock detail chart modes:
  - `1D` (intraday 15m data)
  - `1M`, `1Y`, `5Y`, `ALL` (daily historical data)
- Alert types:
  - changes by % from current price
  - drops below
  - rises above
- Local Android notifications when alerts trigger.

## Setup

1. Open in Android Studio Hedgehog+.
2. Add your Alpha Vantage API key in `local.properties`:

```properties
ALPHA_VANTAGE_API_KEY=your_key_here
```

3. Build and run.

## Notes

- Alpha Vantage free tier has request limits. The app is structured to keep 15-minute polling and can be tuned for throttling/batching.
- Initial symbol search is remote and then cached locally.
- Historical daily data is fetched on demand per stock.
