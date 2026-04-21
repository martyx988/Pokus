# Business Analysis

## 1. Executive Summary

This product is a production-grade backend service for a mobile app focused on stock price alerts. The backend has two equally important business responsibilities: act as a dependable source of daily market price data and act as a dependable source of backend-computed significant-move signals.

The service operates at daily granularity only. It watches the current day's opening price, stores historical closing prices, computes significant downward and upward movement events (`Dip` and `Skyrocket`) using an existing algorithm, and persists both the events and the statistical context used to identify them. The mobile app consumes raw price data, signal events, and the reasoning context behind those events. Custom threshold-style alerts are intentionally out of backend scope and are evaluated locally in the app.

The launch strategy prioritizes signal quality, historical consistency, data quality, and operational trust over broad market coverage. The backend should start with a curated universe of exchanges and instrument types, support manual expansion over time, and avoid duplicate company coverage by selecting a single primary or best listing per company using a defined preference policy with manual override.

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

## 6. Primary Use Cases

- Provide the mobile app with daily price data for supported instruments
- Provide the mobile app with historical closing-price series for supported instruments
- Provide the mobile app with backend-generated `Dip` and `Skyrocket` events
- Provide the mobile app with the supporting statistics and reasoning context behind those events
- Perform an initial historical fill of supported instruments so the backend can operate with adequate context from day one
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
- The backend persists:
  - Daily price history
  - Detected `Dip` and `Skyrocket` events
  - Statistical inputs and derived statistics used to determine whether an event happened
- The backend must support an initial fill capability to populate historical data before steady-state operation.
- Coverage starts from admin-defined exchanges and admin-defined instrument types such as stock, ETF, ETN, and crypto.
- Instruments are loaded based on those admin-defined coverage specifications.
- If a company is listed on multiple exchanges, the backend should generally include only one listing.
- Listing selection should follow a defined primary/best-listing policy with manual override.
- If an instrument is delisted, it should be removed from the supported universe after a buffer period.
- If an exchange is closed for a given day, no price-based computation should happen for that instrument on that day.
- If price data is missing due to a load failure or backend problem, that is considered a backend failure rather than acceptable missing data.
- Data quality is the primary SLA. Timeliness matters, but some buffer is acceptable because the service is daily rather than intraday.

## 8. Constraints

- The product is intentionally daily, not intraday.
- Historical depth needed is at most 1 year per instrument.
- The backend must be production-grade even if initial exchange coverage is narrow.
- The backend should minimize admin workflow while still supporting investigation through dashboards and logs.
- Coverage is curated rather than universal at launch.
- Long-term ambition is to cover most major global stock exchanges, but expansion should not compromise trust.

## 9. Priorities and Tradeoffs

- Highest priority: data quality
- Next priority: signal quality and historical consistency
- Next priority: dependable availability for the app within a buffered daily timing window
- Next priority: operational simplicity with enough observability for failure investigation
- Lower launch priority: broad exchange coverage

Key tradeoffs:

- Trust over breadth: start with fewer exchanges if that improves confidence in the data and signals
- Correctness over speed: daily outputs may tolerate some delay, but poor-quality data is unacceptable
- Curation over exhaustiveness: support a selected instrument universe rather than every possible listing
- Explainability over black-box signaling: persist the basis for signal decisions, not just the outcomes

## 10. Success Metrics

- High-quality daily price data for the supported universe
- High-confidence `Dip` and `Skyrocket` signal generation for supported instruments
- Historical consistency of prices, statistics, and signal outputs
- Daily data and signal availability within the expected buffered SLA window
- Low rate of missing or incorrect data caused by backend load failures
- Low operational burden in steady-state operation
- Ability to expand coverage to additional exchanges and instrument types without degrading trust
- Strong app confidence in backend outputs, including signal reasoning context

## 11. Assumptions

- The existing significant-move algorithm is sufficiently mature for production use and will not need major business redesign.
- The mobile app needs backend outputs from day one in three forms: price data, signal events, and reasoning context.
- One year of historical data is sufficient both for app needs and for the signal algorithm's statistical basis.
- The admin can define a curated universe through exchange and instrument-type selection.
- A practical and defensible notion of "primary/best listing" can be maintained for multi-listed companies.
- Crypto can be handled within the same high-level product model even though its market behavior differs from exchange-traded securities.

## 12. Open Questions

- What exact SLA thresholds define acceptable data quality and acceptable daily timing buffers?
- What specific exchanges and instrument universes will make up the launch set?
- What exact business rules determine the "primary/best listing" for multi-listed companies?
- How long is the delisting buffer period before an instrument is removed from the supported universe?
- What level of detail should the app receive as "reasoning context" without overcomplicating the client experience?
- What business reporting is needed in dashboards for ongoing operational oversight?
- How should crypto venue selection be curated when a single asset may trade across many venues?

## 13. Risks and Uncertainties

- Multi-listed companies may create ambiguous selection decisions that affect coverage consistency.
- Data-source inconsistencies may undermine trust if opening or closing values are not aligned across markets.
- Exchange-calendar handling may be more complex than expected across global markets.
- Crypto market conventions may not fit perfectly into the same operating assumptions as traditional securities.
- If load failures are frequent, the product's value proposition will be damaged because missing data is treated as a backend failure.
- As exchange coverage expands globally, maintaining the same quality bar may become operationally difficult.

## 14. Out of Scope

- Intraday price monitoring
- Backend evaluation of `Custom` alerts
- Full notification delivery logic, since notifications are app-local
- User-defined alert-rule management beyond backend-generated `Dip` and `Skyrocket` events
- Universal support for all exchanges and listings at launch
- A heavy manual admin workflow as a core product surface

## 15. Recommended Next Questions for the Product Specification Agent

- What exact outputs must the mobile app be able to request for prices, signals, and reasoning context?
- What admin inputs are required to define the curated universe of exchanges, instrument types, and listing preferences?
- What are the concrete lifecycle states for instruments, especially active, market-closed, delisted-buffer, and removed?
- What are the exact business acceptance rules for signal generation when data is incomplete, stale, or suspect?
- What daily operational states need to be visible in dashboards and logs for production support?
- What launch exchange set best balances trust, usefulness, and manageable operational scope?
- What business definitions should govern coverage and listing selection for multi-listed companies and for crypto assets?
