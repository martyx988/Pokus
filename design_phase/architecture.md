# Architecture

## 1. Input Summary

The architecture is based on three existing design inputs:

- `business_analysis.md`: establishes the business goal of a trustworthy daily market-data and signal backend for a mobile app, optimized for data quality, historical consistency, low operating cost, and single-owner maintainability.
- `product_spec.md`: defines the authoritative system behavior, including exchange and universe management, daily opening and historical closing price ingestion, `Dip` and `Skyrocket` signal generation, exchange-level publication readiness, operator visibility, retention, validation, and exceptional reprocessing.
- `research_analysis.md`: compares implementation approaches and identifies the strongest fit as a modular application, scheduled staged ingestion, relational primary storage, lightweight background processing, resource-oriented APIs, logs plus metrics, and VPS-first infrastructure.

Key product constraints shaping the architecture:

- Daily granularity only; no intraday monitoring.
- Initial production scope is NYSE, Nasdaq, and Prague Stock Exchange.
- Initial instrument types are stocks, ETFs, and ETNs; crypto is deferred until it can meet the same trust bar.
- External market-data acquisition cost should be near zero.
- Ongoing operating cost should be limited essentially to VPS hosting.
- The system must be sustainable for one owner.
- Exchange/day publication requires terminal outcomes for eligible instruments and greater than 99% coverage.
- Published history is stable by default and changes only through explicit reprocessing.

No blocking conflicts were found between the inputs.

## 2. Architecture Options

### Option 1: Single-Process Modular Monolith

#### Summary

A single backend application contains the mobile API, operator views, scheduled ingestion jobs, signal generation, publication logic, and admin functions. It runs as one deployed process on a VPS and uses a relational database as the source of truth.

#### Major Components

- Mobile API module
- Operator/admin module
- Universe management module
- Data-source adapters
- Scheduled ingestion module
- Signal generation module
- Publication/readiness module
- Relational database
- Structured logging and basic metrics

#### Data Flow

1. Scheduled jobs discover instruments and ingest daily market data.
2. Data-source adapters fetch candidate values from free providers.
3. The ingestion module resolves candidate values through the global source-prioritization policy.
4. Prices, load outcomes, statistics, and signal events are persisted.
5. Publication logic marks exchange/day readiness after terminal outcomes and coverage checks.
6. Mobile API reads published data and signals from the database.
7. Operator views read load states, exceptions, and universe-change history.

#### Technology Choices

- Backend: a mature web framework in one runtime.
- Database: PostgreSQL.
- Jobs: in-process scheduler.
- Cache: none initially.
- Deployment: single VPS process plus PostgreSQL.
- Observability: structured logs plus basic metric counters.

#### Strengths

- Lowest operational complexity.
- Lowest cost.
- Fastest to build.
- Very easy to reason about in early production.
- Good fit for a narrow launch scope.

#### Weaknesses

- Background jobs can compete with API traffic in the same process.
- Retry and recovery semantics must be built carefully.
- Long-running initial fill or reprocessing jobs can affect responsiveness.
- Scaling requires splitting the process later.

#### Cost / Complexity Profile

Lowest cost and lowest complexity. The tradeoff is weaker isolation between app-facing reads and background work.

#### Best Fit

Best for a very small launch where operating simplicity matters more than isolation.

#### Risks

- In-process scheduled jobs may become brittle as staged loads, retries, validation, and reprocessing accumulate.
- One process failure can interrupt both API reads and background processing.
- Operator visibility may need custom work to compensate for the absence of a real job system.

### Option 2: Modular Monolith with Separate API and Worker Processes

#### Summary

One codebase and one domain model are deployed as two process types: an API/web process and a worker/scheduler process. Both use the same PostgreSQL database. The worker owns scheduled ingestion, backfills, retries, validation, signal generation, and publication workflows. The API process serves the mobile app and private operator/admin views.

#### Major Components

- API/web process
- Worker/scheduler process
- Shared domain modules
- PostgreSQL primary database
- Lightweight job queue or database-backed job table
- Market-data provider adapters
- Exchange-calendar service/module
- Signal algorithm adapter
- Publication/read-model builder
- Operator/admin views
- Structured logs and metrics dashboard

#### Data Flow

1. Admin configuration defines supported exchanges and instrument types.
2. Worker schedules universe discovery, daily opening-price loads, yesterday close-price loads, initial fills, validation jobs, retries, and reprocessing jobs.
3. Provider adapters fetch market data from multiple free sources.
4. Ingestion normalizes values and applies source prioritization.
5. Load outcomes are written per instrument and exchange/day.
6. The signal module computes statistics and `Dip`/`Skyrocket` events when data and history are sufficient.
7. Publication logic computes coverage and quality, then marks each exchange/day as ready, partial/problematic, failed, or market closed.
8. Published read models are updated for readiness, current-day prices, recent history, signals, and operator dashboards.
9. The API process serves only supported, published, app-visible data.

#### Technology Choices

- Backend: modular web application.
- Database: PostgreSQL.
- Jobs: PostgreSQL-backed persistent job records/queue at launch.
- Cache: database-backed precomputed read views initially; optional Redis later.
- Deployment: one VPS running API, worker, PostgreSQL, reverse proxy, backups, and observability.
- Observability: structured logs, metrics, health checks, and private dashboards.

#### Strengths

- Strong fit for staged daily ingestion and publication.
- Keeps one codebase while isolating API responsiveness from background workloads.
- Supports initial fill and exceptional reprocessing without blocking mobile reads.
- Preserves single-owner maintainability.
- Allows incremental scaling by adding worker concurrency or moving components later.

#### Weaknesses

- More operational setup than a single-process monolith.
- Requires explicit job idempotency, locking, retries, and state transitions.
- Needs discipline to preserve module boundaries.

#### Cost / Complexity Profile

Low to moderate cost and moderate complexity. It remains VPS-friendly while providing enough operational structure for production-grade daily jobs.

#### Best Fit

Best for this product's current stage: production-grade behavior, daily batch workflows, strong data-quality rules, and one-owner operation under a tight budget.

#### Risks

- Poorly designed job state can cause duplicate loads or missed terminal outcomes.
- Database-backed queues can become a bottleneck if the system grows substantially.
- Internal module boundaries can erode without clear ownership.

### Option 3: Distributed Services with Dedicated Data Pipeline

#### Summary

Separate services handle mobile APIs, universe management, ingestion, signal generation, publication, operator reporting, and data-source integration. Services communicate through queues or messages and may use specialized storage for time-series data.

#### Major Components

- Mobile API service
- Admin/operator service
- Universe service
- Ingestion service
- Signal service
- Publication service
- Reporting/read-model service
- Message broker
- PostgreSQL plus optional time-series store
- Dedicated observability stack

#### Data Flow

1. Universe service publishes supported instrument changes.
2. Ingestion service consumes scheduled work and provider data.
3. Signal service consumes completed price records.
4. Publication service consumes load and signal outcomes.
5. Reporting service maintains read models for app and operator views.
6. API service serves published data from read models.

#### Technology Choices

- Backend: multiple deployable services.
- Database: PostgreSQL plus optional time-series database.
- Queue/broker: RabbitMQ, Kafka, or equivalent.
- Cache: Redis or dedicated read store.
- Deployment: containerized multi-service environment.
- Observability: logs, metrics, tracing, alerts.

#### Strengths

- Highest scale ceiling.
- Strongest independent component isolation.
- More room for specialized storage and processing.
- Easier to assign separate teams in the future.

#### Weaknesses

- Overly complex for a single-owner daily system.
- Higher cost and maintenance burden.
- More failure modes and distributed debugging.
- Slower to build.
- Harder to keep product behavior consistent across services.

#### Cost / Complexity Profile

Highest cost and highest complexity. Operationally misaligned with the near-zero external-cost constraint.

#### Best Fit

Best only if the product later reaches large scale, has multiple maintainers, and needs independent service ownership or very high ingestion/read volume.

#### Risks

- Premature distributed complexity can delay launch and reduce reliability.
- Message ordering, retries, schema coordination, and observability become major responsibilities.
- Infrastructure cost can drift away from the business constraint.

## 3. Recommended Architecture

### Recommended Option

Option 2: Modular Monolith with Separate API and Worker Processes.

### Why This Option

This option is the best match for the product's reliability expectations, daily workload shape, and cost constraints. It keeps the system buildable and maintainable by one owner while giving background processing enough structure to handle initial fills, daily loads, retries, validation, publication, and explicit reprocessing.

Business goals favor trust, completeness, and operational sustainability over broad coverage or theoretical scale. A shared codebase avoids the coordination overhead of microservices, while separate process types keep heavy background jobs from interfering with app-facing reads.

Product requirements strongly favor explicit job state and publication state:

- Exchange/day readiness depends on all eligible instruments reaching terminal outcomes.
- Publication requires greater than 99% coverage.
- Initial fill must generate prices, statistics, and historical signals.
- Historical recomputation must be explicit.
- Operator views need load status, timing, quality, exceptions, and universe-change history.

Those requirements are easier to satisfy with a worker process and job records than with a purely in-process scheduler.

Reliability expectations are production-grade but daily, not intraday. The system needs good recovery, retries, and visibility, but it does not need streaming infrastructure.

Cost sensitivity points toward a VPS-first deployment with PostgreSQL and lightweight supporting services rather than a cloud-first managed architecture.

Implementation speed remains good because the design uses mature, boring components and avoids distributed service boundaries.

### Why Not the Others

Option 1 is simpler, but it underfits the operational complexity of staged ingestion, validation, retries, initial fill, and exceptional reprocessing. It can work for a prototype, but it creates avoidable risk for a production-grade daily data service.

Option 3 offers more scale, but it overfits future possibilities and underfits current constraints. The system is daily, the owner is one person, the budget is tight, and the domain needs consistency more than independent service scaling.

### Assumptions Behind the Recommendation

- The existing signal algorithm can run efficiently inside the worker process.
- PostgreSQL can comfortably store up to three years of daily prices, statistics, signals, load records, and audit history for the expected initial and medium-term universe.
- The app's read traffic is modest to moderate, with spikes around daily refresh windows.
- Operator dashboards are private/internal and do not require public multi-tenant access.
- Initial hosting is a single VPS.
- External market-data sources are free or free-tier and may be rate-limited or unreliable.
- Crypto is deferred until source quality and venue selection can meet the same trust bar as exchange-traded instruments.

## 4. System Overview

The system is a VPS-hosted backend application with two runtime roles:

- API/web role: serves mobile app endpoints and private operator/admin views.
- Worker role: runs scheduled jobs, ingestion, retries, signal computation, publication checks, validation, and reprocessing.

Both roles share the same codebase, domain modules, and PostgreSQL database. PostgreSQL is the source of truth for domain data, historical data, job state, publication state, and audit records.

The worker turns external market-data inputs into trusted, published daily outputs. The API exposes only supported, published, app-visible data to the mobile app. The operator view exposes compact internal visibility into readiness, exceptions, quality, and universe changes.

## 5. Component Breakdown

### API/Web Process

Purpose: Serve mobile app data and private operator/admin interfaces.

Responsibilities:

- Expose supported universe, readiness, current-day prices, recent history, and signals.
- Expose private operator dashboards.
- Expose restricted admin actions for supported exchange/type configuration, validation, and explicit reprocessing.
- Enforce authentication and authorization for admin/operator functions.
- Read published data and read models.

What it should not do:

- Run long ingestion or backfill work.
- Directly fetch external market data during app requests.
- Compute publication readiness inline during mobile reads.

Interactions:

- Reads PostgreSQL.
- Writes admin commands and reprocessing requests.
- May enqueue jobs through the job table/queue.

### Worker/Scheduler Process

Purpose: Own all scheduled and asynchronous backend work.

Responsibilities:

- Schedule daily opening-price loads.
- Schedule yesterday historical close loads.
- Run initial historical fills.
- Run universe discovery and maintenance.
- Run validation for candidate exchanges.
- Run retries and quality checks.
- Run signal generation.
- Run publication readiness checks.
- Run explicit reprocessing jobs.
- Record job state, failures, timings, and exceptions.

What it should not do:

- Serve mobile app traffic.
- Bypass publication rules.
- Mutate historical published records except through explicit reprocessing flows.

Interactions:

- Reads and writes PostgreSQL.
- Calls external market-data providers through adapters.
- Uses exchange calendars.
- Updates read models after publication.

### Universe Management Module

Purpose: Maintain the supported instrument universe for configured exchanges and instrument types.

Responsibilities:

- Discover candidate instruments.
- Apply primary/best-listing policy, including an automatically derived exchange activity priority for tie-breaking after home exchange and listing-level turnover.
- Apply exclusion and quality rules, including the confirmed launch thresholds: low-turnover exclusion after a 60 trading-day review window below the launch traded-value threshold, stale/missing-data exclusion after missing or invalid prices on 3 of the last 10 expected trading days, and protected benchmark exceptions when needed for correctness checks.
- Track additions, removals, exclusions, delisting suspicion, degradation, and restoration.
- Keep removed instruments historically visible but inactive.
- Support the synthetic `CRY` exchange when crypto is later admitted.

What it should not do:

- Publish daily price data.
- Decide source-prioritized price values.
- Generate signals.

Interactions:

- Reads admin exchange/type configuration.
- Writes instruments, support states, and universe-change records.
- Provides eligible-instrument sets to ingestion and publication.

### Market Data Provider Adapter Layer

Purpose: Isolate external free-source integrations from domain logic.

Responsibilities:

- Fetch historical closing prices.
- Fetch current-day opening prices.
- Fetch or derive discovery inputs where providers support them.
- Normalize provider responses into internal candidate records.
- Record provider errors, rate limits, and data gaps.

What it should not do:

- Decide final published values.
- Know app-facing response shapes.
- Directly update publication state.

Interactions:

- Called by ingestion jobs.
- Returns normalized candidate data to ingestion.
- Writes provider attempt metadata for investigation.

### Ingestion Module

Purpose: Convert provider candidates into internal price records and load outcomes.

Responsibilities:

- Load daily opening prices and historical closing prices.
- Apply global source-prioritization policy.
- Record per-instrument success or failure.
- Track missing data, stale values, provider disagreement, and quality findings.
- Ensure idempotent writes for each instrument/day/load type.

What it should not do:

- Mark an exchange/day ready before publication checks.
- Hide backend failures as acceptable missing data.
- Generate user-specific alert state.

Interactions:

- Consumes eligible instruments from universe management.
- Calls provider adapters.
- Writes prices, load attempts, and load outcomes.

### Signal Generation Module

Purpose: Compute backend-owned `Dip` and `Skyrocket` events using the existing algorithm.

Responsibilities:

- Run the existing alert algorithm for eligible instruments.
- Persist supporting statistics and reasoning context.
- Generate historical events during initial fill.
- Generate daily events when sufficient data exists.
- Distinguish no signal from signal unavailable due to insufficient history.

What it should not do:

- Evaluate app-local `Custom` alerts.
- Modify the business logic of the existing algorithm without validation.
- Generate signals when required inputs are missing.

Interactions:

- Reads price history and current-day opening records.
- Writes signal statistics and signal events.
- Supplies publication and API read models.

### Publication Module

Purpose: Decide when exchange/day data becomes trusted for app consumption.

Responsibilities:

- Track exchange/day lifecycle states.
- Determine whether all eligible instruments have terminal load outcomes.
- Compute coverage.
- Exclude accepted delisting-suspected instruments from the denominator when allowed.
- Apply the greater than 99% coverage threshold.
- Track market-closed days.
- Mark ready, partial/problematic, failed, or market closed.
- Preserve published history unless explicit reprocessing occurs.

What it should not do:

- Fetch external data.
- Change universe scope.
- Bypass quality thresholds for convenience.

Interactions:

- Reads load outcomes, exchange calendars, quality checks, and universe state.
- Writes exchange-day publication records and read-model refresh markers.

### Read Model Builder

Purpose: Precompute common app and operator reads after publication and job completion.

Responsibilities:

- Prepare readiness summaries.
- Prepare current-day exchange price outputs.
- Prepare yesterday and 30-day historical read slices.
- Prepare signal read outputs with context.
- Prepare operator load tables and universe-change views.

What it should not do:

- Become the source of truth for domain state.
- Apply different business rules than the core modules.

Interactions:

- Reads normalized source tables.
- Writes database-backed read tables or materialized views.
- May be rebuilt after reprocessing.

### Operator/Admin Module

Purpose: Provide compact internal control and investigation surfaces.

Responsibilities:

- Show separate today-opening and yesterday-historical load tables.
- Show readiness, coverage, timing, quality, degraded state, notes, and exception counts.
- Show universe changes and exclusions.
- Support filters by day, event type, exchange, and instrument.
- Allow restricted admin configuration and explicit reprocessing actions.
- Support new-exchange validation workflows.

What it should not do:

- Expose internal operational details to the mobile app.
- Require routine manual approval for normal instrument changes.

Interactions:

- Reads operational tables and read models.
- Writes admin configuration and commands.
- Enqueues validation or reprocessing jobs.

### PostgreSQL Database

Purpose: Store all authoritative system state.

Responsibilities:

- Store exchanges, instruments, support states, and configuration.
- Store daily prices, statistics, and signal events.
- Store load attempts, load outcomes, quality checks, and publication records.
- Store job state and retry metadata.
- Store universe-change history.
- Store precomputed read models or materialized views.

What it should not do:

- Contain unbounded history beyond retention policy.
- Hide domain behavior inside opaque stored procedures unless there is a clear operational reason.

Interactions:

- Used by API and worker processes.
- Backed up regularly.
- Tuned with indexes, constraints, and retention jobs.

## 6. Textual System Diagram

```text
Mobile App
   |
   v
API/Web Process
   |
   +--> Published Read Models
   |
   v
PostgreSQL Source of Truth
   ^
   |
Worker/Scheduler Process
   |
   +--> Universe Management
   +--> Market Data Provider Adapters
   +--> Ingestion
   +--> Signal Generation
   +--> Publication
   +--> Read Model Builder
   |
   v
External Free/Freemium Market Data Sources

Operator/Admin Browser
   |
   v
Private Operator/Admin Views
   |
   +--> Operational Tables
   +--> Universe Change History
   +--> Reprocessing / Validation Commands
```

## 7. Data Flows

### User Request Flow

1. The mobile app requests exchange readiness.
2. API validates the requested exchange scope.
3. API reads publication/readiness state from the published read model.
4. If an exchange is ready, the app requests current-day prices and signals.
5. API returns only published data for supported instruments.
6. If an exchange is not ready, the API returns a state that tells the app not to refresh that exchange's current-day data.
7. For install/bootstrap, the app requests recent history and receives the latest 30 days available within retention.

### Data Ingestion Flow

1. Worker determines expected exchange/day work using exchange calendars.
2. Worker identifies eligible instruments from the supported universe.
3. Worker creates or resumes load jobs for each exchange/day/load type.
4. Provider adapters fetch candidate data from multiple free sources.
5. Ingestion normalizes candidate values.
6. Ingestion applies the source-prioritization policy.
7. Ingestion writes final price records and load outcomes.
8. Ingestion records provider errors, missing values, stale data, and quality findings.

### Initial Historical Fill Flow

1. Admin triggers or schedules initial fill for configured exchanges and instrument types.
2. Universe discovery establishes the first supported universe.
3. Worker loads historical closes for each eligible instrument.
4. Ingestion applies source prioritization and writes historical prices.
5. Signal module computes historical statistics and events.
6. Read models are built for app bootstrap and operator validation.
7. Production admission occurs after quality and completeness are acceptable.

### Daily Opening-Price Flow

1. Worker starts after the configured daily market event window.
2. Eligible current-day instruments are loaded per exchange.
3. Current-day opening prices are stored.
4. Signal generation runs for instruments with sufficient historical context.
5. Publication checks terminal outcomes and coverage.
6. The exchange/day is published independently if ready.

### Daily Historical Close Flow

1. Worker loads yesterday's historical close after the relevant data is expected to be available.
2. Historical price records are inserted or updated idempotently.
3. Supporting statistics are updated.
4. Historical read models are refreshed.
5. Operator dashboard shows the historical load separately from today's opening-price load.

### Background Jobs

Core job types:

- Universe discovery refresh.
- Initial historical fill.
- Daily opening-price load.
- Daily historical close load.
- Signal computation.
- Publication evaluation.
- Read-model rebuild.
- Provider retry.
- Exchange validation.
- Exceptional reprocessing.
- Retention cutoff.
- Backup/maintenance checks.

### Failure and Degraded Flows

- Provider failure: record failed attempt, try alternate source where possible, and mark final instrument outcome only after retries are exhausted.
- Missing price: treat as backend failure unless market closed or accepted delisting-suspicion rules apply.
- Delisting suspicion: after two consecutive expected trading days without a price, excluding weekends and exchange holidays, mark the instrument as suspected and allow denominator exclusion when appropriate.
- Low coverage: mark exchange/day partial/problematic or failed rather than ready.
- Market closed: mark exchange/day market closed and skip price computation.
- Reprocessing: create an explicit reprocessing job, recompute affected records, rebuild read models, and retain audit evidence.

## 8. Technology Stack

### Backend Framework / Runtime

Recommendation: a mature modular web framework suitable for one codebase with separate API and worker roles. Good candidates are Django/Python, FastAPI/Python with a disciplined service layer, or Spring Boot/Kotlin/Java if the owner prefers the JVM.

Confirmed initial choice: Django with Django REST Framework.

Why it fits:

- Strong admin and operator-view ergonomics.
- Mature ORM and migration tooling.
- Good fit for CRUD-heavy domain state and internal dashboards.
- Works well on a VPS.
- Python is practical for data ingestion and market-data library integration.

Alternatives considered:

- FastAPI: excellent for APIs, but admin/operator surfaces and database workflow require more assembly.
- Spring Boot: mature and robust, but heavier for a single-owner Python-friendly data workflow.
- Node/NestJS: workable, but less natural for data-processing libraries.

Tradeoffs accepted:

- Django is not the thinnest API framework, but the built-in admin and mature ecosystem reduce total ownership cost.

### Database

Recommendation: PostgreSQL inside the Docker Compose/VPS deployment.

Why it fits:

- Strong relational integrity for exchanges, instruments, publications, and audit history.
- Handles daily historical records well at expected scale.
- Supports indexing, partitioning if needed, materialized views, and transactional publication updates.
- Easy to run on a VPS.
- Managed PostgreSQL is out of scope for launch and future planning under the current product constraints.

Alternatives considered:

- SQLite: too limited for concurrent worker/API production use.
- Dedicated time-series database: unnecessary early and adds operational burden.
- Document database: weaker fit for explicit relationships, consistency, and auditability.

Tradeoffs accepted:

- PostgreSQL requires schema discipline and query tuning as history grows.

### Cache / Read Optimization

Recommendation: database-backed read models and materialized views initially; no dedicated cache at launch.

Why it fits:

- App access patterns are predictable.
- Publication events create clear refresh points.
- Avoids cache invalidation complexity.
- Keeps infrastructure simple.

Alternatives considered:

- Direct reads only: simplest, but may become inefficient for repeated 30-day and current-day reads.
- Redis cache: useful later if mobile read traffic grows.

Tradeoffs accepted:

- Read-model freshness must be managed explicitly after publication and reprocessing.

### Background Jobs / Queue

Recommendation: Django-Q2 with the PostgreSQL ORM broker at launch, using explicit job state, retries, idempotency keys, and operator-visible outcomes. Do not introduce Redis at launch.

Why it fits:

- Supports staged ingestion, retries, explicit job status, and worker isolation.
- Avoids distributed messaging complexity.
- Lets the operator see job outcomes.

Alternatives considered:

- In-process scheduler only: too brittle for production-grade staged workflows.
- Kafka/RabbitMQ-style messaging: likely too much operational weight early.

Tradeoffs accepted:

- Job idempotency and locking must be designed carefully.

### External Integrations

Recommendation: provider adapter interface over an exchange-agnostic pool of free or free-tier market-data sources, plus exchange-calendar data.

Why it fits:

- Product requires source diversity.
- Adapters isolate provider quirks and allow replacement.
- Source-prioritization stays centralized.
- Providers should be selected for reusable coverage across current and future exchanges, not as one-off integrations for NYSE, Nasdaq, or Prague Stock Exchange.
- `yfinance` must be included in the candidate source pool.
- FinceptTerminal should be used as inspiration for candidate connector discovery, especially its stated use of broad data connectors such as Yahoo Finance, Polygon, FRED, IMF, World Bank, DBnomics, AkShare, government APIs, and related market-data/broker integrations.
- Initial provider validation matrix should include: `yfinance`, Stooq/pandas-datareader, Nasdaq Data Link/free datasets, Alpha Vantage, Twelve Data, Financial Modeling Prep, Finnhub, Tiingo, Polygon free tier, EODHD/free tier, Marketstack/free tier, OpenFIGI for identifiers, DBnomics, FRED, World Bank, IMF, AkShare, and official exchange downloads as reference/validation sources rather than preferred primary adapters.

Alternatives considered:

- Single provider: simpler but conflicts with resilience requirement.
- Paid market-data provider: better reliability but conflicts with near-zero data acquisition cost.

Tradeoffs accepted:

- Free sources can be unstable, so the system must invest in quality checks and provider observability.
- Candidate providers remain untrusted until tested against completeness, correctness, timeliness, cost, terms, and rate-limit constraints.
- Official exchange websites/downloads may be used as validation/reference sources, but the preferred backend loading model is reusable exchange-agnostic adapters.

### Exchange Calendars

Recommendation: use an exchange-agnostic calendar validation flow. For every exchange added now or in the future, first try `pandas-market-calendars` as the primary calendar library. During exchange onboarding, compare the library's open/closed days against the official exchange calendar for the validation window and keep manual override records for holidays, special closures, late opens, or source gaps. Add a custom calendar adapter only when the library is missing the exchange or mismatches official dates.

### Authentication / Session Model

Recommendation:

- Mobile API: app-level access controls using API keys or signed client credentials initially, plus rate limiting.
- Operator/admin: private login with strong password, optional two-factor authentication, and access through private network path or SSH tunnel.

Why it fits:

- Product has no backend-owned user-specific alert state.
- Admin actions must be restricted.
- Operator dashboards are internal, not public product surfaces.

Alternatives considered:

- Full end-user auth in backend: not required by current scope.
- Public admin surface: unnecessary risk.

Tradeoffs accepted:

- If future app features require user-specific backend state, the auth model must expand.

### Observability

Recommendation: structured logs, operational metrics, health checks, and compact dashboards.

Why it fits:

- Operator needs visibility into readiness, coverage, exceptions, timing, quality, and universe changes.
- Logs plus metrics are enough for a modular monolith with separate workers.
- Full tracing is not justified at launch.

Alternatives considered:

- Logs only: too weak for investigation.
- Distributed tracing: premature until there are meaningful distributed boundaries.

Tradeoffs accepted:

- Metric definitions need discipline from the start.

### Deployment / Hosting

Recommendation: single VPS deployment using Docker Compose for the Django API, worker/scheduler, reverse proxy, PostgreSQL, backups, and log/metric collection. Use systemd only as the host-level supervisor/timer layer where useful.

Why it fits:

- Matches budget.
- Keeps operations centralized.
- Scales enough for initial and moderate growth.

Alternatives considered:

- Managed cloud-first stack: operationally attractive in places but cost-misaligned.
- Multi-node deployment: unnecessary early.

Tradeoffs accepted:

- VPS failure affects the system unless backup and restore procedures are strong.

## 9. API Boundary Design

### Public Mobile API Groups

#### Readiness

Responsibilities:

- Return exchange/day readiness.
- Return market closed, not ready, ready, partial/problematic, or failed states as appropriate for app refresh decisions.

Example conceptual endpoints:

- `GET /api/v1/exchanges/readiness?exchange=NYSE,NASDAQ,PSE`
- `GET /api/v1/exchanges/{exchange}/readiness/current`

#### Supported Universe

Responsibilities:

- Return supported instruments only.
- Distinguish price availability from signal eligibility.
- Hide excluded and unsupported candidates.

Example conceptual endpoints:

- `GET /api/v1/instruments`
- `GET /api/v1/exchanges/{exchange}/instruments`

#### Current-Day Prices

Responsibilities:

- Return published current-day opening-price data.
- Reject or clearly mark requests for exchanges that are not ready.

Example conceptual endpoints:

- `GET /api/v1/exchanges/{exchange}/prices/current`
- `GET /api/v1/instruments/{instrument}/prices/current`

#### Historical Prices

Responsibilities:

- Return recent daily historical closes.
- Support yesterday's record and latest 30-day bootstrap.
- Enforce retention boundaries.

Example conceptual endpoints:

- `GET /api/v1/instruments/{instrument}/prices/history?days=30`
- `GET /api/v1/exchanges/{exchange}/prices/history?date=YYYY-MM-DD`

#### Signals

Responsibilities:

- Return published `Dip` and `Skyrocket` events.
- Return supporting reasoning context from the existing algorithm.
- Distinguish no event from signal unavailable.

Example conceptual endpoints:

- `GET /api/v1/exchanges/{exchange}/signals/current`
- `GET /api/v1/instruments/{instrument}/signals`

### Private Operator/Admin API Groups

#### Operations

Responsibilities:

- Return load tables for today opening prices and yesterday historical loads.
- Return quality, coverage, status, degraded flags, exceptions, and timing.

#### Universe Changes

Responsibilities:

- Return event history for additions, removals, exclusions, delisting suspicion, restoration, and degradation.
- Support filters by event type, exchange, and instrument.

#### Admin Commands

Responsibilities:

- Configure supported exchanges and instrument types.
- Trigger validation for candidate exchanges.
- Trigger explicit reprocessing.
- Trigger retention cutoff.

### Internal Boundaries

Internal modules should communicate through domain services and database-backed job records rather than through network APIs. Network service boundaries should be deferred until there is a clear scaling or ownership reason.

## 10. Data Model Overview

Conceptual entities:

- `Exchange`: market publication unit, including synthetic `CRY` when crypto is admitted.
- `InstrumentType`: stock, ETF, ETN, crypto.
- `Instrument`: canonical supported instrument identity.
- `Listing`: exchange/venue-specific representation of an instrument or asset.
- `SupportedUniverseState`: current support state for a chosen listing.
- `UniverseChangeRecord`: audit record for additions, removals, exclusions, degradations, and restorations.
- `Provider`: external data source.
- `ProviderAttempt`: provider call/result metadata.
- `PriceRecord`: daily price datum, including historical close and current-day open type.
- `LoadJob`: background job definition and state.
- `InstrumentLoadOutcome`: per-instrument terminal outcome for an exchange/day/load type.
- `ExchangeDayLoad`: aggregate load/publication state for an exchange/day/load type.
- `SignalStatistic`: persisted supporting statistics for the algorithm.
- `SignalEvent`: generated `Dip` or `Skyrocket` event.
- `PublicationRecord`: exchange/day publication state and quality summary.
- `QualityCheck`: benchmark and completeness/correctness results.
- `ReadModel`: precomputed app/operator output tables or materialized views.
- `AdminCommand`: explicit validation, reprocessing, or retention command.

Key relationships:

- An exchange has many listings and exchange-day loads.
- An instrument may have many candidate listings, but only one chosen supported listing is app-visible under the global primary/best-listing policy.
- Exchanges have a derived activity-priority rank based on trailing 60 trading-day average total traded value across supported/candidate listings, normalized to USD/EUR-equivalent for cross-market comparison. This rank is used as the final tie-breaker for multi-listed instruments, is recomputed during exchange validation and periodically, initially monthly, and automatically incorporates newly added exchanges.
- Each exchange has a fixed benchmark sample for correctness checks, selected from the top 20 most active supported instruments by trailing 60 trading-day traded value. Candidate lists refresh during exchange validation and monthly review, but the active benchmark set remains stable unless a benchmark becomes invalid or delisted. Benchmark instruments are manually protected from automatic exclusion unless explicitly removed.
- A supported listing has many price records.
- Price records feed signal statistics and signal events.
- Exchange-day publication covers eligible supported listings for that exchange/day.
- Universe-change records reference instruments, listings, exchanges, and old/new support states.
- Provider attempts can produce candidate values for one instrument/day/load type.
- Publication records point to the load and quality state used for readiness.

Important constraints:

- One final supported listing per multi-listed company under the global policy.
- One chosen venue per supported crypto asset under `CRY`.
- Unique price record per instrument/day/price type after source prioritization.
- Historical records remain stable unless updated through explicit reprocessing.
- Retention applies consistently across prices, signals, and supporting statistics.

## 11. Failure Handling

### External Provider Failures

- Try alternate providers according to source configuration.
- Record provider failure details and rate-limit evidence.
- Keep provider attempts visible for investigation.
- Mark instrument load failed only after retry/exhaustion rules complete.
- Do not publish provider-suspect data without quality checks.

### Stale or Missing Data

- Treat missing expected prices as backend failures unless the market is closed or delisting-suspicion rules apply.
- Track stale or missing data at instrument level.
- Allow suspected delistings to be excluded from coverage denominator only after the defined rule is met.
- Preserve the reason for exclusion or degradation.

### Slow Responses

- Enforce provider request timeouts.
- Retry with backoff.
- Allow alternate sources to satisfy the datum.
- Mark exchange/day partial/problematic or failed if timeliness and completeness cannot be met.

### Invalid Requests

- Reject unsupported exchanges, unsupported instruments, invalid dates, and out-of-retention history requests.
- Do not leak excluded candidate instruments through public APIs.
- Return exchange not ready rather than partial unpublished data for current-day app flows.

### Job Failures

- Persist job state transitions.
- Make jobs idempotent by exchange/day/instrument/load type.
- Use locks to prevent duplicate active jobs for the same unit of work.
- Retry transient failures with bounded attempts.
- Surface failed jobs in operator views.

### Database / Cache Issues

- PostgreSQL is the source of truth; if it is unavailable, API should fail closed for app data rather than serve untrusted stale generated files.
- Read models can be rebuilt from source tables.
- If a read-model refresh fails after publication, retain prior published read model until rebuilt or mark affected view degraded, depending on freshness requirements.

### Rate Limiting

- Track provider-specific quotas and throttling.
- Schedule loads to avoid predictable quota bursts.
- Prefer source diversity over aggressive retry storms.
- Mark provider degradation when repeated rate limits threaten publication.

### Partial Outages

- Publish exchanges independently.
- Do not block NYSE because PSE failed, or vice versa.
- Keep degraded exchange state internal unless it affects app refresh readiness.
- Use operator dashboard to show exchange/day-specific failures and exceptions.

## 12. Performance Strategy

### Caching Strategy

Start with PostgreSQL read models or materialized views for:

- exchange readiness
- current-day prices by exchange
- recent 30-day history by instrument or exchange
- current/recent signals and context
- operator load summaries

Add Redis only when measured read traffic or latency requires it.

### Precomputation

Precompute after publication and reprocessing:

- current-day app payloads per exchange
- latest readiness summaries
- recent historical slices
- signal summaries
- operator load-table aggregates

This fits the daily publication model and avoids expensive repeated joins during app refresh spikes.

### Stale vs Fresh Data

- Public mobile current-day data should come only from ready publication records.
- Historical records are stable by default.
- Operator data can show in-progress states directly.
- If correctness benchmark data is delayed, publication may proceed when allowed by product rules, and correctness validation can complete afterward.

### Bottlenecks

Likely early bottlenecks:

- Free provider rate limits.
- Slow provider responses.
- Initial historical fill volume.
- Poor indexing on price/history tables.
- Recomputing signals across large histories.

Mitigations:

- Provider concurrency limits.
- Per-exchange staged schedules.
- Batch inserts/upserts.
- Proper indexes on instrument/date/type and exchange/day/status.
- Idempotent resumable backfill.
- Daily production refresh jobs always take priority over historical backfill jobs.
- Historical backfill throttling should be resolved during implementation based on provider validation and the agreed target of completing a 30-day backfill for the supported launch universe in under 30 minutes, while allowing slower execution if providers rate-limit.
- Optional table partitioning by date if history grows materially.

### Measurement Approach

Track:

- exchange/day load duration
- provider latency and error rates
- per-exchange coverage
- failed instrument count
- correctness benchmark mismatch rate
- signal computation duration
- API response latency for readiness, current prices, history, and signals
- read-model rebuild duration

## 13. Security and Access Control

### Authentication

- Mobile API should use app-level credentials or signed request tokens initially.
- Operator/admin access should require authenticated sessions.
- Admin access should be private by network path where practical, such as SSH tunnel, VPN, or restricted IP allowlist.

### Authorization

- Public mobile clients can read only supported, app-visible, published data.
- Operator users can read operational dashboards.
- Admin users can change exchange/instrument-type configuration, trigger validation, trigger reprocessing, and apply retention cutoff.
- Administrative actions should be audited.

### Sensitive Data Handling

- Store provider keys, admin credentials, and signing secrets in environment variables or a VPS secret file with restricted permissions.
- Do not store secrets in source control.
- Avoid logging credentials, tokens, or provider keys.
- Keep off-machine backups protected.

### Backups

Recommendation: keep backups frugal at launch. Create automated daily PostgreSQL dumps plus file/config backups on the VPS, overwriting the previous local backup so only one backup copy is stored on VPS disk. Off-machine backups are manual, ad hoc, and unencrypted. Because off-machine backups are not automated, the operator dashboard should expose the latest successful local backup timestamp and the latest recorded off-machine copy timestamp.

### Abuse Prevention

- Rate-limit public API endpoints.
- Bound history request sizes.
- Validate exchange, date, and instrument inputs.
- Reject broad unsupported-universe enumeration.
- Keep operator/admin surfaces private.

## 14. Observability

### Logging

Use structured logs for:

- job start/finish/failure
- provider attempts and failures
- source-prioritization conflicts
- publication decisions
- quality check results
- signal generation failures
- admin commands
- reprocessing actions
- universe changes

### Metrics

Track at minimum:

- exchange/day status
- coverage percentage
- eligible instrument count
- successful load count
- failed load count
- degraded flag
- load duration
- provider success/error/timeout/rate-limit counts
- benchmark mismatch percentage
- job retry counts
- API response latency and error rate

### Alerts

Initial alerts should be simple and owner-focused:

- exchange/day failed
- exchange/day not ready beyond expected publication window
- coverage below 99%
- benchmark mismatches above 5%
- repeated provider failures
- worker not running
- backup failure
- database disk usage threshold

### Health Checks

Expose internal health checks for:

- API process alive
- worker process heartbeat
- database connectivity
- latest scheduler heartbeat
- queue depth or pending job age
- last successful backup

## 15. Evolution Path

### Scaling Path

Near term:

- Single VPS.
- One API process.
- One worker process.
- PostgreSQL.
- Database-backed read models.

Medium term:

- Add worker concurrency for provider loads and signal computation.
- Add Redis for queue/cache if PostgreSQL-backed jobs or read models become limiting.
- Partition large price/statistics tables if needed.
- Move backups to automated off-machine storage.
- Add a low-cost managed database only if VPS operations become the main reliability risk.

Long term:

- Split workers by role only when load patterns justify it, such as ingestion worker, signal worker, and read-model worker.
- Add a dedicated analytical or time-series store only if PostgreSQL no longer serves history and reporting needs.
- Consider service decomposition only if multiple maintainers or clear independent scaling boundaries appear.

### Future Decomposition

Potential future boundaries:

- Market-data ingestion service.
- Signal computation service.
- Operator/reporting service.
- Public mobile API service.

These should remain internal modules until there is a concrete reason to pay the distributed-system cost.

### Implementation Validation Outputs

- Provider validation results for the full exchange-agnostic candidate pool.
- Custom calendar adapters, created only when the exchange-agnostic calendar validation flow shows `pandas-market-calendars` is missing or mismatches an exchange.

### Redesign Triggers

Revisit the architecture if:

- A single VPS cannot meet load windows even after worker tuning.
- PostgreSQL read/write performance becomes a recurring bottleneck that requires tuning within the VPS/Compose PostgreSQL deployment.
- Provider rate limits require more complex orchestration.
- App traffic grows beyond database-backed read-model capacity.
- Redis becomes justified by measured worker latency, PostgreSQL lock/contention issues, read-model latency, app refresh spikes, or cacheable bootstrap/current-day response bottlenecks.
- Multiple maintainers need independent release ownership.
- Crypto or global exchange expansion changes the data model materially.
- Operational recovery expectations exceed what a VPS-first setup can provide.

## 16. Assumptions

- Daily granularity remains stable and intraday behavior stays out of scope.
- The existing signal algorithm is available as callable backend logic.
- One year of history is sufficient for signal computation.
- Up to three years of retained history is enough for the cutoff policy.
- The mobile app primarily needs current readiness, current-day prices/signals, yesterday's record, and a 30-day bootstrap.
- App-facing user-specific alert state remains outside backend scope.
- The operator is comfortable maintaining a VPS.
- Free data sources can provide sufficient launch quality when combined and validated.
- Initial app traffic is moderate enough for PostgreSQL-backed read models.
- Operator dashboards are private/internal and can be pragmatic rather than consumer-polished.

## 17. Open Questions

No currently unresolved architecture questions remain blocking implementation planning. Remaining provider and calendar outputs are listed in Section 15 and are expected to be produced during implementation validation.

## 18. Risks

- Free data sources may be too incomplete, delayed, or inconsistent for the required trust bar.
- Prague Stock Exchange data may be harder to source reliably than NYSE/Nasdaq data.
- Provider terms, rate limits, or formats may change and break ingestion.
- Multi-listed company resolution may be ambiguous without strong identifiers and turnover data.
- Incorrect exchange-calendar handling can cause false failures or missed publications.
- Database-backed jobs can fail subtly if idempotency, locking, and terminal states are not well designed.
- Signal recomputation can become expensive during initial fill or exceptional reprocessing.
- Single-VPS hosting creates a concentrated infrastructure failure point.
- Operator dashboards may under-serve investigations if exception details are too shallow.
- Crypto may not fit the same data-quality and publication model without additional rules.
- Historical stability can be undermined if reprocessing paths are not tightly controlled and audited.
