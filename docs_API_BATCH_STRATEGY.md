# Free API Batch Strategy (Practical Plan)

## Can free providers do batch calls?

Short answer: **some can**, but with limits and usually not true real-time institutional breadth.

### Alpha Vantage
- Free tier: not suitable for broad NYSE batch snapshots at scale.
- For your scenario, assume **no practical batch mode** for all needed symbols.

### Finnhub
- Common free usage is mostly per-symbol quote calls.
- Not a reliable free all-NYSE batch option.

### Twelve Data
- Supports multi-symbol requests in some endpoints (comma-separated symbols), i.e. partial batch behavior.
- Still constrained by free credits and practical symbol count; may not scale to large universes daily without careful curation.

### Polygon
- Has strong snapshot endpoints, including broad-market style views on paid plans.
- Free capabilities are restrictive for production-grade broad tracking.

### FMP / EOD-style providers (varies by provider)
- Some providers expose end-of-day or delayed batch/screener snapshots.
- Free tiers often have stricter limits, delayed data, or changing terms.

---

## Is “2 loads/day” feasible on free plans?

**Yes, conditionally** — if you accept one or more of:
1. Reduced stock universe (watchlist only, not all NYSE).
2. Delayed quotes or EOD-like data.
3. Provider-specific limits and occasional missing symbols.

If you insist on broad NYSE coverage with dependable fresh opening/closing snapshots, free tiers usually become fragile.

---

## Recommended architecture for free-tier operation

1. Keep local Room cache as source of truth.
2. Pull data only for symbols with active alerts.
3. Run two scheduled jobs:
   - shortly after open (e.g., 09:40 ET)
   - shortly after close (e.g., 16:10 ET)
4. Add adaptive fallback:
   - if batch endpoint unavailable/throttled, split to small chunks
   - retry with backoff
   - persist last successful snapshot and mark stale age in UI
5. Add provider abstraction (`MarketDataProvider`) so switching providers is low-risk.

---

## Concrete recommendation

For free-first MVP:
- Start with **Twelve Data** for limited batch-like pulls on a **small universe** (e.g., 20–100 symbols), two snapshots/day.
- Keep Alpha Vantage fallback for history if needed.
- Design app/provider layer so paid upgrade can be dropped in later without schema changes.

For production-scale broad NYSE scanning:
- plan for paid market data or backend aggregation.
