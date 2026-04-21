# Business Analysis

## 1. Executive Summary

This product is a production-grade backend service for a mobile app focused on stock price alerts. The backend has two equally important business responsibilities: act as a dependable source of daily market price data and act as a dependable source of backend-computed significant-move signals.

The service operates at daily granularity only. It watches the current day's opening price, stores historical closing prices, computes significant downward and upward movement events (`Dip` and `Skyrocket`) using an existing algorithm, and persists both the events and the statistical context used to identify them. The mobile app consumes raw price data, signal events, and the reasoning context behind those events. Custom threshold-style alerts are intentionally out of backend scope and are evaluated locally in the app.

The launch strategy prioritizes data quality, signal quality, historical consistency, and operational trust over broad market coverage. The backend should start with a curated universe of exchanges and instrument types, support manual expansion over time at the exchange level, and avoid duplicate company coverage by automatically selecting a single primary or best listing per company using a defined global policy. The initial exchange set is the New York Stock Exchange, Nasdaq, and the Prague Stock Exchange.

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
- For the current day, monitoring uses the instrument's opening price.
- Historical price storage uses daily closing prices.
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
- Coverage starts from admin-defined exchanges and admin-defined instrument types such as stock, ETF, ETN, and crypto.
- Instruments are loaded automatically based on those admin-defined coverage specifications.
- Initial instrument population, additions, and removals should be handled automatically within the selected scope.
- If a company is listed on multiple exchanges, the backend should generally include only one listing.
- Listing selection should follow a defined global primary/best-listing policy.
- The instrument-selection algorithm may exclude obscure or problematic instruments using quality or relevance criteria such as turnover.
- The app should see only the supported universe, while exclusions remain visible only in admin reporting.
- Newly admitted instruments should be exposed to the app immediately for price data, even if they do not yet have enough history for signal generation.
- If an instrument is delisted, it should be removed from the supported universe after a buffer period.
- When an instrument leaves the supported universe, its historical prices, signals, and supporting statistics should be retained, but it should no longer be updated.
- Instrument additions, removals, degradations, and exclusions should be captured with lightweight change history and explicit reason codes.
- If an exchange is closed for a given day, no price-based computation should happen for that instrument on that day.
- If price data is missing due to a load failure or backend problem, that is considered a backend failure rather than acceptable missing data.
- The app should use exchange-level readiness to know whether current-day data is ready for consumption.
- Each exchange publishes independently when ready; operations may still track a global daily overview.
- Once an exchange is marked ready, that publication should normally be treated as the trusted daily version.
- Post-publication corrections are allowed only as rare exceptions through explicit backend recomputation or reprocessing.
- The app does not need special correction propagation; current state matters most there and history is primarily used for charts.
- Multiple free data sources should be used primarily to maximize availability.
- When multiple candidate values exist, the backend should resolve them through one global source-prioritization policy.
- New exchanges should be added only after passing short-window pre-production validation proving acceptable instrument discovery quality, primary-listing selection, and daily and historical load completeness/timeliness.
- If a supported exchange experiences repeated quality issues, it should remain supported but be marked internally as degraded while investigated.
- Historical results should remain stable by default. Historical recomputation should happen only as an explicit action.
- Changes to the signal algorithm should be validated against historical data before production rollout.
- Data quality is the primary SLA. Timeliness matters within a defined daily window because the service is daily rather than intraday.
- Timely publication means data should be ready within 30 minutes.

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

- Trust over breadth: start with fewer exchanges if that improves confidence in the data and signals
- Correctness over speed: daily outputs may tolerate some delay, but poor-quality data is unacceptable
- Curation over exhaustiveness: support a selected instrument universe rather than every possible listing
- Explainability over black-box signaling: persist the basis for signal decisions, not just the outcomes
- Multi-source resilience over single-source simplicity: combine free inputs to preserve availability without adding routine manual babysitting

## 10. Success Metrics

- High completeness of exchange/day publications for the supported universe
- High correctness of daily price data for supported instruments
- High-confidence `Dip` and `Skyrocket` signal generation for supported instruments
- Historical consistency of prices, statistics, and signal outputs
- Exchange/day publication within the 30-minute timeliness target
- Low rate of missing or incorrect data caused by backend load failures
- Low operational burden in steady-state operation, with investigation needed only for exceptional cases
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

- What exact SLA thresholds define acceptable completeness, correctness, timeliness, and consistency by exchange/day and by instrument?
- What exact business rules determine the "primary/best listing" for multi-listed companies?
- How long is the delisting buffer period before an instrument is removed from the supported universe?
- What exact criteria should instrument-selection filters use for excluding obscure or problematic instruments?
- What business reporting fields should be visible for exclusions and universe changes?
- How should crypto venue selection be curated when a single asset may trade across many venues?
- What exact source-prioritization policy should resolve conflicting candidate values?

## 13. Risks and Uncertainties

- Multi-listed companies may create ambiguous selection decisions that affect coverage consistency.
- Data-source inconsistencies may undermine trust if opening or closing values are not aligned across markets.
- Free-tier limits or source instability may threaten completeness and timeliness unless source diversification is robust enough.
- Exchange-calendar handling may be more complex than expected across global markets.
- Crypto market conventions may not fit perfectly into the same operating assumptions as traditional securities.
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

- What exact outputs must the mobile app be able to request for prices, signals, reasoning context, and exchange readiness?
- What admin inputs are required to define the curated universe of exchanges and instrument types?
- What are the concrete lifecycle states for instruments, especially active, signal-not-ready, market-closed, degraded, delisted-buffer, and removed?
- What are the exact business acceptance rules for exchange/day publication based on completeness, correctness, timeliness, and consistency?
- What precise fields should appear on the operator dashboard for daily and historical loads by exchange, including status, timing, quality, and exceptions?
- What exact validation checks should new exchanges pass before moving from trial to production support?
- What business definitions should govern coverage and listing selection for multi-listed companies and for crypto assets?
