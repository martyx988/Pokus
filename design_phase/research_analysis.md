# Research Analysis

This document explores implementation approaches for the system defined in [product_spec.md](</c:/Users/marty/VS Code - GitHub/pokus/product_spec.md>). It does not choose a final architecture. Its purpose is to compare realistic options and make tradeoffs explicit for later design decisions.

## Decision Area 1

### 1. Decision Area

System structure for a single-owner production backend with scheduled ingestion, publication logic, operator dashboards, and mobile-facing APIs.

### 2. Options

- Modular monolith
- Modular monolith with separately deployable worker processes
- Microservices split by domain

### 3. How Each Option Works

- Modular monolith: one codebase and one deployable application contains APIs, ingestion logic, publication logic, and operator views, with internal module boundaries.
- Modular monolith with separately deployable worker processes: one codebase and one domain model, but the API process and background job process run separately.
- Microservices split by domain: separate services for ingestion, universe management, signal generation, publication, and operator reporting communicate over network boundaries.

### 4. Pros and Cons

Modular monolith

- Performance: usually strong enough for daily workloads.
- Complexity: lowest of the three.
- Cost: lowest operational cost.
- Scalability: adequate for meaningful growth if the internal boundaries are disciplined.
- Reliability: fewer moving parts reduce failure modes.
- Operational burden: best fit for a single owner.

Modular monolith with separately deployable worker processes

- Performance: strong for scheduled and background-heavy workloads.
- Complexity: moderate.
- Cost: still low to moderate.
- Scalability: better isolation for API traffic versus heavy background jobs.
- Reliability: better fault isolation than a single process, but still simpler than microservices.
- Operational burden: manageable for one owner if deployment remains simple.

Microservices split by domain

- Performance: can scale each area independently.
- Complexity: much higher.
- Cost: higher due to deployment, networking, observability, and coordination overhead.
- Scalability: strongest on paper.
- Reliability: more isolation, but also many more distributed failure modes.
- Operational burden: high for a single owner.

### 5. Business Impact

- Modular monolith supports faster build and lower maintenance risk.
- Separate API and worker processes can improve operational safety without turning the system into a distributed platform.
- Microservices improve theoretical long-term scale, but they slow launch and increase single-owner burden sharply.

### 6. Maturity Assessment

- Modular monolith: Standard / widely adopted
- Modular monolith with separately deployable worker processes: Standard / widely adopted
- Microservices split by domain: Mature but specialized

### 7. When It Makes Sense

- Modular monolith: best when product scope is clear, team size is small, and domain complexity matters more than horizontal team scaling.
- Modular monolith with separately deployable worker processes: best when ingestion and publication jobs may interfere with API responsiveness.
- Microservices split by domain: best when many teams need independent delivery velocity or load patterns are dramatically different.

### 8. Risks

- Modular monolith: can become tangled if module boundaries are not enforced.
- Modular monolith with separately deployable worker processes: can drift into accidental distributed complexity if too many process types are created.
- Microservices split by domain: high hidden complexity, distributed debugging difficulty, and significant maintenance burden.

## Decision Area 2

### 1. Decision Area

Market data ingestion model for daily opening-price and historical close-price workflows.

### 2. Options

- Scheduled polling
- Scheduled polling with staged backfill and refresh jobs
- Event or stream-driven ingestion

### 3. How Each Option Works

- Scheduled polling: the system runs jobs at known times to fetch exchange universe data, current-day opening data, and historical closes.
- Scheduled polling with staged backfill and refresh jobs: separate job types handle initial fills, daily opening loads, daily historical loads, and validation or retry passes.
- Event or stream-driven ingestion: the system consumes live feeds or push-style updates and derives daily outputs from them.

### 4. Pros and Cons

Scheduled polling

- Performance: sufficient for daily systems.
- Complexity: low.
- Cost: low.
- Scalability: acceptable for initial and moderate growth.
- Reliability: predictable if data sources are stable.
- Operational burden: low.

Scheduled polling with staged backfill and refresh jobs

- Performance: strong for this use case.
- Complexity: moderate.
- Cost: still low.
- Scalability: better than simple polling because workloads are separated by purpose.
- Reliability: improved because initial fill, retries, and publication checks are explicit.
- Operational burden: moderate but still realistic for one owner.

Event or stream-driven ingestion

- Performance: strongest for intraday or real-time needs.
- Complexity: high.
- Cost: higher.
- Scalability: high.
- Reliability: can be strong in mature setups, but there are more moving parts.
- Operational burden: high.

### 5. Business Impact

- A scheduled model matches the product promise because the product is daily, not intraday.
- A staged job model improves trust and operational clarity without paying for real-time complexity.
- Stream-driven approaches are hard to justify when daily completeness matters more than minute-level freshness.

### 6. Maturity Assessment

- Scheduled polling: Standard / widely adopted
- Scheduled polling with staged backfill and refresh jobs: Standard / widely adopted
- Event or stream-driven ingestion: Mature but specialized

### 7. When It Makes Sense

- Scheduled polling: good for narrow scope and simple load orchestration.
- Scheduled polling with staged backfill and refresh jobs: good for products with explicit readiness, retries, initial fill, and operator dashboards.
- Event or stream-driven ingestion: good when real-time or near-real-time signals are required.

### 8. Risks

- Scheduled polling: weak retry and state handling can make failures opaque.
- Staged jobs: job orchestration and idempotency must be done carefully.
- Stream-driven ingestion: overengineering risk is high for this product.

## Decision Area 3

### 1. Decision Area

Storage model for prices, supporting statistics, signals, exchange-day load records, and universe-change history.

### 2. Options

- Relational database as primary store
- Relational database plus dedicated time-series store
- Primarily document or key-value oriented storage

### 3. How Each Option Works

- Relational database as primary store: structured tables model exchanges, instruments, daily prices, signals, load states, and audit history.
- Relational database plus dedicated time-series store: relational storage handles domain state and audit records, while a specialized time-series engine stores price history and metrics-like records.
- Primarily document or key-value oriented storage: entities and histories are stored in flexible documents or aggregates rather than strongly relational records.

### 4. Pros and Cons

Relational database as primary store

- Performance: usually strong enough for daily prices, exchange dashboards, and recent-history retrieval.
- Complexity: low to moderate.
- Cost: low.
- Scalability: often sufficient for the expected scope if modeled well.
- Reliability: strong transactional behavior helps publication and audit records.
- Operational burden: low.

Relational database plus dedicated time-series store

- Performance: excellent for large historical volumes and analytical queries.
- Complexity: moderate to high.
- Cost: higher.
- Scalability: stronger for long-term high-volume history.
- Reliability: good, but with more operational coordination.
- Operational burden: higher than a single store.

Primarily document or key-value oriented storage

- Performance: can be good for flexible reads, but depends heavily on access patterns.
- Complexity: moderate.
- Cost: varies.
- Scalability: can scale well horizontally.
- Reliability: weaker fit for rich relationships and audit-style constraints.
- Operational burden: moderate.

### 5. Business Impact

- A relational primary store usually aligns best with the need for auditability, consistency, operator dashboards, and explicit readiness/publication state.
- A mixed relational plus time-series approach may help if history grows materially, but it adds operational overhead early.
- Document-first designs can speed some development styles, but they make business constraints and joins harder to reason about.

### 6. Maturity Assessment

- Relational database as primary store: Standard / widely adopted
- Relational database plus dedicated time-series store: Mature but specialized
- Primarily document or key-value oriented storage: Standard / widely adopted, but less natural for this domain

### 7. When It Makes Sense

- Relational database as primary store: best when domain integrity and auditability matter.
- Relational plus time-series: best when historical analytics become a dominant concern.
- Document or key-value store: best when the domain is flexible and relational consistency matters less.

### 8. Risks

- Relational only: poor schema design can create slow historical queries later.
- Relational plus time-series: duplicated data models can create drift.
- Document-oriented: hidden complexity in reporting and consistency enforcement.

## Decision Area 4

### 1. Decision Area

Background processing and work coordination for loads, retries, initial fill, validation, and recomputation.

### 2. Options

- In-process scheduled jobs without a queue
- Lightweight job queue
- Distributed messaging platform

### 3. How Each Option Works

- In-process scheduled jobs without a queue: the application runs scheduled tasks directly and tracks execution state in application storage.
- Lightweight job queue: jobs are enqueued and processed asynchronously by one or more workers with retry and status support.
- Distributed messaging platform: workloads are broken into events and messages flowing through a broker for multiple consumers.

### 4. Pros and Cons

In-process scheduled jobs without a queue

- Performance: sufficient for small steady workloads.
- Complexity: lowest.
- Cost: lowest.
- Scalability: limited.
- Reliability: can be acceptable, but retries and visibility often need custom work.
- Operational burden: low initially, but may grow awkwardly.

Lightweight job queue

- Performance: good for staged ingestion, retries, reprocessing, and validation workflows.
- Complexity: moderate.
- Cost: low to moderate.
- Scalability: good for this system.
- Reliability: strong if idempotency and job state are designed well.
- Operational burden: manageable.

Distributed messaging platform

- Performance: excellent at scale.
- Complexity: high.
- Cost: higher.
- Scalability: very strong.
- Reliability: strong in expert hands, but hard to run simply.
- Operational burden: high.

### 5. Business Impact

- No-queue scheduling is cheap and simple, but can become brittle when retries, partial failures, and explicit publication rules accumulate.
- A lightweight queue fits the need for predictable background work without burdening a single owner with broker-heavy operations.
- Distributed messaging is likely too complex for a daily product with one maintainer.

### 6. Maturity Assessment

- In-process scheduled jobs without a queue: Standard / widely adopted
- Lightweight job queue: Standard / widely adopted
- Distributed messaging platform: Mature but specialized

### 7. When It Makes Sense

- No queue: good for small systems with simple daily batches.
- Lightweight queue: good when jobs have states, retries, and operator visibility.
- Distributed messaging: good when many independent services must react to high event volumes.

### 8. Risks

- No queue: hidden retry logic and weak observability can hurt trust.
- Lightweight queue: still requires careful design around duplicate execution and job recovery.
- Distributed messaging: high maintenance burden and overengineering risk.

## Decision Area 5

### 1. Decision Area

API interaction model for the mobile app and operator-facing reads.

### 2. Options

- REST-style resource API
- GraphQL API
- Mixed model with REST for core flows and internal query endpoints for operations

### 3. How Each Option Works

- REST-style resource API: clients request specific resources such as readiness, supported instruments, prices, history, and signals.
- GraphQL API: clients ask for exactly the fields they want in a query graph.
- Mixed model: public mobile-facing interactions stay resource-based, while operator views may use more tailored read paths.

### 4. Pros and Cons

REST-style resource API

- Performance: predictable.
- Complexity: low.
- Cost: low.
- Scalability: good.
- Reliability: strong and easy to cache or reason about.
- Operational burden: low.

GraphQL API

- Performance: flexible, but query patterns can become expensive.
- Complexity: moderate to high.
- Cost: moderate.
- Scalability: good with discipline.
- Reliability: fine, but requires stronger query governance.
- Operational burden: higher than simple resources.

Mixed model

- Performance: strong if kept disciplined.
- Complexity: moderate.
- Cost: low to moderate.
- Scalability: good.
- Reliability: good if boundaries stay clear.
- Operational burden: manageable.

### 5. Business Impact

- Resource-oriented APIs are the most straightforward match for known app behaviors like readiness checks, daily current data reads, and 30-day bootstrap loads.
- GraphQL adds flexibility, but this app has fairly well-defined access patterns, so much of that flexibility may not be needed.
- A mixed approach can keep mobile consumption simple while still serving operator dashboards efficiently.

### 6. Maturity Assessment

- REST-style resource API: Standard / widely adopted
- GraphQL API: Standard / widely adopted
- Mixed model: Standard / widely adopted

### 7. When It Makes Sense

- REST: best when use cases are stable and predictable.
- GraphQL: best when multiple clients need highly variable shapes.
- Mixed model: best when public and internal consumers differ significantly.

### 8. Risks

- REST: too many endpoints if not grouped well.
- GraphQL: hidden cost and authorization complexity.
- Mixed model: can drift into inconsistency if conventions are weak.

## Decision Area 6

### 1. Decision Area

Caching and read optimization for recent history, readiness checks, and daily current data.

### 2. Options

- Direct reads from primary storage
- Database-backed materialized or precomputed read views
- Hybrid with dedicated cache for hot reads

### 3. How Each Option Works

- Direct reads from primary storage: API queries hit the main persistent store directly.
- Database-backed materialized or precomputed read views: the system pre-shapes the most common outputs such as exchange readiness or recent-history slices.
- Hybrid with dedicated cache for hot reads: a cache stores frequently read current-day and recent-history responses while primary storage remains the source of truth.

### 4. Pros and Cons

Direct reads from primary storage

- Performance: fine if query shapes remain modest.
- Complexity: lowest.
- Cost: lowest.
- Scalability: acceptable at modest scale.
- Reliability: strong because there is one source of truth.
- Operational burden: lowest.

Database-backed materialized or precomputed read views

- Performance: strong for repetitive dashboard and app patterns.
- Complexity: moderate.
- Cost: low.
- Scalability: better than direct-only when reads grow.
- Reliability: good if refresh logic is clear.
- Operational burden: moderate.

Hybrid with dedicated cache

- Performance: strongest for repeated hot reads.
- Complexity: moderate to high.
- Cost: moderate.
- Scalability: strong.
- Reliability: can be good, but cache invalidation becomes important.
- Operational burden: higher.

### 5. Business Impact

- Direct reads reduce cost and complexity, which is attractive for a single owner.
- Precomputed views align well with fixed app behaviors such as today readiness, today prices, yesterday history, and 30-day bootstrap.
- Dedicated caches can help if the mobile audience grows materially, but they may be unnecessary early.

### 6. Maturity Assessment

- Direct reads from primary storage: Standard / widely adopted
- Database-backed materialized or precomputed read views: Standard / widely adopted
- Hybrid with dedicated cache: Standard / widely adopted

### 7. When It Makes Sense

- Direct reads: best when traffic is modest and schema/query design is good.
- Precomputed views: best when access patterns are highly repetitive and publication creates natural refresh boundaries.
- Dedicated cache: best when read volume or latency pressure becomes substantial.

### 8. Risks

- Direct reads: can degrade over time as historical and operational tables grow.
- Precomputed views: stale read models if refresh timing is poorly defined.
- Dedicated cache: invalidation errors can undermine trust.

## Decision Area 7

### 1. Decision Area

Observability model for quality, readiness, operator dashboards, and failure investigation.

### 2. Options

- Logs-first observability
- Logs plus metrics dashboards
- Logs, metrics, and distributed tracing

### 3. How Each Option Works

- Logs-first observability: the system records structured operational events and relies heavily on log inspection.
- Logs plus metrics dashboards: structured logs remain available, but key quality and load states are also tracked as metrics and shown in dashboards.
- Logs, metrics, and distributed tracing: tracing is added to follow requests and background job flows across components.

### 4. Pros and Cons

Logs-first observability

- Performance: fine.
- Complexity: low.
- Cost: low.
- Scalability: acceptable initially.
- Reliability: adequate for small systems.
- Operational burden: can become painful during investigations.

Logs plus metrics dashboards

- Performance: fine.
- Complexity: moderate.
- Cost: low to moderate.
- Scalability: strong enough for this system.
- Reliability: much better operational clarity.
- Operational burden: best balance for daily operations and investigations.

Logs, metrics, and distributed tracing

- Performance: fine.
- Complexity: high.
- Cost: moderate to high.
- Scalability: strongest.
- Reliability: very strong diagnostic capability.
- Operational burden: highest.

### 5. Business Impact

- Logs alone are cheap but force more manual detective work.
- Logs plus metrics directly support the product requirement of compact dashboards showing status, timing, coverage, and quality.
- Full tracing is valuable when there are many distributed boundaries, but that seems ahead of this product’s likely near-term needs.

### 6. Maturity Assessment

- Logs-first observability: Standard / widely adopted
- Logs plus metrics dashboards: Standard / widely adopted
- Logs, metrics, and distributed tracing: Mature but specialized

### 7. When It Makes Sense

- Logs-first: best for early internal tools with low investigation pressure.
- Logs plus metrics: best for production-grade systems with explicit SLA-like quality expectations.
- Full tracing: best when requests cross many services or asynchronous stages.

### 8. Risks

- Logs-first: too much manual analysis burden for a single owner.
- Logs plus metrics: requires disciplined instrumentation definitions.
- Full tracing: overengineering risk if the system remains fairly compact.

## Decision Area 8

### 1. Decision Area

Infrastructure model under a near-zero budget beyond a paid VPS.

### 2. Options

- Single VPS, mostly self-managed
- VPS plus selective managed components where free or cheap tiers exist
- Heavily managed cloud-first setup

### 3. How Each Option Works

- Single VPS, mostly self-managed: the application, storage, background processing, and dashboards are run under one self-managed footprint.
- VPS plus selective managed components where free or cheap tiers exist: the core runs on the VPS, but certain supporting capabilities may use low-cost external services.
- Heavily managed cloud-first setup: databases, queues, logging, and compute are provided by managed cloud products.

### 4. Pros and Cons

Single VPS, mostly self-managed

- Performance: adequate for modest to meaningful early scale.
- Complexity: operational complexity exists, but it is centralized.
- Cost: best fit for the stated budget.
- Scalability: limited compared with cloud-native managed fleets.
- Reliability: depends on good operations and backups.
- Operational burden: manageable if kept simple.

VPS plus selective managed components where free or cheap tiers exist

- Performance: good.
- Complexity: moderate.
- Cost: can remain reasonable if limited carefully.
- Scalability: better than VPS-only.
- Reliability: some components may become easier to run.
- Operational burden: moderate because the system spans multiple environments.

Heavily managed cloud-first setup

- Performance: strong.
- Complexity: can simplify some operations but introduces provider-specific complexity.
- Cost: worst fit for the stated budget constraint.
- Scalability: strongest.
- Reliability: potentially high.
- Operational burden: mixed, but financially misaligned.

### 5. Business Impact

- VPS-first approaches match the user’s hard budget constraint.
- Selective managed add-ons can be attractive only if they do not create recurring spend pressure or operational split-brain.
- Cloud-first managed designs are hard to justify for this product’s economics.

### 6. Maturity Assessment

- Single VPS, mostly self-managed: Standard / widely adopted
- VPS plus selective managed components: Standard / widely adopted
- Heavily managed cloud-first setup: Standard / widely adopted, but misaligned here

### 7. When It Makes Sense

- Single VPS: best when budget is tight and the owner prefers operational simplicity through centralization.
- Hybrid VPS plus selective managed components: best when one or two pain points justify limited external dependency.
- Managed cloud-first: best when budget is not a primary constraint.

### 8. Risks

- Single VPS: infrastructure failures affect the whole system if recovery practices are weak.
- Hybrid model: hidden dependency and integration complexity.
- Managed cloud-first: cost creep and architectural drift away from product constraints.

## Cross-Area Summary

### Common Patterns

Most teams building a daily, production-grade, data-heavy backend with one main operator would typically favor:

- a modular monolith or modular application with separate worker execution
- scheduled jobs rather than real-time streaming
- a relational primary store
- a lightweight queue or disciplined async job model
- resource-oriented APIs
- logs plus metrics dashboards
- simple infrastructure aligned to the real budget

### Conservative (Low-Risk) Approach

The lowest-risk family of choices tends to be:

- modular monolith
- scheduled ingestion with staged backfill and refresh jobs
- relational primary storage
- lightweight async job coordination rather than full distributed messaging
- REST-style or similarly resource-oriented APIs
- direct reads or precomputed read views for the most common app patterns
- logs plus metrics dashboards
- single-VPS or similarly cost-disciplined hosting

This path minimizes moving parts, aligns well with daily publication logic, and best fits a single owner.

### High-Performance / Scalable Approach

The higher-scale family of choices tends to be:

- modular application split into separately deployable API and worker processes, or eventually microservices
- staged async processing with stronger queueing
- relational storage supplemented by time-series or analytical read optimization
- hybrid read model with precomputed views and caching
- richer observability including tracing
- more elastic infrastructure

This path improves headroom, but it also raises operational and design cost significantly.

### Likely Overengineering

For this system, the following are the clearest overengineering risks:

- microservices from the start
- streaming-first ingestion for a daily product
- distributed messaging platforms intended for high-volume event choreography
- full tracing-heavy observability before the system has meaningful distributed complexity
- cloud-first managed sprawl that conflicts with the budget constraint

## Assumptions and Gaps

### Assumptions Made

- The product specification is the source of truth.
- Daily granularity is stable and not expected to evolve into intraday behavior soon.
- The existing signal algorithm can be treated as a black box from the perspective of system structure.
- Correctness benchmark verification is an internal quality mechanism rather than a user-facing feature.
- Operator dashboards are internal tools, not consumer-facing analytics surfaces.
- Expected supported-universe growth after several exchange expansions is around 15,000 instruments.
- Expected app scale is around 10,000 users, but API decisions should preserve room for further growth.
- Expected active usage can be approximated as around 3,000 daily active users, roughly 200 peak concurrent refreshes, and low-to-moderate request volume with short spikes around daily refresh windows.
- Operator dashboards live on the VPS backend and are accessed privately through an SSH tunnel from the owner's home PC.
- The alert algorithm is moderate in computational cost and suitable for routine daily processing.
- Recovery expectations imply no more than 15 minutes of acceptable data loss and that more than 15 minutes of unavailability is concerning.
- Backup expectations are frugal: automated daily PostgreSQL dumps plus file/config backups on the VPS, overwriting the previous local backup so only one local backup copy is stored, plus manual ad hoc unencrypted off-machine backup copies.

### Unclear or Missing Inputs

- Additional research is required to prepare an exchange-agnostic market-data source candidate pool for backend ingestion. This should not be limited to NYSE, Nasdaq, or Prague Stock Exchange.
- The candidate pool must include `yfinance`.
- FinceptTerminal should be reviewed as inspiration for source discovery because it advertises broad connector coverage, including Yahoo Finance, Polygon, FRED, IMF, World Bank, DBnomics, AkShare, government APIs, and broker/market-data integrations.
- The initial validation matrix should include: `yfinance`, Stooq/pandas-datareader, Nasdaq Data Link/free datasets, Alpha Vantage, Twelve Data, Financial Modeling Prep, Finnhub, Tiingo, Polygon free tier, EODHD/free tier, Marketstack/free tier, OpenFIGI for identifiers, DBnomics, FRED, World Bank, IMF, AkShare, and official exchange downloads as reference/validation sources rather than preferred primary adapters.
- All listed candidate sources should be tested during validation, because many are expected to fail completeness, speed, cost, terms, rate-limit, or exchange-coverage requirements. Failed candidates are useful validation outcomes, not wasted effort.
- The research output should be a validation matrix of free sources, APIs, and Python libraries that may support daily open/close prices, historical prices, volume/turnover, instrument discovery, identifiers, and exchange-calendar support across current and future exchanges.
- Each candidate source should be assessed later against completeness, correctness, timeliness, speed, cost, terms, rate limits, exchange coverage, implementation effort, and operational reliability.
