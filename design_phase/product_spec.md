# Product Specification

## 1. System Overview

### 1.1 Purpose

The system is a production-grade backend service for a mobile app that needs:

- Daily market price data for supported instruments
- Backend-generated significant-move signals (`Dip` and `Skyrocket`)
- Supporting signal context derived from the existing alert algorithm

The system operates only at daily granularity. It stores historical closing prices, tracks the current day's opening price, computes significant-move events using an existing algorithm, and exposes both market data and signal outputs to the mobile app.

### 1.2 Included Scope

The system includes:

- Automatic discovery and maintenance of a supported instrument universe within admin-selected exchanges and instrument types
- Daily ingestion of current-day opening prices and historical daily closing prices
- Historical retention of prices, signal events, and supporting statistics
- Initial historical fill
- Ongoing daily loads
- Backend computation of `Dip` and `Skyrocket`
- Exchange-level readiness/publication state
- Lightweight operational visibility for exceptions, quality, and readiness
- Pre-production validation of new exchanges before production admission

### 1.3 Excluded Scope

The system excludes:

- Intraday monitoring
- User-specific alert state
- Backend evaluation of `Custom` alerts
- Notification delivery
- App-facing SLA dashboards
- Universal support for all exchanges or listings

### 1.4 Launch Scope

The initial production exchange set is:

- New York Stock Exchange
- Nasdaq
- Prague Stock Exchange

Initial launch priority is:

- Stocks
- ETFs
- ETNs

Crypto remains in overall scope but should only be introduced if it can meet the same trust bar. In this specification, `crypto` refers to cryptocurrencies themselves, not crypto ETFs.

## 2. Use Cases

### 2.1 Daily App Refresh

Primary flow:

1. The app checks readiness for one or more supported exchanges.
2. The system returns whether each exchange's current-day publication is ready.
3. For exchanges that are ready, the app retrieves today's prices and available signals.
4. The app also retrieves yesterday's historical record as part of its normal daily refresh pattern.

Variation:

- If an exchange is not ready, the app does not refresh that exchange's current-day data.

### 2.2 App Installation History Load

Primary flow:

1. A newly installed app requests recent historical data.
2. The system returns the latest 30 days of historical price data for supported instruments.
3. The app uses this as its initial historical view.

Variation:

- Signal availability may be absent for newly admitted instruments that do not yet have enough history.

### 2.3 Initial Historical Population

Primary flow:

1. The system performs an initial fill for supported instruments.
2. The system loads historical closing prices.
3. The system computes historical supporting statistics.
4. The system computes historical `Dip` and `Skyrocket` events.
5. The resulting historical baseline becomes the initial production record.

### 2.4 Automatic Universe Maintenance

Primary flow:

1. The admin selects supported exchanges and instrument types.
2. The system discovers candidate instruments within that scope.
3. The system selects a single primary or best listing for multi-listed companies using this precedence:
   - home exchange
   - highest turnover
   - fixed exchange priority
4. The system excludes instruments that fail selection or quality/relevance criteria.
5. The system exposes only the final supported universe to the app.
6. The system continues to add and remove instruments automatically over time.

Variations:

- Newly admitted instruments become available for price data immediately.
- Signal generation for a newly admitted instrument remains unavailable until sufficient history exists.
- Delisted instruments remain historically visible but stop receiving updates after the buffer period.
- Supported cryptocurrencies should be grouped under a synthetic `CRY` exchange and represented by exactly one chosen listing per asset.

### 2.5 Exchange Expansion

Primary flow:

1. The admin chooses to evaluate a new exchange.
2. The system runs a short validation period for that exchange.
3. The system verifies discovery quality, primary-listing selection behavior, and daily/historical load completeness and timeliness.
4. If the exchange meets the trust bar, it may be admitted to production support.

### 2.6 Exceptional Reprocessing

Primary flow:

1. A bad historical or daily publication is identified.
2. The system performs explicit backend recomputation or reprocessing.
3. Stored prices, supporting statistics, and signal events are corrected in backend records.
4. The app is not specially notified; future reads reflect the corrected backend state.

## 3. Functional Requirements

### 3.1 Exchange and Universe Management

- FR-1: The system must allow the admin to define supported exchanges.
- FR-2: The system must allow the admin to define supported instrument types.
- FR-3: The system must automatically discover instruments within the selected exchange and instrument-type scope.
- FR-4: The system must automatically maintain the supported universe over time, including initial population, additions, removals, and delisting handling.
- FR-5: The system must apply a single global primary/best-listing policy so that a company listed on multiple exchanges is generally represented by one supported listing.
- FR-6: The global primary/best-listing policy must rank candidate listings in this order:
  - home exchange
  - highest turnover
  - fixed exchange priority
- FR-7: The system must support automatic exclusion of obscure or problematic instruments based on selection criteria such as persistently low turnover and stale or missing data.
- FR-8: The system must expose only the supported universe to the app.
- FR-9: The system must record instrument additions, removals, exclusions, and degradations with explicit reasons in a lightweight historical record.
- FR-10: When an instrument leaves the supported universe, the system must stop updating it but retain its stored history subject to overall retention rules.
- FR-11: The system must allow newly admitted instruments to be exposed for price data immediately, even before signal eligibility is reached.
- FR-11a: The system must group supported cryptocurrencies under a synthetic `CRY` exchange rather than treating their native venues as separate supported exchanges.
- FR-11b: The system must represent each supported cryptocurrency with exactly one chosen listing.
- FR-11c: The crypto listing-selection policy must rank candidate venues in this order:
  - highest sustained turnover
  - best historical data completeness
  - fixed venue priority
- FR-11d: If no candidate venue for a cryptocurrency meets the trust bar, the system must exclude that cryptocurrency from the supported universe.

### 3.2 Market Data Ingestion and Storage

- FR-12: The system must ingest and store daily closing prices as historical records.
- FR-13: The system must ingest and store the current day's opening price for current-day evaluation.
- FR-14: The system must support an initial historical fill for supported instruments.
- FR-15: The initial historical fill must generate historical prices, supporting statistics, and historical `Dip`/`Skyrocket` events.
- FR-16: The system must support ongoing daily refresh of market data for supported exchanges.
- FR-17: The system must use multiple external data sources to maximize data availability.
- FR-18: When multiple candidate values exist for the same business datum, the system must choose the published value using one global source-prioritization policy.
- FR-19: The global source-prioritization policy must rank candidate values in this order:
  - historical reliability
  - ratio of historical prices available for the instrument from that source
  - exchange coverage quality
  - fixed source order

### 3.3 Signal Generation

- FR-20: The system must compute only `Dip` and `Skyrocket` backend signals.
- FR-21: The system must use the existing alert algorithm for signal generation.
- FR-22: The system must persist the supporting statistics and reasoning context produced or required by the algorithm.
- FR-23: The system must not evaluate user-defined `Custom` alerts.
- FR-24: The system must generate signals only when the required price and historical inputs are available.
- FR-25: The system must allow signal generation to be unavailable for a supported instrument until enough history exists.

### 3.4 Exchange Publication and Readiness

- FR-26: The system must track daily readiness at the exchange level.
- FR-27: The system must publish each exchange independently.
- FR-28: The system must consider an exchange/day eligible for publication only after all eligible instruments for that exchange/day have reached a terminal load outcome for that day.
- FR-29: Terminal load outcomes must include successful load and failed load.
- FR-30: The system must compute exchange/day coverage for publication decisions.
- FR-31: The system must mark an exchange/day as `ready` only when coverage exceeds 99%.
- FR-32: The coverage denominator must be based on eligible instruments for that exchange/day.
- FR-33: Instruments under temporary suspicion of delisting may be excluded from the coverage denominator if they meet the system's delisting-suspicion rule.
- FR-34: The system must mark an instrument as delisting-suspected after 2 consecutive expected trading days without a price, excluding weekends and exchange holidays from that count.
- FR-35: Once an exchange/day is published as `ready`, it must normally be treated as the trusted daily publication for app consumption.
- FR-36: The system must support exceptional explicit reprocessing or recomputation after publication.

### 3.5 Historical Retention and Lifecycle

- FR-37: The system must retain at least the rolling 1 year of history needed for signal computation.
- FR-38: The system may retain more than 1 year of history when capacity allows.
- FR-39: The system must support an ad hoc cutoff function to reduce retained history.
- FR-40: The maximum retained history supported by the cutoff policy must be 3 years.
- FR-41: Retention rules must apply consistently across prices, signal events, and supporting statistics.
- FR-42: Delisted instruments must leave the supported universe after a 5-day buffer.

### 3.6 Operational Visibility

- FR-43: The system must provide a compact operator view focused on exceptions, readiness, and data-quality investigation.
- FR-44: The main operator view must provide two separate load tables:
  - today opening prices load
  - yesterday historical load
- FR-45: The operator must be able to filter the load dashboard by day.
- FR-46: Both load tables must show the same columns for each exchange/day row.
- FR-47: For each exchange/day load row, the operator view must show at minimum:
  - exchange
  - status
  - publication readiness
  - start time
  - finish time
  - total eligible instruments
  - successful loads
  - failed loads
  - coverage percentage
  - quality score or quality result
  - degraded flag
  - notes or exceptions count
- FR-48: The system must distinguish the following exchange/day statuses at minimum:
  - `not started`
  - `in progress`
  - `ready`
  - `partial/problematic`
  - `failed`
  - `market closed`
- FR-49: The system must provide a separate universe-change and exclusion dashboard for support-state history.
- FR-50: The universe-change and exclusion dashboard must support filtering by event type and optionally by exchange and instrument.
- FR-51: The universe-change and exclusion dashboard must support at least these event types:
  - `added`
  - `removed`
  - `excluded`
  - `delisting_suspected`
  - `delisted_removed`
  - `restored`
  - `degraded`
  - `degradation_cleared`
- FR-52: Each universe-change and exclusion row must show at minimum:
  - effective day
  - event type
  - instrument
  - exchange
  - instrument type
  - reason
  - details
  - old state
  - new state
- FR-53: The `details` field may be optional and should be populated when the reason alone is not sufficient to explain the change.
- FR-54: The operator view must support visibility into exclusions and supported-universe changes.
- FR-55: If a production exchange repeatedly misses the quality bar, the system must keep it supported but represent it internally as degraded while investigation is ongoing.

### 3.7 Validation and Change Governance

- FR-56: The system must support a short pre-production validation path for new exchanges.
- FR-57: A new exchange must not enter production support until validation shows acceptable:
  - instrument discovery quality
  - primary-listing selection behavior
  - daily load completeness
  - daily load timeliness
  - historical load completeness
  - historical load timeliness
- FR-58: Historical published results must remain stable by default.
- FR-59: Historical recomputation must occur only through explicit action.
- FR-60: Changes to the signal algorithm must be validated against historical data before production rollout.

## 4. Non-Functional Requirements

### 4.1 Data Freshness

- NFR-1: The system is a daily-granularity system and does not provide intraday freshness.
- NFR-2: Exchange/day publication should occur within 30 minutes of the relevant daily market event window used by the product.

### 4.2 Quality

- NFR-3: The system's quality priorities must be ordered as:
  - completeness
  - correctness
  - timeliness
  - consistency
- NFR-4: Exchange/day publication must require greater than 99% completeness for eligible instruments.
- NFR-5: Instrument-level gaps must influence exchange/day quality assessment even though publication is exchange-scoped.
- NFR-6: Correctness must be evaluated at the exchange level using a small but statistically significant fixed benchmark sample per exchange, focused on important instruments.
- NFR-7: An exchange/day correctness issue exists when benchmark mismatches exceed 5%.
- NFR-8: If trusted reference data is delayed, exchange/day publication may proceed and correctness validation may be completed afterward.

### 4.3 Reliability

- NFR-9: Missing prices caused by backend loading problems must be treated as backend failures.
- NFR-10: The system should require operator intervention only for exceptional failures, not normal daily operation.
- NFR-11: The system must remain trustworthy under constrained free-source usage by using source diversity rather than assuming one source is always available.

### 4.4 Availability and Continuity

- NFR-12: The mobile app must be able to determine whether an exchange's current-day dataset is ready before attempting a full exchange refresh.
- NFR-13: The system must support partial market availability across exchanges because exchanges publish independently.

### 4.5 Cost Sensitivity

- NFR-14: The system must operate under near-zero external data-acquisition cost.
- NFR-15: Ongoing cost expectations are limited essentially to VPS hosting.

### 4.6 Operational Sustainability

- NFR-16: The system must be sustainable for operation and maintenance by a single owner.
- NFR-17: The system should favor automation and compact operator visibility over routine manual review.

### 4.7 Scalability Expectation

- NFR-18: The system must support meaningful future growth in exchanges, supported instruments, and app usage without requiring a change in product scope.

### 4.8 Security Expectations

- NFR-19: The system must expose only supported instruments and supported data views to the app.
- NFR-20: Administrative capabilities such as exchange scope changes, reprocessing, and validation should be restricted to authorized operator use.

## 5. Data & Domain Behavior

### 5.1 Key Entities

- Exchange: A supported market publishing unit. Each exchange has daily load states, readiness states, quality outcomes, and support status.
- Instrument: A supported security or asset selected within an exchange and instrument-type scope.
- Instrument Type: Category such as stock, ETF, ETN, or crypto.
- `CRY` Exchange: A synthetic exchange grouping used to represent supported cryptocurrencies under one exchange-level publication model.
- Daily Price Record: Historical close or current-day open used by the system's daily model.
- Signal Event: A `Dip` or `Skyrocket` event generated by the backend.
- Signal Statistics: Historical or current supporting values used by the alert algorithm.
- Exchange-Day Load: The operational record for a given exchange on a given day.
- Universe Change Record: A lightweight history record explaining additions, removals, exclusions, degradations, and related reasons.

### 5.2 Instrument Lifecycle

An instrument may progress through these conceptual states:

- discovered candidate
- supported for price data
- signal not yet available
- signal eligible
- delisting suspected
- removed from active support
- historical only

### 5.3 Exchange-Day Lifecycle

An exchange/day may progress through these conceptual statuses:

- not started
- in progress
- market closed
- partial/problematic
- ready
- failed

### 5.4 Data Behavior Over Time

- Historical closing prices accumulate over time.
- Current-day opening prices represent the live daily evaluation anchor.
- Supporting statistics evolve as new daily data is added.
- Signal events are generated when the algorithm identifies significant movement.
- Published historical records remain stable unless explicitly reprocessed.
- Removed instruments stop changing, but their historical record remains available subject to retention rules.

### 5.5 Relationships and Constraints

- Each instrument belongs to one chosen supported listing in the final universe.
- Each instrument belongs to one instrument type.
- Each exchange/day publication covers that exchange's eligible instruments for that day.
- Signal generation depends on sufficient historical price context.
- App visibility is limited to supported instruments and published data.

## 6. System Boundaries & External Dependencies

### 6.1 External Dependencies

The system depends on:

- External market data providers or data-loading sources
- Exchange calendars or equivalent market-open/market-closed determination
- Admin-provided scope choices for exchanges and instrument types

### 6.2 Dependency Failure Behavior

- If a market is legitimately closed, no price-based computation should occur for that exchange/day.
- If price data is missing because a load failed, the event must be treated as a backend failure.
- If external sources disagree, the system must resolve values using the global prioritization policy.
- If external sources are limited or partially unavailable, the system should use alternate free sources where possible.
- If repeated quality issues affect an exchange, that exchange remains supported but is internally degraded.

## 7. API-Level Behavior (Conceptual)

### 7.1 Supported Universe Retrieval

Interaction:

- Request the list of supported instruments within the current supported universe.

Conceptual output:

- Supported instruments only
- Instrument identity and category
- Enough current support state to distinguish price availability from signal readiness

Error scenarios:

- Exchange not supported
- Requested scope invalid

### 7.2 Exchange Readiness Retrieval

Interaction:

- Request readiness/publication state for one or more exchanges.

Conceptual output:

- Exchange identifier
- Current day readiness state
- Publication availability
- Optional quality-related summary for app refresh decisions

Error scenarios:

- Unknown exchange
- No current-day load state available

### 7.3 Current-Day Price Retrieval

Interaction:

- Request today's published prices for a supported exchange or supported instruments.

Conceptual output:

- Current-day opening-price-based published data for published exchanges
- Only trusted published results for exchanges marked ready

Error scenarios:

- Exchange not ready
- Instrument unsupported
- Exchange market closed with no publication expected

### 7.4 Historical Price Retrieval

Interaction:

- Request recent historical price data.

Conceptual output:

- Daily historical prices
- Optimized conceptual use cases:
  - yesterday's historical record as part of daily app operation
  - latest 30 days for post-install bootstrap

Error scenarios:

- Instrument unsupported
- Requested history outside retention window

### 7.5 Signal Retrieval

Interaction:

- Request published `Dip` and `Skyrocket` events and their supporting context.

Conceptual output:

- Published signal events
- Supporting reasoning context already defined by the existing algorithm
- Signal absence distinguished from signal unavailability

Error scenarios:

- Instrument supported but not yet signal-eligible
- Exchange not published for the day

### 7.6 Operator Monitoring Retrieval

Interaction:

- Request operational views by exchange and day.

Conceptual output:

- Daily and historical load status
- Separation between today opening-price loads and yesterday historical loads
- Timing
- Quality outcomes
- Exceptions
- Universe changes and exclusions

Error scenarios:

- Unknown exchange/day
- No operational data recorded for requested scope

## 8. Edge Cases & Failure Scenarios

- A company appears on multiple exchanges. The system must choose one primary/best listing using the global policy.
- An instrument matches exchange scope but is too obscure or problematic. The system may exclude it.
- A newly admitted instrument has insufficient history. The app may receive price data but no signal readiness.
- An exchange is closed for the day. No computation should happen for that exchange/day.
- An exchange/day has failed instrument loads. The system may publish only if all eligible instruments reached terminal outcomes and exchange/day coverage exceeds 99%.
- A subset of instruments appears missing because they are suspected delistings. Those may be excluded from the completeness denominator after 2 consecutive expected trading days without a price, excluding weekends and exchange holidays.
- A free source rate limit is reached. The system should continue through alternate sources where possible.
- Different sources provide different values. The system must resolve using the global prioritization policy.
- A cryptocurrency is available from multiple venues. The system must expose only one chosen listing for that asset under the synthetic `CRY` exchange using the crypto venue-selection rule.
- A historical day was published incorrectly. The system may support explicit reprocessing.
- An algorithm change is proposed. It must be historically validated before production use.

## 9. Constraints

- The system is daily only.
- The system must reuse the existing alert algorithm.
- The system must not own user-specific alert logic.
- The system must be production-grade from the start, even with limited exchange scope.
- The system must be operable by a single owner.
- The system must rely on free sources or free-tier access for data loading.
- The system should favor completeness over correctness, correctness over timeliness, and timeliness over consistency when tradeoffs must be surfaced.
- The system should start with NYSE, Nasdaq, and PSE and expand only when new exchanges pass validation.
- The system must preserve low routine operator burden.

## 10. Assumptions

- The existing algorithm already defines the app-facing reasoning context for `Dip` and `Skyrocket`.
- One year of historical data is sufficient for the algorithm's statistical needs.
- Greater retained history is desirable for trust and recovery, but not required for signal correctness.
- The app's primary history usage is:
  - yesterday's historical data during daily use
  - a one-time 30-day historical bootstrap after install
- When crypto is introduced, supported cryptocurrencies are grouped under a synthetic `CRY` exchange and selected using the crypto venue-selection rule.
- Exchange/day readiness is sufficient for app refresh behavior; the app does not need per-instrument SLA states.

## 11. Open Questions

No currently unresolved questions are considered blocking for system specification.

## 12. Acceptance Criteria

- AC-1: The system supports NYSE, Nasdaq, and Prague Stock Exchange as initial production exchanges.
- AC-2: The system exposes only supported instruments to the app.
- AC-3: The system automatically discovers and maintains instruments within admin-selected exchanges and instrument types.
- AC-4: The system applies the primary/best-listing selection rule in this order: home exchange, highest turnover, fixed exchange priority.
- AC-5: The system can exclude instruments with persistently low turnover or stale/missing data.
- AC-6: The system stores historical closing prices and current-day opening prices.
- AC-7: The system performs initial historical fill and generates historical prices, signal events, and supporting statistics.
- AC-8: The system computes only `Dip` and `Skyrocket` backend signals.
- AC-9: The system does not own or evaluate `Custom` alert rules.
- AC-10: A newly admitted instrument can appear in app price data before it is signal-eligible.
- AC-11: An exchange/day is not marked ready until all eligible instruments have terminal outcomes and coverage exceeds 99%.
- AC-12: Instruments under accepted delisting suspicion can be excluded from the publication denominator after 2 consecutive expected trading days without a price, excluding weekends and exchange holidays.
- AC-13: Each exchange publishes independently.
- AC-14: The app can determine whether an exchange is ready before requesting full current-day exchange data.
- AC-15: Published exchange/day data is typically available within 30 minutes.
- AC-16: Historical retention can be reduced through an ad hoc cutoff, with a maximum supported retained window of 3 years.
- AC-17: Delisted instruments leave active support after 5 days but retain historical records.
- AC-18: The system retains prices, signal events, and supporting statistics consistently under the same retention policy.
- AC-19: The operator view can show separate today-opening and yesterday-historical load tables with status, timing, and quality.
- AC-20: The operator view distinguishes at least `not started`, `in progress`, `ready`, `partial/problematic`, `failed`, and `market closed`.
- AC-21: The system provides a separate universe-change and exclusion dashboard filterable by event type and optionally by exchange and instrument.
- AC-22: The universe-change and exclusion dashboard supports at least these event types: `added`, `removed`, `excluded`, `delisting_suspected`, `delisted_removed`, `restored`, `degraded`, and `degradation_cleared`.
- AC-23: Each universe-change and exclusion row shows at minimum effective day, event type, instrument, exchange, instrument type, reason, details, old state, and new state.
- AC-24: The system uses the agreed global source-prioritization order when candidate values conflict.
- AC-25: Exchange-level correctness can be evaluated using a small but statistically significant benchmark sample focused on important instruments, with a 5% mismatch threshold.
- AC-26: The system supports short-window validation for onboarding a new exchange.
- AC-27: A new exchange cannot be promoted to production until discovery quality, primary-listing selection behavior, and daily/historical load completeness and timeliness are validated.
- AC-28: The system supports explicit exceptional reprocessing of published data.
- AC-29: Historical published results remain stable unless explicitly reprocessed.
- AC-30: Algorithm changes require historical validation before production rollout.
- AC-31: The system treats `crypto` as cryptocurrencies themselves, not crypto ETFs.
- AC-32: The system groups supported cryptocurrencies under a synthetic `CRY` exchange.
- AC-33: The system represents each supported cryptocurrency with exactly one chosen listing using this rule: highest sustained turnover, then best historical data completeness, then fixed venue priority.
- AC-34: The system excludes a cryptocurrency if no candidate venue meets the trust bar.

## 13. Out of Scope

- Intraday price handling
- Backend-side `Custom` alert evaluation
- User-specific alert subscriptions or alert-state ownership
- Notification delivery mechanics
- App-facing operational SLA dashboards
- Manual approval of individual instruments before support
- Heavy admin workflows as part of normal operation
- Broad unsupported-universe discovery in the app
