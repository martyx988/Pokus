# Architecture Review

## Executive Summary

Overall risk level: **high-medium**.

The recommended architecture, a modular monolith with separate API and worker processes, is directionally sensible for a daily market-data backend. The concern is not the top-level shape. The concern is that the architecture claims low cost and single-owner maintainability while carrying a large amount of data-quality, universe-management, validation, reprocessing, and operational logic.

The biggest risks are external data reliability, the real complexity of global universe selection, correctness validation after publication, under-specified job recovery, and a fragile single-VPS continuity model. The architecture is not overengineered in deployment style, but it is likely overengineered in domain rules for a first production launch.

## Critical Risks

### 1. Free data sources may not meet the trust bar

- **Issue**: The design depends on multiple free or free-tier providers for opening prices, historical closes, volume/turnover, instrument discovery, identifiers, and validation.
- **Why it matters**: The product requires greater than 99% coverage, correctness checks, publication within 30 minutes, and stable historical records. Free sources frequently have delays, incomplete exchange coverage, changing formats, rate limits, adjusted/unadjusted differences, and weak discovery data.
- **Impact**: Daily publication failures, false readiness, incorrect signals, excessive operator investigation, or forced scope reduction.
- **Where it appears**: Market Data Provider Adapter Layer, Ingestion Module, Performance Strategy, Risks, product FR-17 through FR-19, NFR-11, NFR-14.

### 2. Opening price semantics require strict implementation

- **Issue**: Resolver decision now defines the authoritative price semantics, but implementation must enforce them consistently across providers.
- **Resolved decision**: Current-day evaluation uses the official exchange-local unadjusted open. Historical records use adjusted close. Each stored price record must include its currency. Halted, suspended, or late-open instruments are marked pending or failed according to load rules rather than assigned an invented fallback price.
- **Why it matters**: Signals are based on the opening price. If the opening price is inconsistent, the system can generate false `Dip` and `Skyrocket` events while still appearing operationally healthy.
- **Impact**: Bad signals and loss of user trust despite high apparent coverage.
- **Where it appears**: Ingestion Module, Signal Generation Module, Source prioritization, API Current-Day Prices.

### 3. Current-day publication must wait for correctness validation

- **Resolved item**: Current-day opening-price publication must wait for successful correctness validation. If validation is delayed or fails, the affected exchange/day remains unpublished and the condition must be immediately visible in operator dashboards and logs.
- **Why it matters**: Opening prices drive alert triggers, so `ready` must mean the current-day opening-price dataset has passed correctness validation.
- **Implementation expectation**: Correctness-validation blocks should be true exceptions. If most exchanges are blocked routinely, the loading, validation, or source strategy has failed the product requirement.
- **Where it appears**: Performance Strategy, Quality assumptions, product NFR-8.

### 4. Job correctness is mission-critical but still abstract

- **Issue**: The design calls for idempotency, locks, retries, terminal states, and reprocessing, but does not define the state machine, ownership of terminal outcomes, retry exhaustion rules, or recovery behavior after worker crashes.
- **Why it matters**: Exchange/day readiness depends on terminal outcomes for every eligible instrument. A single stuck or duplicated job can block publication or corrupt outcomes.
- **Impact**: Missed publication windows, duplicate writes, silent partial data, or manual database repair.
- **Where it appears**: Worker/Scheduler Process, Ingestion Module, Publication Module, Failure Handling.

### 5. Universe management is much more complex than the architecture admits

- **Issue**: The system must discover instruments, resolve multi-listings, compute home exchange, track turnover, normalize currencies, derive exchange activity priority, protect benchmark instruments, handle exclusions, track delisting suspicion, and preserve historical identity.
- **Why it matters**: This is not just an admin helper. It is core data-governance logic with many ambiguous cases and weak external-source support.
- **Impact**: Incorrect supported universe, duplicate companies, unstable app-visible coverage, misleading historical continuity, and heavy operator investigation.
- **Where it appears**: Universe Management Module, Data Model Overview, product FR-3 through FR-11.

### 6. Single-VPS continuity conflicts with production-grade trust

- **Issue**: API, worker, database, backups, reverse proxy, and observability all run on one VPS. Backups are daily local overwrites plus manual ad hoc unencrypted off-machine copies.
- **Why it matters**: A VPS disk failure, bad deployment, database corruption, or accidental deletion can compromise both current service and recovery state.
- **Impact**: Extended outage, data loss beyond acceptable expectations, or inability to reconstruct published history.
- **Where it appears**: Deployment / Hosting, Security and Access Control, Backups, Availability assumptions.

### 7. Historical close reprocessing can undermine historical stability

- **Issue**: The architecture allows explicit historical adjusted-close reprocessing, while signal algorithm changes are prospective after launch and bad current-day opening-price publication should be prevented rather than repaired through normal reprocessing.
- **Why it matters**: Historical stability is a core product promise. Even narrowed historical close correction can create confusion if audit evidence and app correction sync are weak.
- **Impact**: Conflicting historical records, app charts changing without clear cause, operator uncertainty, or weak traceability for corrected historical values.
- **Where it appears**: Publication Module, Read Model Builder, Admin Commands, Failure Handling, product FR-36 and FR-58 through FR-60.

## Overengineering Flags

### 1. Global primary/best-listing policy at launch

- **Component / Pattern**: Home exchange, turnover, derived exchange activity priority, currency normalization, and monthly recomputation.
- **Why it may be overkill**: This is a sophisticated global-market data-governance problem before the system has proven reliable for three launch exchanges.
- **Simpler alternative**: Start with explicit exchange-scoped support plus a narrower duplicate-resolution rule for known launch cases.

### 2. Protected benchmark instruments

- **Component / Pattern**: Manual benchmark protection from automatic exclusion.
- **Why it may be overkill**: It creates a special class of instruments that can violate normal exclusion rules, which complicates coverage and quality interpretation.
- **Simpler alternative**: Keep benchmark selection outside the supported-universe lifecycle or allow benchmark replacement when data quality deteriorates.

### 3. Synthetic `CRY` exchange in the initial architecture

- **Component / Pattern**: Crypto-specific exchange and venue-selection rules appear throughout the data model despite crypto being deferred.
- **Why it may be overkill**: It adds model pressure for a future domain that behaves differently from exchange-traded securities.
- **Simpler alternative**: Reserve extension points without modeling crypto-specific production behavior now.

### 4. Read model builder for many outputs at launch

- **Component / Pattern**: Precomputed readiness, prices, history slices, signals, and operator outputs.
- **Why it may be overkill**: For modest launch traffic, this introduces refresh-order and staleness risks before measured query pressure exists.
- **Simpler alternative**: Precompute only publication-critical current-day payloads first; add more read models based on measured slow queries.

### 5. Full exchange expansion machinery before provider validation

- **Component / Pattern**: Generic exchange validation, calendar validation, source pools, and future global expansion hooks.
- **Why it may be overkill**: The launch risk is not lack of expansion machinery. It is whether NYSE, Nasdaq, and PSE can be loaded reliably under cost constraints.
- **Simpler alternative**: Hard-focus validation and operational tooling around the launch exchanges before generalizing.

## Missing or Unclear Requirements

### 1. Exact market-data semantics

- **Resolved item**: Current-day evaluation uses official exchange-local unadjusted open. Historical records use adjusted close. Each stored price record includes currency. Halted, suspended, or late-open instruments are marked pending or failed according to load rules rather than assigned an invented fallback price.
- **Why it matters**: Signals and correctness checks need a precise definition of the data being trusted.
- **Affected area**: Ingestion, source prioritization, signal generation, correctness validation.

### 2. Provider candidate policy

- **Resolved item**: The design phase should accumulate a broad pool of free candidate sources rather than choose final production providers. Licensing review is not a gating policy in this design; use workable free sources where they can contribute to the combined loading algorithm.
- **Why it matters**: Individual free sources are expected to be incomplete, rate-limited, or slow. The production bar applies to the aggregate loading algorithm across complementary sources, not to each source in isolation.
- **Affected area**: Provider adapters, cost model, business risk.

### 3. Job state machine

- **Resolved item**: Jobs use `queued`, `running`, `retry_wait`, `succeeded`, `failed`, `cancelled`, and `stale_abandoned`. Only `succeeded`, `failed`, and `cancelled` are terminal for publication logic. Jobs have bounded retries, provider/request timeouts, idempotency keys, and heartbeat or lock expiry for crashed-worker recovery. Operator-visible manual actions may retry, cancel, or mark failed, with a required reason.
- **Why it matters**: Publication readiness depends on job terminality.
- **Affected area**: Worker, ingestion, publication, operator dashboard.

### 4. Reprocessing audit model

- **Resolved item**: Reprocessing scope is narrowed. After app launch, signal algorithm changes apply prospectively only and must not rewrite app-delivered alerts. Retrospective signal recomputation is allowed only in development and pre-launch validation. Historical adjusted-close corrections may be explicitly reprocessed and picked up by the app through a routine once-daily correction sync. Bad current-day opening-price publication is treated as a prevention and quality-hardening failure rather than a normal reprocessing workflow.
- **Why it matters**: Explicit reprocessing is both necessary and dangerous.
- **Affected area**: Admin commands, publication, read models, historical stability.

### 5. Backup and restore objectives

- **Resolved item**: Launch recovery stays frugal: tolerate up to 24 hours of data loss for historical and backoffice data after severe infrastructure failure, target restoration within 24 hours after VPS loss, run automated daily local PostgreSQL/config/file backups, make manual off-machine backup copies at least weekly, and test restore before launch and after meaningful schema changes. If database corruption occurs, restore from the latest valid backup rather than attempting risky manual repair.
- **Why it matters**: Production-grade trust depends on recovery, not just daily dumps.
- **Affected area**: Deployment, operations, continuity.

### 6. Mobile API abuse expectations

- **Resolved item**: Mobile credentials are app identification and throttling controls, not permanent secrets. The API uses app-level keys or signed tokens at launch, supports overlapping rotation, revocation of abused credentials, and rate limiting by IP, device/app identifier, app version, or similar available attributes. Full backend end-user accounts remain out of scope unless future user-specific backend state requires them.
- **Why it matters**: App-level credentials are extractable from mobile clients.
- **Affected area**: Public API, security, VPS capacity.

### 7. Timezone and calendar edge cases

- **Missing / unclear item**: Market event windows by exchange, daylight saving behavior, holidays, half days, late opens, and local versus UTC storage rules.
- **Why it matters**: The 30-minute target and delisting-suspicion counters depend on correct expected trading days.
- **Affected area**: Scheduler, calendars, publication, delisting logic.

## Cost Concerns

### 1. Free-tier API limits

- **Source of cost**: Paid upgrades may become necessary for completeness, speed, or rate limits.
- **Why it may be problematic**: The business constraint assumes near-zero data acquisition cost.
- **When it becomes significant**: Initial historical fill, daily retries, PSE source gaps, or exchange expansion.

### 2. Operational time cost

- **Source of cost**: Manual investigation of data gaps, provider discrepancies, calendars, failed jobs, and reprocessing.
- **Why it may be problematic**: Single-owner time is the scarce resource.
- **When it becomes significant**: Any week with repeated provider instability or exchange-specific failures.

### 3. Observability and log retention

- **Source of cost**: Metrics dashboard, logs, health checks, alerting, and storage.
- **Why it may be problematic**: "Basic metrics" can still become a non-trivial maintenance system on a VPS.
- **When it becomes significant**: During failure investigation or when provider attempts are logged at high volume.

### 4. Backups

- **Source of cost**: Reliable off-machine backups, encryption, restore testing, and storage.
- **Why it may be problematic**: The architecture currently minimizes backup cost at the expense of recovery confidence.
- **When it becomes significant**: After the first serious VPS or database incident.

### 5. Identifier and corporate-action quality

- **Source of cost**: Reliable identifiers, split handling, delisting data, and listing metadata may require sources that are not truly free.
- **Why it may be problematic**: Without them, universe and history consistency degrade.
- **When it becomes significant**: Multi-listed companies, ETFs/ETNs, corporate actions, and Prague Stock Exchange coverage.

## Scaling Risks

### At 10x scale

- Provider rate limits and slow responses become the first bottleneck, especially for initial fill, retries, and validation.
- PostgreSQL-backed jobs can suffer from lock contention if every instrument/day/load type becomes a row-level coordination problem.
- Read models may become stale or expensive to rebuild if publication triggers broad refreshes.
- Operator dashboards may become noisy if they expose many per-instrument failures without strong grouping.
- The single VPS may need careful CPU, memory, disk I/O, and database tuning earlier than expected.

### At 100x scale

- Free-source acquisition is unlikely to remain viable for global exchange coverage and large app usage.
- A single PostgreSQL instance on one VPS becomes a hard reliability and performance ceiling.
- Initial fill and reprocessing become operationally risky because they compete with daily production jobs.
- Calendar, currency, identifier, and corporate-action handling become a data-platform problem, not a small backend feature.
- Mobile API abuse or refresh spikes can overwhelm the VPS unless caching, rate limiting, and client behavior are tightly controlled.

## Simpler Alternatives

### 1. Current approach: broad automated universe governance

- **Simpler approach**: Launch with a more constrained, explicitly validated universe policy for NYSE, Nasdaq, and PSE.
- **Tradeoff**: Less automatic expansion, but lower risk of silently wrong instrument selection.

### 2. Current approach: many provider candidates and global source priority

- **Simpler approach**: Validate a small number of preferred sources per exchange and use alternates only for gaps.
- **Tradeoff**: Less theoretical resilience, but easier debugging and clearer data provenance.

### 3. Current approach: publication before delayed correctness checks

- **Simpler approach**: Treat correctness as unknown and expose a distinct internal state until validation completes.
- **Tradeoff**: May delay or qualify readiness, but preserves the meaning of trusted publication.

### 4. Current approach: generic exchange expansion path

- **Simpler approach**: Defer generalized expansion machinery until launch exchanges are stable in production.
- **Tradeoff**: Slower future onboarding, but less early architecture surface area.

### 5. Current approach: local-only automated backup plus manual off-machine copy

- **Simpler approach**: Automate one encrypted off-machine backup target from the start.
- **Tradeoff**: Small recurring complexity or cost, but much stronger recovery posture.

## Fragile Assumptions

### 1. Free sources can satisfy completeness and timeliness

- **Why risky**: Free sources are unstable, rate-limited, delayed, and uneven across exchanges.
- **Impact if wrong**: The product cannot meet its core trust promise without reducing scope or paying for data.

### 2. The existing signal algorithm is production-ready as callable backend logic

- **Why risky**: The algorithm may have hidden dependencies, performance issues, or assumptions from the mobile/app context.
- **Impact if wrong**: Signal generation becomes a major implementation and validation project.

### 3. PostgreSQL can comfortably handle all domain, job, read-model, and audit workloads

- **Why risky**: It probably can at launch, but the architecture puts many responsibilities on one database.
- **Impact if wrong**: Locking, slow queries, or storage pressure can affect both ingestion and API reads.

### 4. One owner can operate the system routinely

- **Why risky**: The domain complexity implies frequent edge cases even if infrastructure is simple.
- **Impact if wrong**: Operational burden becomes the limiting factor, not code or hosting.

### 5. PSE can be treated like NYSE and Nasdaq with the same provider model

- **Why risky**: Prague Stock Exchange coverage is likely thinner in free global sources.
- **Resolved fallback**: PSE is mandatory for launch and the trust bar cannot be lowered. If PSE cannot pass validation, launch remains blocked while source discovery, provider combination, adapter behavior, or validation strategy is improved until PSE can pass.
- **Impact if wrong**: Launch may be delayed and PSE may need special source or adapter handling, but it should not be removed from launch scope or admitted under lower quality rules.

### 6. Exchange/day readiness is enough for app behavior

- **Why risky**: A ready exchange can still contain important missing or suspect instruments, especially near the 99% threshold.
- **Impact if wrong**: Users may see gaps or bad signals with no useful app-level explanation.

### 7. Manual off-machine backups are acceptable

- **Why risky**: Manual processes are skipped precisely when systems become busy or stressful.
- **Impact if wrong**: Data loss or long recovery after a VPS incident.

## Open Questions

No remaining unresolved architecture-review questions. Operational burden should be judged by backend KPI exception volume, recurrence, and unresolved incident counts rather than manual operator time tracking.
