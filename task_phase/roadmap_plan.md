# Roadmap Plan

## 1. Input Summary

### Architecture Direction

The approved architecture is a modular monolith deployed as separate API/web and worker/scheduler processes sharing one PostgreSQL database. The API process serves mobile app reads and private operator/admin views. The worker owns scheduled ingestion, initial fills, retries, validation, signal generation, publication checks, read-model refreshes, retention work, and explicit reprocessing.

The system is daily-granularity only. PostgreSQL is the source of truth for instrument universe state, prices, load outcomes, job state, publication state, signal statistics, signal events, audit evidence, read models, admin commands, and operational history. Free or free-tier market-data providers are isolated behind provider adapters, and production values are selected through a global source-prioritization policy.

### Key Constraints

- Launch requires New York Stock Exchange, Nasdaq, and Prague Stock Exchange. All three must meet the same validation and publication trust bar before launch.
- Launch instrument types are stocks, ETFs, and ETNs. Crypto is excluded from launch but remains part of full system scope through the synthetic `CRY` exchange model.
- Daily opening prices must be official exchange-local unadjusted opens. Historical closing prices must be adjusted closes.
- Exchange/day publication is independent per exchange and requires all eligible instruments to reach terminal outcomes, greater than 99% coverage, and successful correctness validation for current-day opening-price publication.
- Current-day opening-price publication failures must be prevented through validation and loading safeguards rather than treated as normal reprocessing.
- Published historical data is stable by default and can change only through explicit historical adjusted-close reprocessing.
- Post-launch signal algorithm changes apply prospectively. Retrospective signal recomputation is allowed only in development and pre-launch validation.
- External data acquisition cost must remain near zero, and ongoing operations should fit VPS hosting and single-owner maintainability.
- Operator visibility must focus on exceptions, readiness, quality, load timing, universe changes, degradation, backups, worker health, and recurring KPI misses.

### Critical Decisions Affecting Execution

- Build the database, domain model, job state model, and worker/API boundary before feature-specific flows, because every major capability depends on shared state, idempotent jobs, and publication rules.
- Validate provider behavior and exchange calendars early, especially for Prague Stock Exchange, because source quality can block launch and must not lower the trust bar.
- Build a narrow end-to-end daily publication slice early: configured exchange and instrument scope, universe discovery, provider loading, candidate selection, load outcomes, publication readiness, read-model refresh, and mobile readiness/current-price reads.
- Keep operator visibility in the early slice, not as a late polish item, because trust and single-owner operation depend on seeing why an exchange is not ready.
- Introduce initial historical fill and signal generation after the daily price/publication path proves the data model, provider adapters, and job reliability.
- Add explicit reprocessing, retention, backup visibility, and expansion governance after the core daily and historical flows are stable, because these depend on the same auditability and job controls.

No blocking conflicts were found between `architecture.md` and `product_spec.md`.

## 2. Core Execution Scope

The core execution scope is the minimal system slice that proves trusted end-to-end daily publication for at least one configured launch exchange while using the same architecture and rules required for all launch exchanges.

### Core Data Flow

- Admin-supported exchange and instrument-type configuration is required so the worker can determine the intended universe instead of relying on hardcoded scope.
- Universe discovery and supported-listing selection are required so ingestion operates on eligible instruments and the app only sees the supported universe.
- Exchange calendar handling is required so the system distinguishes expected trading days from market-closed days and avoids false failures.
- Daily current-day opening-price ingestion is required because app refresh and signal evaluation depend on the official opening-price anchor.
- Candidate-value capture and source-prioritized selection are required because no single free provider is assumed complete or authoritative.
- Per-instrument load outcomes are required because publication readiness depends on terminal outcomes across the eligible exchange/day universe.
- Exchange/day publication state is required because mobile clients must check readiness before requesting current-day data.
- Read-model refresh after publication is required so app-facing endpoints serve only trusted published data.
- Operator load visibility is required so failures, blocked publication, coverage, timing, and quality are inspectable from the first working slice.

### External Interactions

- At least one provider adapter path must fetch normalized price candidates, provider attempt metadata, provider errors, and provider timing.
- Exchange calendar resolution must identify trading and closed days.
- API clients must be able to retrieve readiness and current-day published prices.
- Operator/admin clients must be able to view load state and configure supported exchanges/instrument types.

### Basic Error Handling

- Jobs must persist state transitions using `queued`, `running`, `retry_wait`, `succeeded`, `failed`, `cancelled`, and `stale_abandoned`.
- Only `succeeded`, `failed`, and `cancelled` count as terminal outcomes for publication-readiness logic.
- Provider calls must use bounded retries and request timeouts.
- Ingestion writes must be idempotent by instrument, exchange-local date, load type, and source/result unit.
- Missing prices on expected trading days must be treated as backend failures unless calendar or delisting-suspicion rules apply.
- Publication must fail closed: app-facing current-day data remains unavailable until readiness rules pass.

### Minimal API Surface

- Supported universe retrieval for app-visible supported instruments and their price/signal readiness status.
- Exchange readiness retrieval for one or more exchanges.
- Current-day price retrieval for ready exchanges only.
- Private operator load table retrieval for today opening-price loads.
- Private admin configuration for supported exchanges and instrument types.

Each element is required because the product's trust model depends on a complete chain from configured scope to eligible instruments, provider evidence, selected prices, terminal load outcomes, publication readiness, app-visible read models, and operator investigation.

## 3. Full System Scope

### Exchange and Universe Management

- Admin-defined supported exchanges and instrument types.
- Automatic discovery and maintenance of instruments within supported scope.
- Initial population, additions, removals, delisting suspicion, restoration, degradation, and exclusion handling.
- Single global primary/best-listing policy using home exchange, highest turnover, and automatically derived exchange activity priority.
- Monthly and validation-time exchange activity priority recomputation.
- Low-turnover exclusion after a 60 trading-day review window.
- Stale/missing-data exclusion after missing or invalid prices on 3 of the last 10 expected trading days.
- Delisting suspicion after 2 consecutive expected trading days without price, excluding weekends and holidays.
- Delisted instrument removal from active support after a 5-day buffer, with history retained.
- Benchmark instrument protection from automatic exclusion where needed for correctness checks.
- Symbol, name, and identifier change history.
- Stable provider/reference identifier storage when available.
- Suspected split or corporate-action anomaly flags for operator review, without requiring a full launch corporate-action engine.
- Synthetic `CRY` exchange support for future cryptocurrency admission.
- One chosen crypto listing per supported asset using highest sustained turnover, best historical data completeness, and fixed venue priority.
- Crypto exclusion when no candidate venue meets the trust bar.

### Market Data Loading and Storage

- Adjusted historical daily closing-price ingestion and storage.
- Official exchange-local unadjusted current-day opening-price ingestion and storage.
- Price currency storage for every price record.
- Initial historical fill for supported instruments.
- Ongoing daily current-day opening and yesterday historical close loads.
- Multiple complementary free/free-tier provider integrations.
- Provider admission based on implementation validation results.
- Global source-prioritization policy using provider/exchange reliability score, source historical availability ratio, exchange coverage quality, and fixed source order.
- Provider/exchange reliability score maintenance from validation and production outcomes.
- Candidate-value audit evidence, selected source, and selection reason retention.
- Halted, suspended, and late-open instruments marked pending or failed according to load rules, not assigned invented fallback prices.

### Signal Generation

- Backend generation of only `Dip` and `Skyrocket`.
- Reuse of the existing alert algorithm.
- Persistence of supporting statistics and reasoning context.
- Historical signal generation during initial fill.
- Daily signal generation when sufficient inputs are available.
- Explicit distinction between no signal and signal unavailable because of insufficient history.
- No backend evaluation of user-defined `Custom` alerts.
- Prospective-only production rollout for signal algorithm changes after historical validation.

### Publication and App Reads

- Exchange-level daily readiness.
- Independent publication per exchange.
- Terminal outcome requirement across eligible instruments before publication evaluation.
- Coverage computation against the eligible exchange/day denominator.
- `ready` only when coverage exceeds 99%.
- Current-day publication blocked until correctness validation succeeds.
- Correctness benchmark sample from the top 20 most active supported instruments by trailing 60 trading-day traded value.
- Benchmark mismatch threshold of 5%.
- App-facing readiness, current-day prices, recent historical prices, signals, and signal context.
- App installation bootstrap with latest 30 days of historical data.
- Yesterday historical record retrieval for normal daily app operation.
- App-visible data limited to supported instruments and published data.

### Operator, Admin, and Governance

- Compact operator view for exceptions, readiness, quality, timing, and degraded states.
- Separate today-opening and yesterday-historical load tables with matching columns.
- Load filtering by day.
- Exchange/day statuses: `not started`, `in progress`, `ready`, `partial/problematic`, `failed`, and `market closed`.
- Universe-change and exclusion dashboard with event-type, exchange, and instrument filters.
- Required universe-change event types and row fields from the product specification.
- Production exchange degradation and restoration rules based on repeated KPI misses or 3 consecutive healthy expected trading days.
- Manual job retry, cancel, and mark-failed actions with required reason.
- Short validation path for candidate exchanges.
- Launch validation for NYSE, Nasdaq, and Prague Stock Exchange.
- Historical adjusted-close reprocessing and dependent backend statistic correction through explicit action.
- Routine once-daily app correction sync for corrected historical records.
- Retention cutoff with 1-year minimum for signal needs and 3-year maximum supported retained window.
- Restricted admin/operator access, audited admin actions, mobile credential rotation, revocation, and rate limiting.

### Reliability, Operations, and Infrastructure

- Persistent PostgreSQL-backed jobs or queue records.
- Idempotency keys, locking, bounded retries, request timeouts, worker heartbeat, and lock expiry.
- API and worker health checks.
- PostgreSQL read models or materialized views for app and operator reads.
- Automated daily local PostgreSQL and configuration/file backups.
- Weekly manual off-machine backup copy tracking.
- Restore testing before launch and after meaningful schema changes.
- Structured logs, metrics, dashboards, and simple owner-focused alerts.
- VPS-first deployment with API process, worker process, PostgreSQL, reverse proxy, backups, and observability.
- Evolution path for worker concurrency, Redis, partitioning, automated off-machine backup, managed database, or service decomposition only when measured needs justify them.

## 4. Milestone Roadmap

### Milestone 1: Platform Skeleton and Domain Foundation

### Goal

Establish the deployable API/worker/PostgreSQL foundation and shared domain state needed by every later workflow.

### Included Scope

- Modular monolith codebase structure with separate API/web and worker/scheduler process roles.
- PostgreSQL schema foundation for exchanges, instrument types, instruments, listings, supported universe state, provider records, price records, load jobs, instrument load outcomes, exchange-day loads, publication records, read models, admin commands, and audit records.
- Job state model with required states and terminal-state semantics.
- Exchange calendar abstraction.
- Basic authentication boundary for private operator/admin surfaces and app-level identification for public reads.
- Health checks for API, worker heartbeat, database connectivity, scheduler heartbeat, and queue depth or pending job age.
- Initial structured logging and metrics plumbing.

### Dependencies

- Approved architecture and product specification.
- Existing alert algorithm interface known well enough to reserve statistics and signal storage boundaries.

### Key Risks

- Incorrect domain model constraints can force painful changes when ingestion, publication, or reprocessing are implemented.
- Weak job-state semantics can create duplicate loads or missed terminal outcomes.
- Calendar abstraction mistakes can cause false market-open or market-closed decisions later.

### Validation Goal

Prove that API and worker processes can share durable state, create and transition jobs idempotently, expose health, and represent exchange/day lifecycle states without performing real provider ingestion yet.

### Acceptance Criteria

- API and worker roles run independently against the same PostgreSQL database.
- Required job states exist and terminal states are enforced for publication-related records.
- Core entities support exchange/day, instrument/day, provider attempt, price, publication, signal, and universe-change relationships.
- Health checks report API, worker, database, scheduler, queue age/depth, and backup placeholder state.
- Structured logs include job lifecycle and admin-command events.

### Why This Comes Now

All data-loading, signal, publication, operator, retention, and reprocessing work depends on durable domain state and reliable job execution semantics.

### Milestone 2: Admin Scope, Calendar, and Universe Discovery Slice

### Goal

Create the first supported universe from admin-selected exchanges and instrument types, with enough lifecycle tracking to feed ingestion.

### Included Scope

- Admin configuration for supported exchanges and instrument types.
- Launch exchange configuration for NYSE, Nasdaq, and Prague Stock Exchange.
- Instrument discovery adapter boundary and initial discovery workflow.
- Supported universe state, candidate listing records, stable identifier fields where available, and universe-change records.
- Primary/best-listing selection using home exchange, turnover, and exchange activity priority.
- Exchange activity priority computation during validation/discovery and monthly recomputation path.
- Basic quality/exclusion state fields for low turnover, stale/missing data, delisting suspicion, benchmark protection, symbol/name/identifier changes, degradation, restoration, and historical-only status.
- Market-closed handling through exchange calendars.

### Dependencies

- Milestone 1 domain, job, calendar, and admin foundations.

### Key Risks

- Provider discovery quality may differ sharply by exchange, especially for Prague Stock Exchange.
- Multi-listed entities may be difficult to reconcile without strong identifiers.
- Turnover normalization across currencies can affect best-listing outcomes.

### Validation Goal

Prove that configured launch scope can produce an eligible supported universe and auditable universe-change history without exposing unsupported candidates to the app.

### Acceptance Criteria

- Admin can configure supported exchange and instrument-type scope.
- Worker can discover candidate instruments and produce a supported universe for each launch exchange.
- Primary/best-listing decisions are explainable through stored ranking inputs.
- Universe-change records are created for additions, exclusions, degradations, restorations, symbol/name/identifier changes, and removals when applicable.
- App-facing universe retrieval returns only supported instruments and support/signal-readiness state.

### Why This Comes Now

Ingestion and publication cannot be trusted until the system knows which instruments are eligible and why they are app-visible.

### Milestone 3: Provider Validation and Source Prioritization Foundation

### Goal

Establish the shared provider evidence, adapter, and scoring foundation needed for later live source testing and loader implementation.

### Included Scope

- Provider adapter contracts for discovery, metadata, symbology, validation, and later price-loading roles.
- Provider registry, source-role model, and source classification model.
- Provider attempt logging with latency, errors, auth needs, rate limits, stale/missing values, and raw normalized candidate metadata.
- Candidate-evidence storage and selected-value audit evidence foundations.
- Global source-prioritization policy model using provider/exchange reliability score, historical availability ratio, exchange coverage quality, and fixed source order.
- Provider/exchange reliability scoring inputs and update model.
- Environment-variable and Docker wiring for authenticated provider testing without hardcoded secrets.
- Calendar validation output and custom calendar adapter decision path if library calendars are missing or mismatched.

### Dependencies

- Milestone 1 job/domain foundation.
- Milestone 2 launch exchange scope, universe candidates, and calendar abstraction.

### Key Risks

- Provider contracts may be too narrow for later real-source testing if role boundaries are not defined early.
- Provider formats or availability may change during implementation.
- Source-prioritization evidence can become too shallow for later investigations if not retained early.

### Validation Goal

Prove that the system can record, explain, and rerun provider evidence consistently enough to support real source testing and multi-source loader implementation without locking the project to one provider strategy too early.

### Acceptance Criteria

- Provider attempts and candidate values are retained for investigation.
- Source-prioritization decisions are reproducible from stored evidence.
- Provider/exchange reliability scores can be computed from validation and production-style outcomes.
- Environment-variable and Docker wiring support keyed provider execution without hardcoded secrets.
- Provider/source role and classification data can support later live validation runs and combined loader decisions.

### Why This Comes Now

The project needs shared provider evidence, secret handling, and scoring structure before real source testing can happen safely and before higher-level workflows depend on any concrete loader behavior.

### Milestone 3.1: Real Instrument-Universe Source Validation and Combined Loader

### Goal

Test all listed sources with real live requests for instrument-universe loading and metadata discovery, then implement and integrate one combined universe loader that uses multiple sources to achieve the required overall quality.

### Included Scope

- Real live validation runs for every listed source: `yfinance`, `EODHD`, `FMP`, `Finnhub`, `Alpha Vantage`, `Stooq`, `Tiingo`, `Marketstack`, `Polygon`, official `NASDAQ`/Nasdaq Trader sources, official `NYSE` sources, official `PSE`/`PSE EDGE`, `Twelve Data`, `OpenFIGI`, `Nasdaq Data Link`, `FRED`, `DBnomics`, `IMF`, `World Bank`, and `AkShare`.
- Per-source evaluation of availability, auth requirements, quota/rate-limit behavior, speed, exchange coverage, symbol discovery quality, metadata quality, identifier quality, normalization usefulness, and specific usefulness for `NYSE`, `NASDAQ`, and `PSE`.
- Explicit source classification from evidence: `promote`, `fallback only`, `validation only`, `not for universe loader`, or `reject`.
- Role-based source assignment for the combined algorithm, such as primary discovery, metadata enrichment, symbology normalization, fallback discovery, and validation-only checks.
- One real combined instrument-universe loader implementation that replaces the current placeholder path in the project.
- Integration of the combined loader into the worker/project flow in its real production location, without waiting for later price-loading milestones.
- Docker-runnable development path for real source execution with environment-based secrets.
- Repo-tracked validation artifacts and rerun instructions covering per-source evidence and combined-loader outcomes.

### Dependencies

- Milestone 1 platform and job foundation.
- Milestone 2 supported-universe structure, candidate listing model, and calendar abstraction.
- Milestone 3 provider evidence, source-role, secret-wiring, and scoring foundation.

### Key Risks

- Several sources may be too weak on their own, especially for `PSE`, and the milestone can fail if the combined algorithm is judged too much like a single-source trust test.
- Free-tier quotas, auth friction, or format drift can slow real validation runs and Docker repeatability.
- Macro/enrichment sources may prove irrelevant to universe loading, but still consume validation effort because they must be tested and classified from real evidence.
- Combined-loader behavior can become hard to reason about if source roles and evidence are not kept explicit and auditable.

### Validation Goal

Prove that the system can achieve launch-quality instrument-universe loading and metadata discovery for `NYSE`, `NASDAQ`, and `PSE` through a complementary multi-source algorithm, without requiring any single source to be sufficient on its own.

### Acceptance Criteria

- Every listed source is tested through real live requests, downloads, or equivalent real provider interaction where technically applicable, and the evidence is retained in repo-tracked validation artifacts.
- Each tested source has an explicit classification, observed limits/availability notes, measured speed notes, exchange-coverage notes, and a reasoned role decision.
- Sources that do not materially help instrument-universe loading are still tested and explicitly classified as `not for universe loader`, `validation only`, or `reject` from evidence.
- The combined algorithm uses multiple sources where that improves overall universe and metadata quality rather than forcing one source to act as a universal trust anchor.
- The placeholder instrument-universe loader path is replaced by a real integrated implementation in the project.
- The combined universe loader runs in development against live sources and is runnable in Docker with environment-based secrets.
- The integrated loader produces auditable supported-universe and metadata outputs for configured launch exchanges and preserves evidence needed for investigation.

### Why This Comes Now

The current instrument-universe load path is missing. It must be validated and implemented before current-day or historical price-loading milestones build on top of it, and it needs real source evidence rather than paper assumptions.

### Milestone 4: Core Daily Opening Publication Slice

### Goal

Deliver the first working end-to-end current-day opening-price publication flow for launch exchanges.

### Included Scope

- Scheduled current-day opening-price load jobs per exchange/day.
- Provider fetch, normalization, candidate capture, source-prioritized selected value, and price record storage.
- Per-instrument load outcomes and exchange-day aggregate load state.
- Handling for missing, stale, halted, suspended, late-open, provider-failed, and market-closed cases.
- Bounded retries, request timeouts, idempotency keys, locks, worker heartbeat, and stale-running recovery.
- Coverage computation against eligible instruments.
- Correctness validation using fixed benchmark sample and 5% mismatch threshold.
- Publication decisions: ready, partial/problematic, failed, market closed, and not ready/in progress states.
- Read-model refresh after successful publication.
- Public app endpoints for readiness and current-day prices.
- Operator today-opening load table with required columns, quality results, degraded flag, exception count, and timing.

### Dependencies

- Milestone 1 platform and job foundation.
- Milestone 2 supported universe and calendars.
- Milestone 3 provider evidence, source prioritization, and benchmark basis.
- Milestone 3.1 real source testing, source-role classification, and integrated universe loader.

### Key Risks

- Publication can be blocked by delayed benchmark/reference data.
- Rate limits or slow providers can miss the 30-minute target.
- Partial failures can be incorrectly hidden if terminal outcomes and coverage denominator rules are wrong.

### Validation Goal

Prove the core product trust loop: the app sees an exchange as ready only after terminal outcomes, greater than 99% coverage, and successful correctness validation; otherwise the operator can see why publication is blocked.

### Acceptance Criteria

- Each launch exchange publishes independently.
- Current-day opening prices are not app-visible until the exchange/day is ready.
- Publication requires terminal outcomes for all eligible instruments, greater than 99% coverage, and successful correctness validation.
- Market-closed days do not run price computation and show the correct exchange/day state.
- Operator table shows exchange, status, publication readiness, start/finish time, eligible count, success count, failure count, coverage, quality result, degraded flag, and exception count.
- Repeated timeliness misses can mark an exchange internally degraded without exposing partial-quality data to the app.

### Why This Comes Now

This is the smallest meaningful working system state: it connects scope, providers, jobs, publication, app reads, and operator visibility.

### Milestone 5: Historical Close Loading and 30-Day App Bootstrap

### Goal

Add adjusted historical close ingestion and app historical reads while preserving the same trust and audit model.

### Included Scope

- Scheduled yesterday historical close loads.
- Adjusted close price storage with currency.
- Historical load outcomes and exchange-day historical load states.
- Provider candidate capture and source-prioritized selection for historical closes.
- App historical price retrieval for yesterday and latest 30 days.
- Operator yesterday-historical load table matching today-opening table columns.
- Retention-aware API validation for out-of-window history requests.
- Historical read models for recent instrument/exchange slices.

### Dependencies

- Milestone 4 daily ingestion/publication mechanics.
- Milestone 3 provider validation for historical completeness and timeliness.

### Key Risks

- Historical data completeness may vary by provider and exchange.
- Adjusted close semantics can differ across providers.
- Historical API performance can suffer without read models and indexes.

### Validation Goal

Prove that the app can perform daily historical retrieval and installation bootstrap from trusted adjusted-close data.

### Acceptance Criteria

- Yesterday historical loads run independently from current-day opening loads.
- Historical price records are adjusted closes and include currency.
- App can retrieve yesterday's record and latest 30 days within retention limits.
- Operator can inspect today-opening and yesterday-historical loads as separate tables with matching columns.
- Missing historical prices on expected trading days are treated as backend failures unless valid lifecycle rules apply.

### Why This Comes Now

Historical data is needed for app bootstrap and signal computation, but it is lower risk to add after the current-day publication model is proven.

### Milestone 6: Initial Historical Fill and Signal Baseline

### Goal

Create the historical baseline needed for production launch and generate backend signal history using the existing algorithm.

### Included Scope

- Initial historical fill jobs for supported launch instruments.
- Resumable, idempotent backfill behavior with daily production refresh priority over backfill.
- Supporting statistic persistence for the existing alert algorithm.
- Historical `Dip` and `Skyrocket` event generation.
- Signal unavailable state for instruments with insufficient history.
- Retrospective signal recomputation allowed in development and pre-launch validation.
- Performance measurement for backfill duration, signal computation duration, and read-model rebuild duration.

### Dependencies

- Milestone 5 historical close loading.
- Existing alert algorithm callable from the worker.
- Milestone 1 signal statistics and event model.

### Key Risks

- Signal computation may be expensive across the full launch universe.
- Provider rate limits may slow initial fill.
- Algorithm integration may reveal missing context or statistic persistence requirements.

### Validation Goal

Prove that supported instruments have enough retained adjusted-close history and computed statistics/events to serve production signal needs.

### Acceptance Criteria

- Initial fill loads at least the rolling 1-year history required for signals, within the system's retention policy.
- Historical prices, supporting statistics, and `Dip`/`Skyrocket` events are generated for eligible instruments.
- Newly admitted instruments can be price-visible while signal-unavailable until enough history exists.
- The system distinguishes no signal from insufficient-history signal unavailability.
- Backfill can pause, resume, and avoid blocking daily production refresh.

### Why This Comes Now

Signals require historical data and a stable algorithm integration, so they come after the historical load path is reliable.

### Milestone 7: Daily Signal Publication and App Signal Reads

### Goal

Add daily production signal generation and app-facing signal retrieval on top of published price data.

### Included Scope

- Daily `Dip` and `Skyrocket` generation after required current-day and historical inputs are available.
- Persistence of daily signal events, supporting statistics, and reasoning context.
- App signal retrieval for current and historical signal views.
- Read-model refresh for signal summaries and context.
- Signal-generation failure handling and operator-visible exceptions.
- Prospective-only production rollout path for signal algorithm changes after historical validation.

### Dependencies

- Milestone 4 current-day publication.
- Milestone 5 historical close loads.
- Milestone 6 signal baseline and algorithm integration.

### Key Risks

- Signal generation can accidentally run before data is complete.
- Algorithm changes can undermine historical stability if governance boundaries are weak.
- App semantics can be confused if no-signal and unavailable states are not clearly represented.

### Validation Goal

Prove that daily published market data produces only valid backend-owned `Dip` and `Skyrocket` events and exposes clear signal state to the app.

### Acceptance Criteria

- Signals are generated only when required price and historical inputs are available.
- `Custom` alerts are not evaluated by the backend.
- App endpoints return published signals and reasoning context.
- No-signal and signal-unavailable states are distinguishable.
- Signal algorithm changes require historical validation and apply prospectively after production rollout.

### Why This Comes Now

Daily signals are the main product value, but their correctness depends on the earlier trusted price and historical baseline milestones.

### Milestone 8: Full Operator, Recovery, and Degradation Controls

### Goal

Complete the operational surface needed for single-owner production operation.

### Included Scope

- Full operator dashboard for exceptions, readiness, quality, timing, provider failures, benchmark mismatches, KPI misses, degraded states, and unresolved incidents.
- Universe-change and exclusion dashboard with required filters and row fields.
- Manual job actions: retry, cancel, mark failed, each with required reason and audit trail.
- Degradation detection for quality misses, correctness blocks, repeated 30-minute publication target misses, provider/calendar incidents, backup failures, worker failures, and unresolved degraded states.
- Degradation clearing after 3 consecutive healthy expected trading days or audited operator override.
- Backup status visibility for latest local backup and latest recorded off-machine copy.
- Alerts for exchange/day failed, not ready beyond expected window, coverage below 99%, benchmark mismatches above 5%, repeated provider failures, worker not running, backup failure, database disk usage threshold, recurring KPI misses, and unresolved degraded states.

### Dependencies

- Milestones 4 through 7 operational events, metrics, and job state.
- Milestone 1 health and observability foundation.

### Key Risks

- Dashboard data can become too noisy for a single owner.
- Missing drill-down evidence can make provider or universe issues hard to diagnose.
- Manual actions can undermine auditability if reasons and state transitions are not enforced.

### Validation Goal

Prove that routine operation requires no manual review and exceptional failures are visible, actionable, and auditable.

### Acceptance Criteria

- Operator can filter load dashboards by day.
- Universe-change dashboard supports event type, exchange, and instrument filtering.
- Required universe-change event types are visible.
- Manual job actions require recorded reasons and are audit logged.
- Degraded exchange state is visible internally and never lowers app-facing trust behavior.
- Alerts and health checks cover worker, database, backups, publication, coverage, correctness, provider, and KPI failure modes.

### Why This Comes Now

The core product flows now exist, so this milestone turns them into an operable production system rather than a black-box batch pipeline.

### Milestone 9: Retention, Explicit Reprocessing, and Correction Sync

### Goal

Implement lifecycle controls for historical stability, storage limits, and exceptional data correction.

### Included Scope

- Retention cutoff function with 1-year minimum signal history and 3-year maximum supported retained window.
- Consistent retention across prices, signal events, and supporting statistics.
- Explicit historical adjusted-close reprocessing workflow.
- Dependent backend statistic correction.
- Routine once-daily app correction sync for corrected historical records.
- Audit trail for reprocessing requests, affected records, selected candidate values, reasons, and read-model rebuilds.
- Guardrails preventing current-day opening-price correction from being treated as normal reprocessing.
- Guardrails preventing post-launch signal algorithm changes from retrospectively rewriting previously delivered app alerts or signal events.

### Dependencies

- Milestones 5 through 7 historical price and signal storage.
- Milestone 8 operator/admin audit and visibility.

### Key Risks

- Reprocessing can undermine trust if it mutates published history without explicit audit evidence.
- Retention cutoff can orphan signals or statistics if applied inconsistently.
- Correction sync can confuse app clients if change markers are incomplete.

### Validation Goal

Prove that historical corrections are controlled, auditable, and app-synchronizable while preserving publication stability rules.

### Acceptance Criteria

- Retention cutoff applies consistently across prices, signals, and statistics.
- Historical adjusted-close reprocessing is explicit, audited, and scoped.
- App correction sync can identify corrected historical records once daily.
- Current-day opening-price publication errors are routed to quality-hardening investigation, not normal reprocessing.
- Post-launch signal algorithm changes do not rewrite previously delivered signal events.

### Why This Comes Now

Lifecycle and correction controls require mature historical, signal, read-model, admin, and audit foundations.

### Milestone 10: Launch Validation, Security Hardening, and VPS Operations

### Goal

Complete launch readiness for NYSE, Nasdaq, and Prague Stock Exchange on the VPS-first operating model.

### Included Scope

- End-to-end launch validation for NYSE, Nasdaq, and PSE against identical trust criteria.
- Production deployment on one VPS with API process, worker process, PostgreSQL, reverse proxy, backups, and observability.
- Admin/operator access restriction through authenticated sessions and private network path where practical.
- Mobile API credentials or signed tokens, credential rotation with overlap, revocation, and rate limiting.
- Input validation for exchange, instrument, date, history size, unsupported universe enumeration, and retention windows.
- Secret handling through environment variables or restricted VPS secret files.
- Automated daily local PostgreSQL and file/config backups.
- Weekly manual off-machine backup copy tracking.
- Restore test before launch.
- Performance validation for publication target, provider latency, signal computation, read-model rebuilds, API latency, and backup/restore operations.

### Dependencies

- Milestones 1 through 9.

### Key Risks

- PSE may fail validation and block launch.
- VPS resource constraints may affect provider loads, signal generation, database performance, or backups.
- Security controls may be too weak if public and private surfaces are not cleanly separated.

### Validation Goal

Prove the complete launch system can operate within cost, trust, security, and single-owner constraints.

### Acceptance Criteria

- NYSE, Nasdaq, and PSE all meet validation and publication trust bars.
- Current-day publication is typically available within the 30-minute target.
- App reads are rate-limited, authenticated/identified as designed, and restricted to supported published data.
- Admin/operator functions are restricted and audited.
- Restore has been tested successfully.
- Local backup and off-machine copy timestamps are visible.
- No launch-blocking operational, provider, calendar, security, or data-quality failures remain unresolved.

### Why This Comes Now

Launch readiness should validate the complete system after the functional and operational capabilities are implemented, not before the core risk-reducing slices exist.

### Milestone 11: Exchange Expansion Governance

### Goal

Enable controlled support for additional exchanges without weakening launch trust rules.

### Included Scope

- Candidate exchange validation workflow.
- Validation criteria for discovery quality, primary-listing selection behavior, daily load completeness/timeliness, historical load completeness/timeliness, correctness, and provider reliability.
- Exchange activity priority recomputation for newly added exchanges.
- Monthly review of candidate benchmark lists while preserving active benchmark stability unless invalid or delisted.
- Promotion path from validation to production support.
- Degraded-state behavior for repeatedly missed production quality bars.

### Dependencies

- Milestones 2, 3, 4, 5, 8, and 10.

### Key Risks

- New exchanges may require provider or calendar work that exceeds the low-cost operating model.
- Expansion can increase operator burden if automation and dashboards do not scale.
- Multi-listed selection can change when new exchanges enter the activity-priority order.

### Validation Goal

Prove that exchange expansion is governed by the same trust bar and does not require redesigning the launch system.

### Acceptance Criteria

- New exchanges cannot enter production until all validation criteria pass.
- Provider/exchange reliability and benchmark evidence are captured during validation.
- Expansion does not expose unsupported candidate instruments to the app.
- Operational burden remains visible through KPI exceptions and unresolved incident counts.

### Why This Comes Now

The launch exchanges must stabilize first; the expansion workflow then reuses the same validation and publication machinery for future scope.

### Milestone 12: Crypto Admission Under Synthetic CRY Exchange

### Goal

Implement the specified cryptocurrency support model when sources and venues can meet the same trust bar.

### Included Scope

- Synthetic `CRY` exchange support as a publication unit.
- Cryptocurrency instrument type handling distinct from crypto ETFs.
- Candidate venue discovery for supported cryptocurrencies.
- Exactly one chosen listing per crypto asset.
- Crypto venue-selection policy: highest sustained turnover, best historical data completeness, fixed venue priority.
- Crypto exclusion when no venue meets the trust bar.
- Daily and historical loading, readiness, publication, signals, operator visibility, retention, validation, and reprocessing behavior consistent with the full system trust model.

### Dependencies

- Milestones 1 through 11.
- Provider validation demonstrating crypto can meet the same trust bar.

### Key Risks

- Crypto venue and market behavior may not align cleanly with exchange-day calendar assumptions.
- Free data quality may fail the same correctness and completeness bar.
- Synthetic exchange semantics may require careful calendar and publication-window decisions.

### Validation Goal

Prove that crypto can be admitted only when it behaves like a trustworthy publication unit under the same system guarantees.

### Acceptance Criteria

- Crypto is grouped under `CRY`, not native venue exchanges.
- Each supported crypto asset has exactly one chosen listing.
- Crypto candidates failing the trust bar are excluded.
- App-facing behavior remains ready/not-ready and supported/published only.
- Operator visibility, validation evidence, and provider reliability scoring cover crypto behavior.

### Why This Comes Now

Product scope excludes crypto from launch and requires it to meet the same trust bar if introduced later. This milestone keeps the full specified capability planned without weakening launch focus.

## 5. Build Order Rationale

The roadmap starts with shared platform, data model, jobs, calendars, observability, and process separation because the architecture depends on a single codebase with clear API and worker roles. Without this foundation, later ingestion and publication work would be hard to make idempotent, auditable, and recoverable.

Universe management comes before ingestion because the system must know the eligible instrument denominator before it can judge load completeness or publication readiness. Provider foundation work follows immediately because free-source quality is the largest external risk and must be measurable before concrete loader behavior is locked in. Real source testing and the combined instrument-universe loader then come next, especially because Prague Stock Exchange can still block launch and the current universe-loading implementation gap must be closed before price/publication flows are built on top.

The first end-to-end product slice is current-day opening-price publication. It exercises the essential trust loop with the least historical and signal complexity: provider evidence, selected prices, terminal outcomes, coverage, correctness validation, publication state, app readiness/current-price reads, and operator load visibility.

Historical loading and initial fill come after current-day publication because they reuse the ingestion, provider, audit, and operator patterns while adding volume and adjusted-close semantics. Signal generation follows historical baseline creation because signals depend on sufficient historical inputs and the existing algorithm integration.

Operational controls, retention, and reprocessing are sequenced after the core flows because they depend on complete event, audit, publication, price, and signal state. Launch hardening comes after all functional and operational capabilities are present so validation can measure the true production system.

Exchange expansion and crypto admission come after launch validation because the product requires launch exchanges first and requires future scope to meet the same trust bar rather than bypass it.

## 6. Dependency Map

- Milestone 1 is the root dependency for all later work.
- Milestone 2 depends on Milestone 1 and feeds Milestones 3, 3.1, 4, 5, 8, 11, and 12.
- Milestone 3 depends on Milestones 1 and 2 and feeds Milestone 3.1 plus later ingestion, publication, validation, expansion, and crypto work.
- Milestone 3.1 depends on Milestones 1 through 3 and feeds Milestones 4, 8, 10, 11, and 12.
- Milestone 4 depends on Milestones 1, 2, 3, and 3.1 and creates the first app-visible publication slice.
- Milestone 5 depends on Milestones 3 and 4 and enables historical reads and signal inputs.
- Milestone 6 depends on Milestone 5 and the existing alert algorithm.
- Milestone 7 depends on Milestones 4, 5, and 6.
- Milestone 8 depends on operational events from Milestones 4 through 7 and observability foundations from Milestone 1.
- Milestone 9 depends on Milestones 5 through 8.
- Milestone 10 depends on Milestones 1 through 9 and gates production launch.
- Milestone 11 depends on the validated launch machinery from Milestones 2, 3, 3.1, and 4 through 10.
- Milestone 12 depends on the full launch and expansion foundations from Milestones 1, 2, 3, 3.1, and 4 through 11 plus crypto-specific provider validation.

## 7. Roadmap-Level Testing Strategy

### Milestone 1

- Unit tests for job state transitions, terminal-state semantics, idempotency-key generation, and domain constraints.
- Integration tests for API/worker/database connectivity and health checks.
- Migration tests for schema creation and rollback where supported.

### Milestone 2

- Unit tests for primary/best-listing ranking, exchange activity priority, lifecycle transitions, and exclusion/degradation state changes.
- Calendar tests for expected trading days, weekends, holidays, and market-closed states.
- Integration tests for admin configuration, discovery workflow, supported universe output, and universe-change audit records.

### Milestone 3

- Contract tests for provider adapters and normalized candidate records.
- Integration tests for provider attempt logging, candidate-evidence storage, source-role/classification persistence, reliability-score updates, secret wiring, and validation result generation.
- Fault-injection tests for provider timeouts, rate limits, stale data, missing data, conflicting values, and malformed responses.

### Milestone 3.1

- Real live validation runs against every listed source, including keyed and non-keyed execution paths where applicable.
- Integration tests for per-source classification, role assignment, combined-loader evidence retention, and supported-universe output generation.
- Docker execution tests for the integrated universe loader with environment-based secrets.
- Comparative test runs showing how the combined algorithm improves overall universe and metadata quality beyond any single-source-only strategy.
- Special validation attention for `PSE`, including proof that weak auxiliary sources are still classified accurately even when they are not promotable.

### Milestone 4

- End-to-end tests for current-day opening-price load through app readiness and current-price retrieval.
- Integration tests for retries, lock expiry, stale abandoned recovery, terminal outcomes, coverage denominator rules, correctness validation, benchmark mismatch threshold, and read-model refresh.
- Failure tests for blocked publication, market closed, partial/problematic, failed, and delayed provider scenarios.
- Performance testing begins here for provider latency, exchange/day load duration, read-model refresh duration, and API response latency.

### Milestone 5

- End-to-end tests for yesterday historical load and 30-day app bootstrap.
- Integration tests for adjusted-close storage, currency handling, retention-window validation, historical read models, and operator historical load table.
- Provider comparison tests for adjusted-close consistency.

### Milestone 6

- Algorithm integration tests for statistics and historical `Dip`/`Skyrocket` generation.
- Backfill resumability and idempotency tests.
- Performance tests for initial fill duration, batch writes, signal computation duration, and production-load priority over backfill.

### Milestone 7

- End-to-end tests for daily signal generation after price publication.
- Tests distinguishing no signal from signal unavailable.
- Regression tests for prospective-only algorithm rollout behavior.
- API tests for signal retrieval and published-only visibility.

### Milestone 8

- Dashboard integration tests for load filters, required columns, universe-change filters, event types, degraded states, and exception visibility.
- Audit tests for manual retry, cancel, and mark-failed actions.
- Alerting tests for exchange failure, readiness delay, coverage breach, benchmark mismatch, repeated provider failure, worker failure, backup failure, disk threshold, and recurring KPI misses.

### Milestone 9

- Retention tests verifying consistent cutoff across prices, signals, and supporting statistics.
- Reprocessing integration tests for explicit historical adjusted-close correction, dependent statistic correction, audit trail, and read-model rebuild.
- Correction sync tests for once-daily app pickup.
- Guardrail tests preventing normal reprocessing of current-day opening-price publication failures and post-launch retrospective signal rewrites.

### Milestone 10

- Full production rehearsal across NYSE, Nasdaq, and PSE.
- Security tests for admin/operator authorization, mobile credential rotation, revocation, rate limiting, and invalid input handling.
- Backup and restore tests.
- Load and performance tests for daily publication window, read spikes, database indexes, queue depth, worker throughput, and API latency.

### Milestones 11 and 12

- Validation-suite tests for candidate exchange and crypto admission.
- Regression tests ensuring new exchanges or `CRY` do not weaken supported-universe visibility, publication, correctness, retention, signal, or operator rules.

Integration testing becomes critical at Milestone 3 because provider behavior, calendars, source prioritization, and validation outcomes must work together. Real live source testing becomes critical at Milestone 3.1 because the combined universe loader must be proven against actual provider behavior, not only contracts. Full end-to-end testing becomes critical at Milestone 4 when publication gates app-visible data. Performance testing should begin at Milestone 3.1 for source-speed measurement and broaden at Milestones 4, 6, and 10.

## 8. Observability Rollout Plan

### Early Logs

From Milestone 1, structured logs must include:

- API start/stop and worker start/stop.
- Job creation, start, finish, failure, retry, cancellation, stale-abandoned recovery, and lock events.
- Admin commands and configuration changes.
- Health-check failures.

From Milestones 2 through 4, logs must add:

- Universe discovery outcomes and universe-change events.
- Calendar decisions for market-open and market-closed days.
- Provider attempts, provider failures, rate limits, stale/missing data, and latency.
- Candidate conflicts, source-prioritization decisions, selected source, and selection reason.
- Source classification outcomes, combined-loader role decisions, and real validation-run summaries.
- Publication decisions, coverage calculations, correctness-validation results, and publication blocks.

Later logs must add:

- Signal generation failures and algorithm rollout decisions.
- Reprocessing actions, affected records, and read-model rebuilds.
- Retention cutoff actions.
- Backup success/failure and restore test outcomes.
- Exchange validation and crypto admission outcomes.

### Early Metrics

From Milestone 1, track:

- API health, worker heartbeat, scheduler heartbeat, database connectivity, queue depth, pending job age, job state counts, and API error rate.

From Milestones 3 and 4, track:

- Exchange/day status, eligible instrument count, successful load count, failed load count, coverage percentage, load duration, provider success/error/timeout/rate-limit counts, benchmark mismatch percentage, correctness-validation blocked state, job retry counts, read-model refresh duration, and API latency for readiness/current-price endpoints.
- Per-source availability, observed quota/rate-limit events, validation-run duration, source classification counts, and combined-loader contribution patterns during Milestone 3.1.

From Milestones 5 through 7, add:

- Historical load duration, historical completeness, backfill progress, signal computation duration, signal unavailable count, signal generation failures, and signal API latency.

From Milestones 8 through 10, add:

- Degraded exchange count, recurring KPI misses, unresolved incident count, alert counts, backup timestamp age, off-machine copy timestamp age, disk usage, restore-test result, and operational exception recurrence.

### Later Additions

- Redis/cache metrics only if Redis is introduced.
- Table partition and database contention metrics if price/statistics growth requires deeper tuning.
- Per-worker concurrency metrics if worker concurrency is added.
- More detailed provider reliability trend dashboards as exchange count grows.

### Alerting Timing

Alerting becomes necessary no later than Milestone 8, before production launch hardening. Minimal alerts should cover exchange/day failed, exchange/day not ready beyond expected window, coverage below 99%, benchmark mismatches above 5%, repeated provider failures, worker not running, backup failure, database disk usage threshold, recurring KPI misses, and unresolved degraded states.

## 9. Risk Register

### Free Provider Quality Is Insufficient

- Affected milestone: Milestones 3, 3.1, 4, 5, 10, 11, 12.
- Impact: Launch blocked or publication windows missed.
- Mitigation approach: Validate providers early, combine complementary free sources, retain provider evidence, update provider/exchange reliability scores, and block launch rather than lowering trust bar.

### Prague Stock Exchange Fails Trust Bar

- Affected milestone: Milestones 3.1 and 10.
- Impact: Launch blocked because PSE is mandatory.
- Mitigation approach: Iterate on source discovery, provider combination, adapter behavior, and calendar validation until PSE passes the same criteria as NYSE and Nasdaq.

### Exchange Calendar Errors

- Affected milestone: Milestones 1, 2, 3, 4, 5, 10, 12.
- Impact: False failures, missed loads, incorrect delisting suspicion, or wrong publication state.
- Mitigation approach: Build calendar abstraction early, validate calendars during provider/exchange validation, add custom calendar adapters only when validation shows a library gap.

### Job State or Locking Bugs

- Affected milestone: Milestones 1, 4, 5, 6, 8, 9.
- Impact: Duplicate loads, missed terminal outcomes, stuck publication, or unsafe reprocessing.
- Mitigation approach: Enforce idempotency keys, locks, heartbeat, lock expiry, bounded retries, terminal-state rules, and state-transition tests.

### Source Prioritization Is Not Explainable

- Affected milestone: Milestones 3, 3.1, 4, 5, 8, 9.
- Impact: Operator cannot investigate conflicting or incorrect provider values.
- Mitigation approach: Persist candidate values, selected source, selection reason, provider attempts, reliability inputs, and provider/exchange score changes.

### Multi-Listed Instrument Resolution Is Ambiguous

- Affected milestone: Milestones 2, 3.1, 10, 11.
- Impact: Wrong supported listing, duplicate company exposure, or unstable universe.
- Mitigation approach: Store stable identifiers when available, record ranking evidence, normalize turnover, track symbol/name/identifier changes, and audit selection outcomes during validation.

### Signal Computation Is Too Slow

- Affected milestone: Milestones 6, 7, 10.
- Impact: Initial fill or daily publication may miss targets.
- Mitigation approach: Measure computation duration, batch work, prioritize daily production refresh over backfill, optimize indexes and read models, and add worker concurrency only when measured.

### Historical Reprocessing Undermines Stability

- Affected milestone: Milestone 9.
- Impact: Published history or delivered signals become untrustworthy.
- Mitigation approach: Require explicit admin action, audit affected records, limit post-launch algorithm changes to prospective behavior, and route current-day opening-price errors to quality hardening.

### Operator Dashboard Is Too Shallow

- Affected milestone: Milestone 8.
- Impact: Single owner cannot diagnose exceptional failures quickly.
- Mitigation approach: Build dashboards from real job/provider/publication evidence, include exception counts and drill-down fields, and track KPI exception volume and recurrence.

### VPS Resource Constraints

- Affected milestone: Milestones 4, 6, 8, 10.
- Impact: Missed publication windows, slow API reads, failed backups, or database pressure.
- Mitigation approach: Use read models, indexes, measured concurrency, batch writes, backfill throttling, local backups, performance tests, and redesign triggers for Redis, partitioning, or managed database only when needed.

### Security Boundary Weakness

- Affected milestone: Milestones 1, 8, 10.
- Impact: Unauthorized admin actions, abuse of app APIs, or leaked secrets.
- Mitigation approach: Restrict admin/operator access, audit admin commands, rate-limit app endpoints, rotate/revoke mobile credentials, validate inputs, and store secrets outside source control.

### Crypto Does Not Fit Daily Exchange Model

- Affected milestone: Milestone 12.
- Impact: Crypto admission could weaken trust semantics.
- Mitigation approach: Require same trust bar, represent crypto through `CRY`, choose one listing per asset, exclude assets without acceptable venues, and validate calendar/publication-window behavior before production admission.

## 10. Readiness Gates

### Gate to Milestone 2

- API and worker roles run against PostgreSQL.
- Core domain schema and job state model exist.
- Health checks and structured job/admin logs exist.

### Gate to Milestone 3

- Admin scope configuration works.
- Launch exchanges and instrument types can be represented.
- Discovery can produce candidate and supported universe records.
- Universe-change records are auditable.
- Calendar abstraction can identify expected trading and closed days.

### Gate to Milestone 3.1

- Provider adapters can produce normalized candidates.
- Provider attempts and candidate evidence are stored.
- Source-prioritization decisions are reproducible.
- Docker and environment-variable wiring can run keyed providers without hardcoded secrets.

### Gate to Milestone 4

- All listed sources have been tested and classified from real evidence.
- The combined instrument-universe loader is integrated into the project and replaces the placeholder path.
- Development and Docker execution paths can run the live universe loader with environment-based secrets.
- Launch exchanges have an auditable multi-source universe-loading strategy strong enough to proceed into daily price-publication work.

### Gate to Milestone 5

- Current-day opening-price publication works end to end.
- App readiness and current-price endpoints serve only ready exchange/day data.
- Operator today-opening table exposes required state and quality evidence.
- Job retry, idempotency, timeout, and stale recovery paths are validated.

### Gate to Milestone 6

- Adjusted historical close loads work.
- App can retrieve yesterday and 30-day history.
- Operator yesterday-historical load table works.
- Historical read models and retention-window validation are in place.

### Gate to Milestone 7

- Initial historical fill is resumable and idempotent.
- Required signal history and statistics exist.
- Historical `Dip` and `Skyrocket` events are generated in pre-launch context.
- Signal performance is measured.

### Gate to Milestone 8

- Daily signal generation works on published data.
- App signal reads distinguish signal, no signal, and unavailable states.
- Signal failures are logged and operator-visible.
- Algorithm-change governance is defined in system behavior.

### Gate to Milestone 9

- Operator dashboards expose load status, quality, exceptions, universe changes, degraded states, and manual job actions.
- Alerts and health checks cover critical production failure modes.
- Manual actions are audited with required reasons.

### Gate to Milestone 10

- Retention cutoff works consistently.
- Historical adjusted-close reprocessing is explicit and audited.
- Correction sync behavior is validated.
- Guardrails prevent unsafe current-day and retrospective signal rewrites.

### Gate to Milestone 11

- NYSE, Nasdaq, and PSE pass launch validation.
- VPS deployment, security, backups, restore test, observability, and performance targets are production-ready.
- No launch-blocking provider, calendar, security, or operational issues remain.

### Gate to Milestone 12

- Exchange expansion workflow is validated.
- Provider and calendar validation can assess new publication units without redesign.
- Operator burden remains acceptable under expanded scope.

## 11. Next Step Recommendation

The Task Decomposer Agent should decompose Milestone 1: Platform Skeleton and Domain Foundation next.

This milestone is the dependency root for the entire roadmap. It should be decomposed before feature milestones because the API/worker split, PostgreSQL schema foundation, job state semantics, idempotency model, health checks, and initial observability determine how every later ingestion, publication, signal, operator, retention, and reprocessing capability will be built.
