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

All three launch exchanges are mandatory for launch. Prague Stock Exchange must meet the same trust bar as NYSE and Nasdaq; if validation fails, launch remains blocked until the source discovery, loading, or validation strategy is improved enough for PSE to pass.

Initial launch priority is:

- Stocks
- ETFs
- ETNs

Crypto is not part of launch scope and is reserved for future expansion. If introduced later, it should only be admitted if it can meet the same trust bar. In this specification, `crypto` refers to cryptocurrencies themselves, not crypto ETFs.

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
   - automatically derived exchange activity priority
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

1. A historical adjusted-close data issue is identified.
2. The system performs explicit backend recomputation or reprocessing for affected historical records.
3. Stored historical prices and dependent backend statistics may be corrected in backend records.
4. The mobile app can pick up corrected historical records through a routine once-daily correction sync.

Production boundaries:

- After app launch, signal algorithm changes must apply prospectively only; previously delivered app alerts must not be retrospectively rewritten.
- Retrospective signal recomputation is allowed during development and pre-launch validation only.
- A bad published current-day opening price is not treated as a normal reprocessing case. Because opening prices drive alert triggers, the loading and validation process must be strengthened to prevent incorrect opening-price publication.

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
  - automatically derived exchange activity priority based on trailing 60 trading-day average total traded value across supported/candidate listings, normalized to USD/EUR-equivalent for cross-market comparison
- FR-6a: The system must recompute exchange activity priority during exchange validation and periodically, initially monthly, so larger and more active exchanges are prioritized and newly added exchanges enter the priority order automatically.
- FR-7: The system must support automatic exclusion of obscure or problematic instruments using the launch exclusion rule:
  - Low-turnover exclusion applies only after a 60 trading-day review window.
  - For NYSE and Nasdaq, the initial low-turnover threshold is median daily traded value below USD 100,000.
  - For Prague Stock Exchange, the initial threshold is the local-currency equivalent of USD 100,000, adjusted after trial validation if needed.
  - Stale/missing-data exclusion applies when an instrument has missing or invalid prices on 3 of the last 10 expected trading days, unless the instrument is already covered by the 2-day delisting-suspicion rule.
  - Manually protected benchmark instruments may be exempted from automatic exclusion when needed for correctness checks.
- FR-8: The system must expose only the supported universe to the app.
- FR-9: The system must record instrument additions, removals, exclusions, and degradations with explicit reasons in a lightweight historical record.
- FR-9a: The system must record symbol, name, and identifier changes as lightweight universe-change events when detected.
- FR-9b: The system must store stable provider or reference identifiers when available, but launch scope does not require a full corporate-action engine.
- FR-9c: Suspected split or corporate-action anomalies must be flagged for operator review rather than automatically rewriting current-day opening prices or signal history.
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

- FR-12: The system must ingest and store adjusted daily closing prices as historical records.
- FR-13: The system must ingest and store the official exchange-local unadjusted current-day opening price for current-day evaluation.
- FR-13a: Each stored price record must include the price currency, because currencies vary by exchange and listing.
- FR-13b: Halted, suspended, or late-open instruments must be marked pending or failed according to load rules rather than assigned an invented fallback price.
- FR-14: The system must support an initial historical fill for supported instruments.
- FR-15: The initial historical fill must generate historical prices, supporting statistics, and historical `Dip`/`Skyrocket` events.
- FR-16: The system must support ongoing daily refresh of market data for supported exchanges.
- FR-17: The system must use multiple external data sources to maximize data availability.
- FR-17a: Individual free or free-tier sources are not expected to satisfy completeness, speed, or robustness requirements by themselves; the combined loading algorithm across multiple complementary sources must satisfy the publication criteria.
- FR-17b: Provider admission into the production loading algorithm must be based on implementation validation results, not selected during design.
- FR-18: When multiple candidate values exist for the same business datum, the system must choose the published value using one global source-prioritization policy.
- FR-19: The global source-prioritization policy must rank candidate values in this order:
  - provider/exchange reliability score
  - ratio of historical prices available for the instrument from that source
  - exchange coverage quality
  - fixed source order
- FR-19a: Provider reliability scores must be maintained per provider and exchange, because the system is price-focused and does not need separate reliability dimensions per price data type at launch.
- FR-19b: Provider/exchange reliability scores must be updated from validation and production outcomes, including benchmark matches, missing-rate, timeliness, stale data, provider errors, and disagreement frequency.
- FR-19c: The system must retain audit evidence for candidate price values, the selected source, and the reason the selected source won.

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
- FR-31a: Current-day opening-price publication must not be marked `ready` until correctness validation has completed successfully.
- FR-31b: If correctness validation is delayed or fails and blocks current-day opening-price publication, the exchange/day must remain unpublished and the condition must be immediately visible in operator dashboards and logs.
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
- FR-55a: A degraded production exchange becomes eligible for normal status after 3 consecutive expected trading days meeting all SLA baselines: greater than 99% coverage, benchmark mismatch rate at or below 5%, publication within the 30-minute target, and no unresolved provider/calendar incident affecting that exchange. Operator override is allowed for exceptional cases.
- FR-55f: If an exchange misses the 30-minute publication target on 3 of the last 5 expected trading days but eventually meets coverage and correctness, it must be marked internally degraded, shown prominently in dashboards/logs, and investigated for source-strategy or loading improvements.
- FR-55g: Repeated timeliness degradation must not lower app-facing trust. The app should see the exchange as not ready until it is ready, not receive lower-trust current-day data.
- FR-55b: Background load and processing jobs must use explicit states: `queued`, `running`, `retry_wait`, `succeeded`, `failed`, `cancelled`, and `stale_abandoned`.
- FR-55c: Only `succeeded`, `failed`, and `cancelled` job outcomes count as terminal for publication-readiness logic.
- FR-55d: Jobs must have bounded retry attempts, provider/request timeouts, idempotency keys, and worker heartbeat or lock expiry so crashed workers can be recovered.
- FR-55e: Operator manual actions may retry, cancel, or mark a job failed, but must require a recorded reason.

### 3.7 Validation and Change Governance

- FR-56: The system must support a short pre-production validation path for new exchanges.
- FR-56a: NYSE, Nasdaq, and Prague Stock Exchange are mandatory launch exchanges and must all pass the same validation and publication trust bar before launch.
- FR-56b: If Prague Stock Exchange fails validation, the system must not lower the trust bar or remove PSE from launch scope; the team must iterate on source discovery, provider combination, adapter behavior, or validation strategy until PSE can be supported successfully.
- FR-57: A new exchange must not enter production support until validation shows acceptable:
  - instrument discovery quality
  - primary-listing selection behavior
  - daily load completeness
  - daily load timeliness
  - historical load completeness
  - historical load timeliness
- FR-58: Historical published results must remain stable by default.
- FR-59: Historical recomputation must occur only through explicit action.
- FR-59a: Historical adjusted-close corrections may be propagated to the mobile app through a routine once-daily correction sync.
- FR-59b: After app launch, reprocessing must not retrospectively rewrite previously delivered app alerts or signal events due to signal-algorithm changes.
- FR-59c: Retrospective signal recomputation is allowed in development and pre-launch validation environments.
- FR-59d: Incorrect current-day opening-price publication must be treated as a prevention and quality-hardening failure, not a normal reprocessing workflow.
- FR-60: Changes to the signal algorithm must be validated against historical data before production rollout, then applied prospectively after rollout.

## 4. Non-Functional Requirements

### 4.1 Data Freshness

- NFR-1: The system is a daily-granularity system and does not provide intraday freshness.
- NFR-2: Exchange/day publication should occur within 30 minutes of the relevant daily market event window used by the product.
- NFR-2a: Repeated 30-minute target misses are internal degradation events, not app-visible partial-quality states.

### 4.2 Quality

- NFR-3: The system's quality priorities must be ordered as:
  - completeness
  - correctness
  - timeliness
  - consistency
- NFR-4: Exchange/day publication must require greater than 99% completeness for eligible instruments.
- NFR-5: Instrument-level gaps must influence exchange/day quality assessment even though publication is exchange-scoped.
- NFR-6: Correctness must be evaluated at the exchange level using a small fixed benchmark sample per exchange, selected from the top 20 most active supported instruments by trailing 60 trading-day traded value. Candidate lists refresh during exchange validation and monthly review, but the active benchmark set remains stable unless a benchmark becomes invalid or delisted.
- NFR-7: An exchange/day correctness issue exists when benchmark mismatches exceed 5%.
- NFR-8: Current-day opening-price publication must wait for successful correctness validation; delayed or failed correctness validation must block publication for the affected exchange/day.
- NFR-8a: Blocked current-day publication due to correctness validation delay or failure is a serious load-quality failure and should be rare in normal operation. If most exchanges are blocked routinely, the loading, validation, or source strategy has failed the product requirement.

### 4.3 Reliability

- NFR-9: Missing prices caused by backend loading problems must be treated as backend failures.
- NFR-10: The system should require operator intervention only for exceptional failures, not normal daily operation.
- NFR-10a: The system must not require manual operator time tracking. Operational burden should be inferred from KPI exception volume, recurrence, and unresolved incident counts.
- NFR-10b: Routine operations are considered acceptable when backend KPIs are consistently met; repeated KPI misses, unresolved degraded exchanges, recurring validation blocks, backup failures, worker failures, or repeated publication delays indicate operational burden that requires automation, source-strategy improvement, dashboard improvement, or scope discipline for future expansion.
- NFR-11: The system must remain trustworthy under constrained free-source usage by using source diversity rather than assuming one source is always available.
- NFR-11a: Source diversity may include splitting the supported universe across complementary free sources when rate limits, speed limits, or coverage gaps prevent any one source from meeting the target alone.

### 4.4 Availability and Continuity

- NFR-12: The mobile app must be able to determine whether an exchange's current-day dataset is ready before attempting a full exchange refresh.
- NFR-13: The system must support partial market availability across exchanges because exchanges publish independently.
- NFR-13a: Launch recovery targets are frugal: tolerate up to 24 hours of data loss for historical and backoffice data after a severe infrastructure failure, and target restoration within 24 hours after VPS loss.
- NFR-13b: The system must support automated daily local PostgreSQL and configuration/file backups, plus at least weekly manual off-machine backup copies.
- NFR-13c: Restore must be tested before launch and after meaningful schema changes.

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
- NFR-21: Mobile app credentials must be treated as app identification and throttling controls, not permanent secrets, because embedded mobile credentials can be extracted.
- NFR-22: The system must support mobile API key or signed-token rotation with overlapping old/new credentials, revocation of abused credentials, and rate limiting by IP, device/app identifier, app version, or similar available request attributes.
- NFR-23: Full backend end-user accounts are out of scope unless future app features require user-specific backend state.

## 5. Data & Domain Behavior

### 5.1 Key Entities

- Exchange: A supported market publishing unit. Each exchange has daily load states, readiness states, quality outcomes, and support status.
- Instrument: A supported security or asset selected within an exchange and instrument-type scope.
- Instrument Type: Category such as stock, ETF, ETN, or crypto.
- `CRY` Exchange: A synthetic exchange grouping used to represent supported cryptocurrencies under one exchange-level publication model.
- Daily Price Record: Adjusted historical close or official exchange-local unadjusted current-day open used by the system's daily model, including the price currency.
- Signal Event: A `Dip` or `Skyrocket` event generated by the backend.
- Signal Statistics: Historical or current supporting values used by the alert algorithm.
- Exchange-Day Load: The operational record for a given exchange on a given day.
- Universe Change Record: A lightweight history record explaining additions, removals, exclusions, degradations, and related reasons.
- Identifier Record: Provider or reference identifiers stored when available to help preserve instrument continuity across symbol or name changes.

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

- Adjusted historical closing prices accumulate over time.
- Official exchange-local unadjusted current-day opening prices represent the live daily evaluation anchor.
- Price records preserve the currency of the listing or exchange-specific price.
- Halted, suspended, or late-open instruments remain pending or fail according to load rules rather than receiving invented prices.
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
- An exchange/day current-day opening-price load has not passed correctness validation. The system must not publish that exchange/day as ready; the failure must be highly visible in dashboards and logs.
- A subset of instruments appears missing because they are suspected delistings. Those may be excluded from the completeness denominator after 2 consecutive expected trading days without a price, excluding weekends and exchange holidays.
- A free source rate limit is reached. The system should continue through alternate sources where possible.
- Multiple free sources may each be incomplete or speed-limited, but the aggregate loading algorithm may still pass if sources complement each other across instruments, exchanges, or load phases.
- Different sources provide different values. The system must resolve using the global prioritization policy.
- Provider reliability differs by exchange. The system should score source reliability per provider and exchange, learn from validation and production outcomes, and retain candidate-value audit evidence.
- A provider reports a symbol, name, identifier, split, or corporate-action-like change. The system should rely on adjusted close for historical continuity, store stable identifiers where available, record symbol/name/identifier changes as universe-change events, and flag suspected split or corporate-action anomalies for operator review.
- A cryptocurrency is available from multiple venues. The system must expose only one chosen listing for that asset under the synthetic `CRY` exchange using the crypto venue-selection rule.
- A historical adjusted-close record was published incorrectly. The system may support explicit reprocessing, and the app can pick up corrected historical records during its routine once-daily correction sync.
- An algorithm change is proposed. It must be historically validated before production use. After app launch, the changed algorithm applies only to new signal computation going forward.
- A current-day opening price would be published incorrectly. The system must prevent publication through stronger validation and loading safeguards rather than relying on normal reprocessing.

## 9. Constraints

- The system is daily only.
- The system must reuse the existing alert algorithm.
- The system must not own user-specific alert logic.
- The system must be production-grade from the start, even with limited exchange scope.
- The system must be operable by a single owner.
- The system must rely on free sources or free-tier access for data loading.
- The system should favor completeness over correctness, correctness over timeliness, and timeliness over consistency when tradeoffs must be surfaced.
- The system must launch with NYSE, Nasdaq, and PSE all passing the same trust bar, and expand only when new exchanges pass validation.
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
- AC-1a: Launch is blocked until NYSE, Nasdaq, and Prague Stock Exchange all meet the same validation and publication trust bar.
- AC-2: The system exposes only supported instruments to the app.
- AC-3: The system automatically discovers and maintains instruments within admin-selected exchanges and instrument types.
- AC-4: The system applies the primary/best-listing selection rule in this order: home exchange, highest turnover, automatically derived exchange activity priority.
- AC-5: The system excludes low-turnover instruments after a 60 trading-day review window when median daily traded value is below the launch threshold, and excludes stale/missing-data instruments after missing or invalid prices on 3 of the last 10 expected trading days, with protected benchmark exceptions allowed.
- AC-6: The system stores adjusted historical closing prices, official exchange-local unadjusted current-day opening prices, and the currency for each stored price record.
- AC-7: The system performs initial historical fill and generates historical prices, signal events, and supporting statistics.
- AC-8: The system computes only `Dip` and `Skyrocket` backend signals.
- AC-9: The system does not own or evaluate `Custom` alert rules.
- AC-10: A newly admitted instrument can appear in app price data before it is signal-eligible.
- AC-11: An exchange/day current-day opening-price publication is not marked ready until all eligible instruments have terminal outcomes, coverage exceeds 99%, and correctness validation has completed successfully.
- AC-12: Instruments under accepted delisting suspicion can be excluded from the publication denominator after 2 consecutive expected trading days without a price, excluding weekends and exchange holidays.
- AC-13: Each exchange publishes independently.
- AC-14: The app can determine whether an exchange is ready before requesting full current-day exchange data.
- AC-15: Published exchange/day data is typically available within 30 minutes; an exchange missing that target on 3 of the last 5 expected trading days is internally degraded and requires investigation while the app continues to see only ready/not-ready behavior.
- AC-16: Historical retention can be reduced through an ad hoc cutoff, with a maximum supported retained window of 3 years.
- AC-17: Delisted instruments leave active support after 5 days but retain historical records.
- AC-18: The system retains prices, signal events, and supporting statistics consistently under the same retention policy.
- AC-19: The operator view can show separate today-opening and yesterday-historical load tables with status, timing, and quality.
- AC-20: The operator view distinguishes at least `not started`, `in progress`, `ready`, `partial/problematic`, `failed`, and `market closed`.
- AC-20a: The operator view surfaces KPI exceptions and recurring failures clearly enough that operational burden can be judged from backend health signals rather than manual time logging.
- AC-21: The system provides a separate universe-change and exclusion dashboard filterable by event type and optionally by exchange and instrument.
- AC-22: The universe-change and exclusion dashboard supports at least these event types: `added`, `removed`, `excluded`, `delisting_suspected`, `delisted_removed`, `restored`, `degraded`, and `degradation_cleared`.
- AC-23: Each universe-change and exclusion row shows at minimum effective day, event type, instrument, exchange, instrument type, reason, details, old state, and new state.
- AC-24: The system uses the agreed global source-prioritization order when candidate values conflict, backed by provider/exchange reliability scores and candidate-value audit evidence.
- AC-24a: The system tracks symbol, name, and identifier changes as universe-change events, stores stable provider/reference identifiers when available, and flags suspected split or corporate-action anomalies for operator review without requiring a full corporate-action engine at launch.
- AC-25: Exchange-level correctness is evaluated using a small fixed benchmark sample selected from the top 20 most active supported instruments by trailing 60 trading-day traded value, with manual protection from automatic exclusion and a 5% mismatch threshold; current-day opening-price publication is blocked until this validation succeeds.
- AC-26: The system supports short-window validation for onboarding a new exchange.
- AC-27: A new exchange cannot be promoted to production until discovery quality, primary-listing selection behavior, and daily/historical load completeness and timeliness are validated.
- AC-28: The system supports explicit exceptional reprocessing of historical adjusted-close records and dependent backend statistics.
- AC-29: Historical published results remain stable unless explicitly reprocessed, and the app can pick up corrected historical records through a routine once-daily correction sync.
- AC-30: Algorithm changes require historical validation before production rollout and apply prospectively after launch rather than rewriting previously delivered app alerts.
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
