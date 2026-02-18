# Free(ish) Stock Market Data API Options for NYSE Monitoring

## 1) Alpha Vantage (current implementation)
**Pros**
- Free tier available, easy API key.
- Has symbol search + intraday + daily history in one provider.
- Simple integration for Android.

**Cons**
- Strict free rate limits (not suitable for broad market sweep every 20 min).
- No free one-call all-NYSE intraday batch endpoint.
- Responses can be slow and include throttling notes.

## 2) Finnhub (free tier)
**Pros**
- Better free request volume than Alpha Vantage for many scenarios.
- Useful quote endpoints and websocket options.
- Reasonable docs and SDK support.

**Cons**
- Free tier still limited for full-NYSE polling every 20 min.
- Coverage/fields for deep historical intraday can vary by plan.
- Might require paid tier for robust production alerting at scale.

## 3) Twelve Data (free tier)
**Pros**
- Clean API, real-time/intraday + historical.
- Good data model and symbol coverage.
- Often easier to work with than some legacy APIs.

**Cons**
- Free tier credits are still limiting for all-NYSE frequent checks.
- Batch endpoints/usage usually constrained by plan.

## 4) Polygon.io (free tier)
**Pros**
- High-quality market data platform.
- Strong real-time + aggregates + websocket support.

**Cons**
- Free plan limits/history are restrictive for broad frequent scanning.
- Paid plans usually needed for scalable production workloads.

## 5) IEX Cloud / similar paid-first providers
**Pros**
- Better institutional quality and scalable throughput.
- Stronger SLAs and batch/streaming options (depending on plan).

**Cons**
- Not truly free at the required scale.

---

## Recommendation
For your requirement (**many NYSE symbols, every 20 minutes, market hours, with reliable alerts**), a pure free API is generally insufficient.

Best practical path:
1. Use **Finnhub free tier** or **Twelve Data free tier** for prototyping and a small watch universe.
2. Keep app architecture with local cache + retries + background worker.
3. For production-scale NYSE coverage, move to a paid plan (Polygon/Finnhub/TwelveData/IEX-like) or a backend aggregator that can batch and fan-out updates to devices.

If you want, I can switch this implementation from Alpha Vantage to Finnhub next and keep the same database/UI contract.
