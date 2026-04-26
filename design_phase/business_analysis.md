# Business Analysis

## 1. Executive Summary

This product is a production-grade backend service for a mobile app focused on stock price alerts. The backend has two equally important business responsibilities: act as a dependable source of daily market price data and act as a dependable source of backend-computed significant-move signals.

The service operates at daily granularity only. It watches the current day's opening price, stores historical closing prices, computes significant downward and upward movement events (`Dip` and `Skyrocket`) using an existing algorithm, and persists both the events and the statistical context used to identify them. The mobile app consumes raw price data, signal events, and the reasoning context behind those events. Custom threshold-style alerts are intentionally out of backend scope and are evaluated locally in the app.

The launch strategy prioritizes data quality, signal quality, historical consistency, and operational trust over broad market coverage. The backend should start with a curated universe of exchanges and instrument types, support manual expansion over time at the exchange level, and avoid duplicate company coverage by automatically selecting a single primary or best listing per company using a defined global policy. The mandatory initial exchange set is the New York Stock Exchange, Nasdaq, and the Prague Stock Exchange.

## 2. Business Goal

Deliver a production-grade backend that provides the mobile app with clean, dependable daily price data and trustworthy significant-move signals for supported instruments, while being able to scale coverage over time without sacrificing data quality or historical consistency.

## 3. Problem Statement

The mobile app needs a reliable backend source for daily market data and meaningful signal detection across supported instruments. Without a dedicated backend service, the app would lack:

- A consistent source of historical and current daily price data
- A trustworthy backend-owned mechanism for detecting significant daily moves
- A persistent history of detected events and the statistical basis behind them
- A controlled, curated market universe that avoids duplicate or low-quality listings
- Operational accountability around data quality, loading failures, and coverage health

The product problem is therefore not simply "fetch market data." It is "provide a high-trust daily market data and signal service that users can rely on for alert-driven behavior in the app."

## 4. Target Users

- Mobile app end users who want to monitor instruments and receive meaningful stock-price-related alerts
- The mobile app itself as the immediate consumer of backend data, signals, and signal context
- The admin/operator, who defines the supported universe and occasionally investigates failures or expands coverage

## 5. Value Proposition

The backend creates value by combining dependable daily market data with explainable backend-generated signals.

For end users, the value is:

- Confidence that significant-move alerts are based on a consistent backend process
- Lower need to manually watch daily price movements
- Trust that signals are grounded in historical behavior rather than arbitrary thresholds

For the product/operator, the value is:

- A curated, controlled market universe instead of uncontrolled data sprawl
- Historical traceability for why a signal was produced
- A production-grade foundation that can expand to more exchanges over time
- A low-maintenance operating model suitable for a single owner

## 6. Primary Use Cases

- Provide the mobile app with daily price data for supported instruments
- Provide the mobile app with historical closing-price series for supported instruments, optimized around efficient access to recent history
- Provide the mobile app with backend-generated `Dip` and `Skyrocket` events
- Provide the mobile app with the supporting statistics and reasoning context behind those events
- Perform an initial historical fill of supported instruments so the backend can operate with adequate context from day one
- Generate historical `Dip` and `Skyrocket` events and their supporting statistics during initial fill
- Refresh daily data for the supported universe on an ongoing basis
- Maintain and expand the supported exchange and instrument universe over time
- Detect and investigate data-quality or loading failures when needed

## 7. Business Rules and Logic

- The backend operates only at daily granularity.
- For the current day, monitoring uses the instrument's official exchange-local unadjusted opening price.
- Historical price storage uses adjusted daily closing prices.
- Each stored price must retain its currency, because listing currencies vary across exchanges.
- Halted, suspended, or late-open instruments should be marked pending or failed according to load rules rather than assigned an invented fallback price.
- The backend computes only significant-move events: `Dip` and `Skyrocket`.
- The significance-detection algorithm already exists and must be reused.
- `Custom` threshold-style alerts are not part of backend computation and are evaluated locally in the app.
- The backend is a shared market-data and signal service and does not own user-specific alert state.
- The backend persists:
  - Daily price history
  - Detected `Dip` and `Skyrocket` events
  - Statistical inputs and derived statistics used to determine whether an event happened
- The backend must support an initial fill capability to populate historical data before steady-state operation.
- Initial fill must produce a complete historical baseline across prices, signal events, and supporting statistics.
- Coverage starts from admin-defined exchanges and admin-defined instrument types. Launch coverage is stocks, ETFs, and ETNs; crypto is reserved for future expansion.
- Instruments are loaded automatically based on those admin-defined coverage specifications.
- Initial instrument population, additions, and removals should be handled automatically within the selected scope.
- If a company is listed on multiple exchanges, the backend should generally include only one listing.
- Listing selection should follow a defined global primary/best-listing policy. After home exchange and listing-level turnover, remaining ties should be broken by an automatically derived exchange activity priority based on trailing 60 trading-day average total traded value across supported/candidate listings, normalized to USD/EUR-equivalent for cross-market comparison. The ranking should be recomputed during exchange validation and periodically, initially monthly, so larger exchanges are favored and newly added exchanges are incorporated automatically.
- The instrument-selection algorithm may exclude obscure or problematic instruments using the confirmed launch rule: low-turnover exclusion after a 60 trading-day review window below the launch traded-value threshold, stale/missing-data exclusion after missing or invalid prices on 3 of the last 10 expected trading days, and protected benchmark exceptions when needed for correctness checks.
- The app should see only the supported universe, while exclusions remain visible only in admin reporting.
- Newly admitted instruments should be exposed to the app immediately for price data, even if they do not yet have enough history for signal generation.
- If an instrument is delisted or under confirmed delisting suspicion, it should be removed from the supported universe after a 5 expected trading-day buffer, excluding weekends and exchange holidays.
- When an instrument leaves the supported universe, its historical prices, signals, and supporting statistics should be retained, but it should no longer be updated.
- Instrument additions, removals, degradations, and exclusions should be captured with lightweight change history and explicit reason codes.
- Symbol, name, and identifier changes should be captured as lightweight universe-change events when detected.
- Launch scope should not include a full corporate-action engine. Historical continuity should rely primarily on adjusted close, stable provider/reference identifiers should be stored when available, and suspected split or corporate-action anomalies should be flagged for operator review.
- Universe-change and exclusion reporting should show effective day, event type, instrument, exchange, instrument type, reason, details, old state, and new state. It should support filtering by event type and optionally by exchange and instrument.
- If an exchange is closed for a given day, no price-based computation should happen for that instrument on that day.
- If price data is missing due to a load failure or backend problem, that is considered a backend failure rather than acceptable missing data.
- The app should use exchange-level readiness to know whether current-day data is ready for consumption.
- Each exchange publishes independently when ready; operations may still track a global daily overview.
- Once an exchange is marked ready, that publication should normally be treated as the trusted daily version.
- Current-day opening-price publication must wait for successful correctness validation. If an exchange is not published because correctness validation is delayed or failed, that is a serious load-quality failure that must be immediately visible in dashboards and logs.
- The implementation should aim for correctness-validation blocks to be true exceptions. If most exchanges are blocked routinely, the loading, validation, or source strategy has failed the product requirement.
- Post-publication corrections are allowed only as rare exceptions for historical adjusted-close records and dependent backend statistics.
- Historical close corrections are not critical enough to require immediate mobile-app intervention; the app can pick them up through a routine once-daily correction sync.
- Incorrect current-day opening-price publication should be prevented through stronger loading and validation because opening prices drive alert triggers.
- After app launch, signal algorithm changes apply prospectively only and must not retrospectively rewrite alerts already delivered to the app. Retrospective signal recomputation is acceptable in development and pre-launch validation only.
- Multiple free data sources should be used primarily to maximize availability.
- The design phase should accumulate a broad pool of free candidate sources rather than decide final production sources upfront.
- Individual free sources are expected to have limitations; the target is for the combined loading algorithm to meet speed, quality, and robustness criteria by using sources in complementary ways.
- When multiple candidate values exist, the backend should resolve them through one global source-prioritization policy: provider/exchange reliability score, then ratio of historical prices available for the instrument from that source, then exchange coverage quality, then fixed source order as the final tie-breaker.
- Provider reliability should be scored per provider and exchange, updated from validation and production outcomes, and supported by audit evidence showing candidate price values and why the selected source won.
- New exchanges should be added only after passing short-window pre-production validation proving acceptable instrument discovery quality, primary-listing selection, and daily and historical load completeness/timeliness.
- Prague Stock Exchange is mandatory for launch and must meet the same trust bar as NYSE and Nasdaq. If PSE validation fails, launch remains blocked while source discovery, provider combination, adapter behavior, or validation strategy is improved.
- If a supported exchange experiences repeated quality issues, it should remain supported but be marked internally as degraded while investigated.
- If an exchange misses the 30-minute publication target on 3 of the last 5 expected trading days but eventually meets coverage and correctness, it should be internally degraded, visible in dashboards/logs, and investigated for source-strategy or loading improvements. The app should continue to see only ready/not-ready behavior and should not receive lower-trust current-day data.
- Historical results should remain stable by default. Historical adjusted-close recomputation should happen only as an explicit action.
- Changes to the signal algorithm should be validated against historical data before production rollout, then applied prospectively after launch.
- Data quality is the primary SLA. Timeliness matters within a defined daily window because the service is daily rather than intraday.
- Timely publication means data should be ready within 30 minutes.
- The confirmed business SLA baseline is:
  - Completeness: exchange/day publication requires greater than 99% coverage.
  - Correctness: benchmark mismatch rate above 5% creates a correctness issue.
  - Timeliness: daily publication should usually occur within 30 minutes of the relevant market event window.
  - Repeated timeliness misses: 3 misses in the last 5 expected trading days creates internal degradation and requires investigation.
  - Consistency: historical published outputs remain stable unless explicit reprocessing is performed.
  - Instrument gaps: missing prices count as backend failures unless the market is closed or delisting-suspicion rules apply.
  - Current-day readiness: opening-price publication requires successful correctness validation before the exchange/day is marked ready.

## 8. Constraints

- The product is intentionally daily, not intraday.
- The signal algorithm needs at most 1 year of history per instrument.
- Retained history may exceed 1 year when storage allows, but retention should support ad hoc cutoff with a maximum of 3 years.
- The backend must be production-grade even if initial exchange coverage is narrow.
- The backend will be owned and maintained by a single person.
- The backend should minimize admin workflow while still supporting investigation through dashboards and logs.
- Coverage is curated rather than universal at launch.
- Long-term ambition is to cover most major global stock exchanges, but expansion should not compromise trust.
- There is effectively no external market-data budget beyond the paid VPS.
- Data ingestion must rely on free sources, libraries, or free-tier APIs.
- Provider licensing review is not a gating design-phase concern; the system should use workable free sources where they can contribute to the combined loading algorithm.
- Launch recovery expectations are frugal: up to 24 hours of data loss is acceptable for historical and backoffice data after severe infrastructure failure, restoration should be targeted within 24 hours after VPS loss, local backups should run daily, manual off-machine backup copies should happen at least weekly, and restore should be tested before launch and after meaningful schema changes.
- Mobile API credentials should be treated as app identification and throttling controls rather than permanent secrets. The backend should support rotation with overlapping credentials, revocation of abused credentials, and practical rate limiting without adding full end-user backend accounts at launch.
- There are no special legal, compliance, or geographic constraints currently in scope.
- There is no hard deadline; the preference is to optimize for doing it right.

## 9. Priorities and Tradeoffs

- Highest priority: completeness
- Next priority: correctness
- Next priority: timeliness
- Next priority: consistency
- Next priority: signal quality and historical consistency
- Next priority: operational simplicity with enough observability for failure investigation
- Lower launch priority: broad exchange coverage

Key tradeoffs:

- Trust over breadth after mandatory launch scope: NYSE, Nasdaq, and PSE must all pass the same trust bar before launch; later expansion can stay narrow if that improves confidence
- Correctness over speed: daily outputs may tolerate some delay, but poor-quality data is unacceptable
- Curation over exhaustiveness: support a selected instrument universe rather than every possible listing
- Explainability over black-box signaling: persist the basis for signal decisions, not just the outcomes
- Multi-source resilience over single-source simplicity: combine imperfect free inputs so the overall loading algorithm, not each individual source, can satisfy availability, speed, quality, and robustness goals without adding routine manual babysitting

## 10. Success Metrics

- High completeness of exchange/day publications for the supported universe
- High correctness of daily price data for supported instruments
- High-confidence `Dip` and `Skyrocket` signal generation for supported instruments
- Historical consistency of prices, statistics, and signal outputs
- Exchange/day publication within the 30-minute timeliness target
- Low rate of missing or incorrect data caused by backend load failures
- Low operational burden in steady-state operation, inferred from backend KPI health: investigation should be needed only when KPIs are missed, degraded states recur, validation blocks persist, backups fail, workers fail, or publication delays repeat.
- Ability to onboard additional exchanges confidently through pre-production validation
- Strong app confidence in backend outputs, including signal reasoning context

## 11. Assumptions

- The existing significant-move algorithm is sufficiently mature for production use and will not need major business redesign.
- The mobile app needs backend outputs from day one in three forms: price data, signal events, and reasoning context.
- One year of historical data is sufficient for the signal algorithm's statistical basis.
- The admin can define a curated universe through exchange and instrument-type selection.
- A practical and defensible notion of "primary/best listing" can be maintained for multi-listed companies.
- Crypto can be handled within the same high-level product model even though its market behavior differs from exchange-traded securities.
- Stocks, ETFs, and ETNs are the higher-confidence launch priority, while crypto should be included only if it can meet the same trust bar.
- The app mainly values current state and recent history; deeper retained history serves backend trust, recovery, and analysis needs.

## 12. Open Questions

No currently unresolved business questions remain blocking for product or architecture specification.

## 13. Risks and Uncertainties

- Multi-listed companies may create ambiguous selection decisions that affect coverage consistency.
- Data-source inconsistencies may undermine trust if opening or closing values are not aligned across markets.
- Free-tier limits or source instability may threaten completeness and timeliness unless source diversification is robust enough.
- Exchange-calendar handling may be more complex than expected across global markets.
- Crypto market conventions may not fit perfectly into the same operating assumptions as traditional securities if crypto is added in a future expansion.
- If load failures are frequent, the product's value proposition will be damaged because missing data is treated as a backend failure.
- As exchange coverage expands globally, maintaining the same quality bar may become operationally difficult.

## 14. Out of Scope

- Intraday price monitoring
- Backend evaluation of `Custom` alerts
- Full notification delivery logic, since notifications are app-local
- User-specific alert state and alert-rule management beyond backend-generated `Dip` and `Skyrocket` events
- Universal support for all exchanges and listings at launch
- A heavy manual admin workflow as a core product surface

## 15. Recommended Next Questions for the Product Specification Agent

No currently unresolved recommended product-specification questions remain. Earlier recommended questions have been resolved, incorporated into `product_spec.md`, deferred as future scope, or transferred into architecture/research validation work.
