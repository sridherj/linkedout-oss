# Startup Pipeline Migration Analysis

> Spike S3: Compatibility analysis for migrating the startup discovery/enrichment pipeline from `linkedin_intel` (second-brain) to LinkedOut.

**Date:** 2026-03-27
**Status:** Analysis complete

---

## 1. Current State: Tables and Queries Used by Pipeline

### Tables Touched by Pipeline Code

The pipeline code lives in `~/workspace/second-brain/agents/pipeline/` and operates against the PostgreSQL database `linkedin_intel`. Below is every table referenced in the three core files (`db.py`, `company_ops.py`, `enrichment/helpers.py`).

| Table | Used By | Operations |
|-------|---------|------------|
| `companies` | `db.py`, `company_ops.py` | SELECT, INSERT, UPDATE (upsert by `canonical_name` / `normalized_name`) |
| `funding_rounds` | `db.py`, `company_ops.py` | SELECT, INSERT, UPDATE (upsert by company_id + round_type + amount_usd) |
| `growth_signals` | `db.py`, `company_ops.py` | SELECT, INSERT (upsert on company_id + signal_type + signal_date + source) |
| `pipeline_state` | `db.py` | SELECT, UPDATE (singleton rows keyed by `pipeline_name`) |
| `raw_feed_items` | `db.py` | INSERT (bulk via `execute_values`, upsert on gmail_message_id + source_url) |
| `company_growth_metrics` | `db.py` | REFRESH MATERIALIZED VIEW CONCURRENTLY |

### SQL Queries Extracted from Pipeline Code

#### `db.py` -- 10 queries

1. **`upsert_raw_items`** -- INSERT INTO `raw_feed_items` (gmail_message_id, email_received_at, source_feed, feed_category, title, summary, source_url, raw_url, published_at) ON CONFLICT (gmail_message_id, source_url) DO NOTHING
2. **`reset_run_counters`** -- UPDATE `pipeline_state` SET run_* = 0 WHERE pipeline_name = %s
3. **`finalize_run_counters`** -- UPDATE `pipeline_state` SET total_* = total_* + run_* WHERE pipeline_name = %s
4. **`update_pipeline_state`** -- UPDATE `pipeline_state` SET <dynamic fields> WHERE pipeline_name = %s
5. **`get_unenriched_companies`** -- SELECT c.id, c.canonical_name, c.normalized_name, c.website, c.description, c.vertical FROM companies c LEFT JOIN funding_rounds fr ON c.id = fr.company_id WHERE c.watching = true AND fr.id IS NULL
6. **`get_companies_by_names`** -- SELECT id, canonical_name, normalized_name, website, description, vertical FROM companies WHERE normalized_name = ANY(%s)
7. **`get_existing_rounds`** -- SELECT id, round_type, amount_usd, announced_on, lead_investors, source, confidence FROM funding_rounds WHERE company_id = %s
8. **`get_existing_signals`** -- SELECT id, signal_type, signal_date, value_numeric, value_text, source, source_url, confidence FROM growth_signals WHERE company_id = %s [AND signal_type = %s]
9. **`update_company_metadata`** -- UPDATE companies SET <vertical, hq_city, hq_country, founded_year, estimated_employee_count, website, description, estimated_arr_usd, arr_signal_date, arr_confidence> WHERE id = %s
10. **`enrichment_report`** -- Multiple aggregate queries: COUNT(DISTINCT fr.company_id), COUNT(*) with confidence grouping, signal_type grouping, estimated_arr_usd coverage

#### `company_ops.py` -- 5 queries

1. **`insert_or_match_company`** -- SELECT id FROM companies WHERE normalized_name = %s; UPDATE companies SET watching = true WHERE id = %s; INSERT INTO companies (canonical_name, normalized_name, website, description, watching, vertical) ON CONFLICT (canonical_name) DO UPDATE SET watching = true
2. **`insert_funding_round`** -- SELECT id, confidence FROM funding_rounds WHERE company_id = %s AND round_type = %s AND amount_usd IS NOT DISTINCT FROM %s; UPDATE funding_rounds SET ... WHERE id = %s (confidence upgrade); INSERT INTO funding_rounds (...) ON CONFLICT DO NOTHING
3. **`insert_growth_signal`** -- INSERT INTO growth_signals (...) ON CONFLICT (company_id, signal_type, signal_date, source) DO UPDATE SET ... WHERE EXCLUDED.confidence > growth_signals.confidence

#### `enrichment/helpers.py` -- 0 new queries

Pure CLI wrapper that delegates to `db.py` and `company_ops.py` functions. No direct SQL.

---

## 2. Column Mapping Table

### `companies` (old) -> `company` (new LinkedOut)

| Old Column | New LinkedOut Column | Notes |
|---|---|---|
| `id` (SERIAL int) | `id` (TEXT nanoid, prefix 'co') | PK type change -- see Section 4 |
| `canonical_name` | `canonical_name` | Direct match |
| `normalized_name` | `normalized_name` | Direct match |
| `linkedin_url` | `linkedin_url` | Direct match |
| `linkedin_id` | **MISSING** | Dropped in new schema |
| `universal_name` | `universal_name` | Direct match |
| `pdl_id` | **MISSING** | External ID dropped |
| `wikidata_id` | **MISSING** | External ID dropped |
| `sec_cik` | **MISSING** | External ID dropped |
| `website` | `website` | Direct match |
| `domain` | `domain` | Direct match |
| `industry` | `industry` | Direct match |
| `founded_year` | `founded_year` | Direct match |
| `hq_city` | `hq_city` | Direct match |
| `hq_country` | `hq_country` | Direct match |
| `employee_count_range` | `employee_count_range` | Direct match |
| `estimated_employee_count` | `estimated_employee_count` | Direct match |
| `size_tier` | `size_tier` | Direct match |
| `network_connection_count` | `network_connection_count` | Direct match |
| `parent_company_id` (INTEGER) | `parent_company_id` (TEXT) | FK type change (int -> nanoid) |
| `enrichment_sources` | `enrichment_sources` | Direct match (TEXT[]) |
| `enriched_at` | `enriched_at` | Direct match |
| `watching` (BOOLEAN) | **MISSING** | Startup-specific flag |
| `description` (TEXT) | **MISSING** | Startup-specific |
| `vertical` (TEXT) | **MISSING** | Startup-specific (industry is closest) |
| `sub_category` | **MISSING** | Startup-specific |
| `funding_stage` | **MISSING** | Denormalized from funding_rounds |
| `total_raised_usd` | **MISSING** | Denormalized from funding_rounds |
| `last_funding_date` | **MISSING** | Denormalized from funding_rounds |
| `round_count` | **MISSING** | Denormalized from funding_rounds |
| `estimated_arr_usd` | **MISSING** | Revenue tracking |
| `arr_signal_date` | **MISSING** | Revenue tracking |
| `arr_confidence` | **MISSING** | Revenue tracking |

### `funding_rounds` (old) -> Does not exist in new LinkedOut

| Old Column | New LinkedOut Column |
|---|---|
| `id` (SERIAL) | **TABLE MISSING** |
| `company_id` (INTEGER FK) | **TABLE MISSING** |
| `round_type` | **TABLE MISSING** |
| `announced_on` | **TABLE MISSING** |
| `amount_usd` | **TABLE MISSING** |
| `lead_investors` | **TABLE MISSING** |
| `all_investors` | **TABLE MISSING** |
| `source` | **TABLE MISSING** |
| `source_url` | **TABLE MISSING** |
| `confidence` | **TABLE MISSING** |
| `notes` | **TABLE MISSING** |

### `growth_signals` (old) -> Does not exist in new LinkedOut

Entire table is missing from new schema.

### `pipeline_state` (old) -> Does not exist in new LinkedOut

Pipeline infrastructure table -- not part of domain model.

### `raw_feed_items` (old) -> Does not exist in new LinkedOut

Pipeline infrastructure table -- not part of domain model.

---

## 3. Missing Columns

### Missing from `company` Entity (Required by Pipeline)

These columns are actively queried by pipeline code but do not exist in the new LinkedOut `CompanyEntity`:

| Column | Used By | Impact |
|---|---|---|
| `watching` (BOOLEAN) | `get_unenriched_companies`, `enrichment_report`, `company_growth_metrics` | **HIGH** -- core filter for all enrichment queries |
| `description` (TEXT) | `insert_or_match_company`, `get_unenriched_companies` | **MEDIUM** -- stored during discovery |
| `vertical` (TEXT) | `get_unenriched_companies`, `update_company_metadata` | **MEDIUM** -- could map to `industry` but semantics differ |
| `funding_stage` (TEXT) | Denormalized trigger from `funding_rounds` | **LOW** -- can recompute from `funding_round` table |
| `total_raised_usd` (BIGINT) | Denormalized trigger | **LOW** -- can recompute |
| `last_funding_date` (DATE) | Denormalized trigger | **LOW** -- can recompute |
| `round_count` (INTEGER) | Denormalized trigger | **LOW** -- can recompute |
| `estimated_arr_usd` (BIGINT) | `enrichment_report` | **MEDIUM** -- revenue snapshot on company |
| `arr_signal_date` (DATE) | Revenue trigger | **LOW** |
| `arr_confidence` (SMALLINT) | Revenue trigger | **LOW** |

### Entire Tables Missing from LinkedOut

| Table | Impact |
|---|---|
| `funding_rounds` | **HIGH** -- core enrichment data, needs new entity |
| `growth_signals` | **HIGH** -- growth/revenue tracking, needs new entity |
| `pipeline_state` | **MEDIUM** -- pipeline infra, can live as separate migration |
| `raw_feed_items` | **MEDIUM** -- pipeline infra |
| `extracted_companies` | **MEDIUM** -- pipeline infra |
| `discovery_signals` | **MEDIUM** -- pipeline infra |
| `pipeline_failed_items` | **LOW** -- dead letter queue |
| `company_growth_metrics` (materialized view) | **MEDIUM** -- needs funding_rounds first |

---

## 4. PK Migration Notes

### Integer -> Nanoid

The old schema uses `SERIAL` (auto-increment integer) PKs. The new LinkedOut schema uses nanoid string PKs with entity-specific prefixes (via `BaseEntity`).

| Entity | Old PK | New PK Format | Example |
|---|---|---|---|
| companies | `42` (int) | `co_abc123xyz` (text) | Prefix: `co` |
| funding_rounds | `1001` (int) | `fr_def456uvw` (text) | Prefix: `fr` (proposed) |
| growth_signals | `5001` (int) | `gs_ghi789rst` (text) | Prefix: `gs` (proposed) |

**Migration implications:**

1. **All FK references change type.** `funding_rounds.company_id` changes from `INTEGER` to `TEXT`. All pipeline queries using `%s` placeholders continue to work (psycopg2 handles TEXT params fine), but the VALUES must be nanoid strings.
2. **Data migration requires a mapping table.** During migration, build `old_id -> new_nanoid` lookup for companies. Then rewrite all FK references in funding_rounds, growth_signals, etc.
3. **Pipeline code changes.** Functions like `insert_or_match_company` return `int | None` today. Must return `str | None` after migration. Type hints and callers need updating.
4. **CLI `--company-id` arguments.** Currently `type=int` in argparse. Must change to `type=str`.

---

## 5. Connection String Changes

### Old Pattern (second-brain pipeline)

```python
# db.py get_connection()
dsn = os.environ.get("LINKEDIN_INTEL_DSN") or os.environ.get("DATABASE_URL")
if dsn:
    conn = psycopg2.connect(dsn)
else:
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "linkedin_intel"),
        user=os.environ.get("PGUSER", "sj"),
        password=os.environ.get("PGPASSWORD", ""),
    )
```

- Raw `psycopg2` connections
- Database name: `linkedin_intel`
- Manual connection management (each function opens/closes)
- `conn.autocommit = False` with explicit `conn.commit()`

### New Pattern (LinkedOut)

```python
# SQLAlchemy async engine via shared infrastructure
# src/shared/infrastructure/database/connection.py (or similar)
SQLALCHEMY_DATABASE_URL = settings.database_url  # from .env
engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)
```

- SQLAlchemy 2.0 with async sessions
- Database name: `linkedout` (or configured via `DATABASE_URL`)
- Dependency-injected sessions (FastAPI `Depends`)
- Declarative ORM (not raw SQL)

### Migration approach:

**Option A (recommended for Phase 1):** Keep pipeline code using raw psycopg2 but point it at the LinkedOut database. The pipeline is a batch job -- it does not need async sessions or DI. Add `LINKEDOUT_DSN` env var. This minimizes code changes.

**Option B (full migration):** Rewrite pipeline to use SQLAlchemy ORM through LinkedOut's repository layer. More work but enables code reuse and testing via the existing test infrastructure.

---

## 6. New Entity Drafts

### FundingRoundEntity

Required by the enrichment pipeline. Maps directly from old `funding_rounds` table.

```python
"""Funding round entity -- shared (no tenant/BU scoping)."""
from typing import Optional
from sqlalchemy import BigInteger, Date, Index, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from common.entities.base_entity import BaseEntity


class FundingRoundEntity(BaseEntity):
    __tablename__ = 'funding_round'
    id_prefix = 'fr'

    company_id: Mapped[str] = mapped_column(
        String, nullable=False,
        comment='FK to company entity'
    )
    round_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment='Seed, Series A, Series B, etc.'
    )
    announced_on: Mapped[Optional[str]] = mapped_column(
        Date, nullable=True,
        comment='Date the round was announced'
    )
    amount_usd: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment='Round amount in whole USD'
    )
    lead_investors: Mapped[Optional[list]] = mapped_column(
        ARRAY(Text), nullable=True,
        comment='Lead investor names'
    )
    all_investors: Mapped[Optional[list]] = mapped_column(
        ARRAY(Text), nullable=True,
        comment='All investor names'
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment='URL of the source article'
    )
    confidence: Mapped[int] = mapped_column(
        SmallInteger, default=5,
        comment='Confidence score 1-10'
    )

    __table_args__ = (
        Index('ix_fr_company', 'company_id'),
        Index('ix_fr_announced', 'announced_on'),
        Index('ix_fr_round_type', 'round_type'),
        Index('ix_fr_dedup', 'company_id', 'round_type', 'amount_usd', unique=True),
    )
```

**Notes:**
- `source` field from old schema maps to `BaseEntity.source` (inherited).
- `notes` field from old schema maps to `BaseEntity.notes` (inherited).
- `created_at` / `updated_at` inherited from `BaseEntity`.
- FK to `company(id)` should be added in migration, not in entity (following LinkedOut conventions for shared entities).

### StartupTrackingEntity (Alternative: Columns on CompanyEntity)

The old schema added startup-specific columns directly to the `companies` table (`watching`, `description`, `vertical`, `funding_stage`, etc.). Two options:

**Option A -- Add columns to CompanyEntity (recommended):**

Add `watching`, `description`, `vertical` to `CompanyEntity`. The denormalized funding columns (`funding_stage`, `total_raised_usd`, etc.) can be computed from `FundingRoundEntity` via a materialized view or trigger, as the old schema does.

**Option B -- Separate StartupTrackingEntity:**

```python
class StartupTrackingEntity(BaseEntity):
    __tablename__ = 'startup_tracking'
    id_prefix = 'st'

    company_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    watching: Mapped[bool] = mapped_column(default=False)
    vertical: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sub_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    funding_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    total_raised_usd: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    last_funding_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    round_count: Mapped[int] = mapped_column(Integer, default=0)
    estimated_arr_usd: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    arr_signal_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    arr_confidence: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
```

**Recommendation:** Option A is simpler. Add `watching` (BOOLEAN), `description` (TEXT), and `vertical` (TEXT) to `CompanyEntity`. The denormalized funding summary columns should be computed via a view, not stored on the company row -- this is cleaner than the trigger-based approach in the old schema.

### GrowthSignalEntity

Required by enrichment pipeline for revenue/traction tracking.

```python
"""Growth signal entity -- shared (no tenant/BU scoping)."""
from typing import Optional
from sqlalchemy import BigInteger, Date, Index, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from common.entities.base_entity import BaseEntity


class GrowthSignalEntity(BaseEntity):
    __tablename__ = 'growth_signal'
    id_prefix = 'gs'

    company_id: Mapped[str] = mapped_column(
        String, nullable=False,
        comment='FK to company entity'
    )
    signal_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment='arr, mrr, revenue, revenue_growth_pct, notable_customers, etc.'
    )
    signal_date: Mapped[str] = mapped_column(
        Date, nullable=False,
        comment='Date the signal was observed'
    )
    value_numeric: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment='Numeric value (USD for revenue, count for headcount)'
    )
    value_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment='Human-readable description of the signal'
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment='URL where the signal was found'
    )
    confidence: Mapped[int] = mapped_column(
        SmallInteger, default=5,
        comment='Confidence score 1-10'
    )

    __table_args__ = (
        Index('ix_gs_company_date', 'company_id', 'signal_date'),
        Index('ix_gs_dedup', 'company_id', 'signal_type', 'signal_date', 'source', unique=True),
    )
```

**Notes:**
- `source` field reuses `BaseEntity.source` (inherited).
- Dedup index uses `source` from BaseEntity -- matches old schema's `(company_id, signal_type, signal_date, source)` unique constraint.

---

## 7. Pipeline Infrastructure Tables

These tables are pipeline-specific (not domain entities) and are not part of the LinkedOut data model. They need to be created separately, either as LinkedOut entities or as raw SQL migrations.

### `pipeline_state`

```sql
CREATE TABLE IF NOT EXISTS pipeline_state (
    pipeline_name           TEXT PRIMARY KEY,
    last_run_started_at     TIMESTAMPTZ,
    last_run_completed_at   TIMESTAMPTZ,
    last_successful_run_at  TIMESTAMPTZ,
    status                  TEXT DEFAULT 'idle'
        CHECK (status IN ('idle', 'running', 'success', 'failed')),
    error_message           TEXT,
    last_gmail_history_id   TEXT,
    total_emails_processed  INTEGER DEFAULT 0,
    total_items_parsed      INTEGER DEFAULT 0,
    total_items_extracted   INTEGER DEFAULT 0,
    total_companies_found   INTEGER DEFAULT 0,
    total_noise_flagged     INTEGER DEFAULT 0,
    total_promoted          INTEGER DEFAULT 0,
    total_errors            INTEGER DEFAULT 0,
    run_emails_processed    INTEGER DEFAULT 0,
    run_items_parsed        INTEGER DEFAULT 0,
    run_items_extracted     INTEGER DEFAULT 0,
    run_companies_found     INTEGER DEFAULT 0,
    run_noise_flagged       INTEGER DEFAULT 0,
    run_promoted            INTEGER DEFAULT 0,
    run_errors              INTEGER DEFAULT 0,
    metadata                JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `raw_feed_items`

```sql
CREATE TABLE IF NOT EXISTS raw_feed_items (
    id                  SERIAL PRIMARY KEY,
    gmail_message_id    TEXT NOT NULL,
    email_received_at   TIMESTAMPTZ,
    source_feed         TEXT NOT NULL,
    feed_category       TEXT,
    title               TEXT NOT NULL,
    summary             TEXT,
    source_url          TEXT NOT NULL,
    raw_url             TEXT,
    published_at        TIMESTAMPTZ,
    extracted_at        TIMESTAMPTZ,
    is_noise            BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (gmail_message_id, source_url)
);
```

### `extracted_companies`

```sql
CREATE TABLE IF NOT EXISTS extracted_companies (
    id                  SERIAL PRIMARY KEY,
    raw_item_id         INTEGER NOT NULL REFERENCES raw_feed_items(id) ON DELETE CASCADE,
    company_name        TEXT NOT NULL,
    normalized_name     TEXT,
    description_snippet TEXT,
    website_url         TEXT,
    role_in_item        TEXT DEFAULT 'primary',
    has_funding_event   BOOLEAN DEFAULT FALSE,
    amount_usd          BIGINT,
    round_type          TEXT,
    announced_on        DATE,
    lead_investors      TEXT[],
    all_investors       TEXT[],
    confidence          SMALLINT DEFAULT 5,
    is_ai_startup       BOOLEAN,
    dedup_status        TEXT DEFAULT 'pending',
    matched_company_id  TEXT,  -- changed from INTEGER to TEXT for nanoid FK
    dedup_method        TEXT,
    dedup_score         NUMERIC(4,3),
    dedup_run_at        TIMESTAMPTZ,
    source              TEXT DEFAULT 'rss_pipeline',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `discovery_signals`

```sql
CREATE TABLE IF NOT EXISTS discovery_signals (
    id                  SERIAL PRIMARY KEY,
    normalized_name     TEXT NOT NULL UNIQUE,
    canonical_name      TEXT,
    signal_count        INTEGER DEFAULT 1,
    source_feeds        TEXT[],
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    best_description    TEXT,
    best_website_url    TEXT,
    best_confidence     SMALLINT DEFAULT 5,
    is_ai_startup       BOOLEAN,
    sample_raw_item_ids INTEGER[],
    has_funding_event   BOOLEAN DEFAULT FALSE,
    amount_usd          BIGINT,
    round_type          TEXT,
    lead_investors      TEXT[],
    promotion_status    TEXT DEFAULT 'candidate',
    promoted_company_id TEXT,  -- changed from INTEGER to TEXT for nanoid FK
    reviewed_by         TEXT,
    reviewed_at         TIMESTAMPTZ,
    rejection_reason    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `pipeline_failed_items`

```sql
CREATE TABLE IF NOT EXISTS pipeline_failed_items (
    id              SERIAL PRIMARY KEY,
    raw_item_id     INTEGER REFERENCES raw_feed_items(id) ON DELETE SET NULL,
    stage           TEXT NOT NULL,
    error_type      TEXT,
    error_message   TEXT NOT NULL,
    stack_trace     TEXT,
    item_data       JSONB,
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    next_retry_at   TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    pipeline_name   TEXT DEFAULT 'startup_discovery',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `company_growth_metrics` (Materialized View)

Depends on `funding_rounds` (-> `funding_round`) and `companies` (-> `company`) existing first. DDL from old schema can be adapted once `FundingRoundEntity` exists.

### Decision: Entity vs Raw SQL

Pipeline infrastructure tables (`pipeline_state`, `raw_feed_items`, `extracted_companies`, `discovery_signals`, `pipeline_failed_items`) are operational tables, not domain entities. Two options:

- **Option A:** Create as raw Alembic migrations (no SQLAlchemy entity). Keeps pipeline tables separate from the domain model.
- **Option B:** Create as LinkedOut entities with `BaseEntity` inheritance. More consistent but adds entity/repo/service boilerplate for tables that are only used by batch jobs.

**Recommendation:** Option A for pipeline infra tables. Option B only for `FundingRoundEntity` and `GrowthSignalEntity` which are domain entities used by both the pipeline and the LinkedOut API.

---

## 8. Stale Agent Assessment

### `taskos-startup-discover` -- STALE

**Evidence:**
- Agent description says: "add them to the SQLite companies database (`data/companies.db`)"
- Imports from `agents.shared.db` (SQLite module), not `agents.pipeline.db` (PostgreSQL module)
- Uses functions: `get_connection()`, `add_company()`, `company_exists()`, `find_by_normalized_name()`, `get_company_count()` -- all from the SQLite module
- The pipeline code (`promote.py`) actually promotes companies to PostgreSQL via `company_ops.insert_or_match_company()`
- **Verdict: Fully stale.** The discover agent writes to a SQLite database that is no longer the source of truth. The PostgreSQL `companies` table in `linkedin_intel` is the actual data store. This agent needs to be rewritten to target either `linkedin_intel` or (after migration) the LinkedOut PostgreSQL database.

### `taskos-startup-enrich` -- PARTIALLY STALE

**Evidence:**
- Correctly references PostgreSQL `linkedin_intel` database
- Uses `agents.pipeline.enrichment.helpers` CLI (which uses `agents.pipeline.db`)
- Company IDs are integers (`--company-id <ID>` with `type=int`)
- **Verdict: Partially stale.** Works against the old schema. After migration to LinkedOut, needs updates for: nanoid company IDs, new connection string, possibly new CLI wrapper.

### `taskos-startup-pipeline` -- PARTIALLY STALE

**Evidence:**
- Runs `agents.pipeline.run` which uses `agents.pipeline.db` (PostgreSQL)
- Parses output but does not directly query the database
- **Verdict: Minimally stale.** Will work as long as the pipeline code itself is migrated. Agent definition just needs env var updates.

---

## 9. Migration Effort Estimate

### Phase 1: Domain Entities (Prerequisite)

| Task | Effort | Notes |
|---|---|---|
| Add `watching`, `description`, `vertical` columns to `CompanyEntity` | 2h | Simple column additions + Alembic migration |
| Create `FundingRoundEntity` + repo + service | 4-6h | Follow CRUD scaffold pattern. Shared entity (no tenant scoping). |
| Create `GrowthSignalEntity` + repo + service | 4-6h | Similar to FundingRoundEntity |
| Create `company_growth_metrics` materialized view | 2h | Alembic raw SQL migration |
| **Phase 1 Subtotal** | **12-16h (~2 days)** | |

### Phase 2: Pipeline Code Migration

| Task | Effort | Notes |
|---|---|---|
| Update `db.py` connection to use `LINKEDOUT_DSN` | 1h | Env var change |
| Update all queries for nanoid PKs (TEXT instead of INTEGER) | 3-4h | Every `company_id` param changes type |
| Update `company_ops.py` for new table name (`company` not `companies`) | 2h | Table name + column changes |
| Update `enrichment/helpers.py` argparse (`--company-id` to str) | 1h | Trivial |
| Create pipeline infra tables via Alembic migration | 3h | Raw SQL migration for pipeline_state, raw_feed_items, etc. |
| Data migration script (old int PKs -> nanoid PKs) | 4-6h | Build mapping table, rewrite all FKs |
| **Phase 2 Subtotal** | **14-18h (~2-3 days)** | |

### Phase 3: Agent Updates

| Task | Effort | Notes |
|---|---|---|
| Rewrite `taskos-startup-discover` agent | 4h | Switch from SQLite to LinkedOut PostgreSQL |
| Update `taskos-startup-enrich` agent | 2h | Nanoid IDs, new connection |
| Update `taskos-startup-pipeline` agent | 1h | Env var changes |
| **Phase 3 Subtotal** | **7h (~1 day)** | |

### Total Estimate

| Phase | Effort |
|---|---|
| Phase 1: Domain Entities | 2 days |
| Phase 2: Pipeline Code | 2-3 days |
| Phase 3: Agent Updates | 1 day |
| **Total** | **5-6 days** |

**Risk factors:**
- Data migration (Phase 2) is the riskiest part -- integer-to-nanoid FK rewriting across 6+ tables
- Pipeline infra tables may surface additional queries in files not analyzed (e.g., `promote.py`, `dedup.py`, `extract.py`, `news/` modules)
- The `company_growth_metrics` materialized view depends on triggers that may need rethinking with SQLAlchemy ORM

---

## Appendix: Files Analyzed

| File | Location |
|---|---|
| `db.py` | `~/workspace/second-brain/agents/pipeline/db.py` |
| `company_ops.py` | `~/workspace/second-brain/agents/pipeline/company_ops.py` |
| `enrichment/helpers.py` | `~/workspace/second-brain/agents/pipeline/enrichment/helpers.py` |
| `schema.sql` | `~/workspace/second-brain/linkedin-intel/db/schema.sql` |
| `startup_extensions.sql` | `~/workspace/second-brain/linkedin-intel/db/startup_extensions.sql` |
| `pipeline_tables.sql` | `~/workspace/second-brain/linkedin-intel/db/pipeline_tables.sql` |
| `company_entity.py` | `/data/workspace/linkedout/src/linkedout/company/entities/company_entity.py` |
| `linkedout_data_model.collab.md` | `/data/workspace/linkedout/docs/specs/linkedout_data_model.collab.md` |
| `taskos-startup-pipeline.md` | `~/workspace/second-brain/.claude/agents/taskos-startup-pipeline.md` |
| `taskos-startup-enrich.md` | `~/workspace/second-brain/.claude/agents/taskos-startup-enrich.md` |
| `taskos-startup-discover.md` | `~/workspace/second-brain/.claude/agents/taskos-startup-discover.md` |
