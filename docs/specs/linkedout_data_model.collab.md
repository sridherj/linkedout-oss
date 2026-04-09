---
feature: linkedout-data-model
module: core
scope: Schema design, table relationships, shared vs scoped split, affinity source tracking, indexes, RLS policies
linked_files:
  - backend/src/common/entities/base_entity.py
  - backend/src/common/entities/tenant_bu_mixin.py
  - backend/src/common/entities/soft_delete_mixin.py
  - backend/src/common/entities/agent_run_entity.py
  - backend/src/organization/entities/tenant_entity.py
  - backend/src/organization/entities/bu_entity.py
  - backend/src/organization/entities/app_user_entity.py
  - backend/src/organization/entities/app_user_tenant_role_entity.py
  - backend/src/organization/enrichment_config/entities/enrichment_config_entity.py
  - backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py
  - backend/src/linkedout/experience/entities/experience_entity.py
  - backend/src/linkedout/education/entities/education_entity.py
  - backend/src/linkedout/profile_skill/entities/profile_skill_entity.py
  - backend/src/linkedout/company/entities/company_entity.py
  - backend/src/linkedout/company_alias/entities/company_alias_entity.py
  - backend/src/linkedout/role_alias/entities/role_alias_entity.py
  - backend/src/linkedout/connection/entities/connection_entity.py
  - backend/src/linkedout/contact_source/entities/contact_source_entity.py
  - backend/src/linkedout/import_job/entities/import_job_entity.py
  - backend/src/linkedout/enrichment_event/entities/enrichment_event_entity.py
  - backend/src/linkedout/search_session/entities/search_session_entity.py
  - backend/src/linkedout/search_session/entities/search_turn_entity.py
  - backend/src/linkedout/search_tag/entities/search_tag_entity.py
  - backend/src/linkedout/funding/entities/funding_round_entity.py
  - backend/src/linkedout/funding/entities/growth_signal_entity.py
  - backend/src/linkedout/funding/entities/startup_tracking_entity.py
  - backend/migrations/versions/001_baseline.py
version: 1
last_verified: "2026-04-09"
---

# LinkedOut Data Model Spec

> Multi-tenant schema for warm network intelligence. Shared crawled profiles + user-scoped connections with multi-source affinity tracking.

**Scope:** All database tables, relationships, constraints, indexes, RLS policies, and the shared-vs-scoped split rationale.
**Status:** Verified against OSS codebase 2026-04-09.

---

## Design Principles

1. **Shared dimension, private connections.** LinkedIn profile data (crawled via Apify or other crawlers) is public — shared across all tenants. Who you know and how well you know them is private — scoped per user (AppUser), with Tenant+BU as the structural scoping container.
2. **AppUser-level by default, tenant-level for team sharing.** All day-to-day operations (search, import, affinity) filter by `app_user_id`. Tenant+BU exists as the structural scope. In Phase 5, two AppUsers from the same tenant can optionally share their combined network. Until then, Tenant:BU is practically 1:1.
3. **TenantBuMixin on all scoped tables.** Every scoped entity has `tenant_id` and `bu_id` (via TenantBuMixin) plus `app_user_id` (FK to AppUser) for ownership. Default queries filter by `app_user_id`. Team queries filter by `tenant_id`.
4. **Affinity source is always tracked.** Every signal that feeds into the affinity score records where it came from. Affinity scores are idempotent and regenerable — if we improve the algorithm later, we can recompute for all users from the stored signal data.
5. **Nanoid primary keys.** All tables use string PKs with entity-specific prefixes (e.g., `tenant_abc123`, `conn_xyz789`), following the codebase's BaseEntity pattern.
6. **Table naming: singular.** Following codebase convention where table names match entity names (e.g., `connection` not `connections`, `experience` not `experiences`). Entity class `ConnectionEntity` -> table `connection`.
7. **SQLite-compatible entity definitions.** Entity classes use Text placeholders for PostgreSQL-specific types (ARRAY, JSONB, TSVECTOR, vector) to enable SQLite-backed unit tests. Actual PostgreSQL types are applied in Alembic migrations. Exceptions: `ContactSourceEntity.raw_record` uses `JSONB` directly (auto-compiled to JSON for SQLite by a custom compiler). `SearchTurnEntity.transcript` and `SearchTurnEntity.results` also use `JSONB` directly. `ExperienceEntity.is_current` uses a regular nullable Boolean instead of the spec's `GENERATED ALWAYS` computed column because SQLite does not support computed columns.
8. **Dual embedding columns.** `crawled_profile` stores two embedding vectors: `embedding_openai` (1536-dim, text-embedding-3-small) and `embedding_nomic` (768-dim, nomic-embed-text-v1.5). The `embedding_model` and `embedding_dim` columns track which model generated the active embedding.

---

## BaseEntity Fields

All entities inherit from `BaseEntity`, which provides these common fields. They are **not repeated** in individual table definitions below.

```sql
-- Provided by BaseEntity on ALL tables:
id                TEXT PRIMARY KEY,              -- nanoid with entity-specific prefix
created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
deleted_at        TIMESTAMPTZ,                   -- soft delete timestamp
archived_at       TIMESTAMPTZ,                   -- archive timestamp
created_by        TEXT,                          -- who created this record
updated_by        TEXT,                          -- who last updated
is_active         BOOLEAN NOT NULL DEFAULT TRUE,
version           INTEGER NOT NULL DEFAULT 1,
source            TEXT,                          -- data origin tracking
notes             TEXT                           -- free-form notes
```

Additionally, entities using **TenantBuMixin** automatically get:

```sql
-- Provided by TenantBuMixin:
tenant_id         TEXT NOT NULL REFERENCES tenant(id),
bu_id             TEXT NOT NULL REFERENCES bu(id)
```

---

## Table Overview

### Shared Dimension Tables (no tenant_id, no bu_id)

These tables store data that is reusable across all users/tenants. No scoping.

| Table | Purpose | Approximate Scale |
|-------|---------|-------------------|
| `crawled_profile` | Profile data from crawlers (Apify etc), deduped by normalized LinkedIn URL | 22K initial, growing |
| `experience` | Work history per profile | ~134K |
| `education` | School records per profile | ~30K |
| `profile_skill` | Skills per profile | ~80K |
| `company` | Canonical company records | ~49K |
| `company_alias` | Variant company names -> canonical | ~10K |
| `role_alias` | Variant role titles -> canonical | ~500 |

### Scoped Tables (TenantBuMixin + app_user_id FK)

These tables store private data. Scoped by Tenant+BU (via TenantBuMixin) with `app_user_id` FK for ownership. Default queries filter by `app_user_id`. Team queries filter by `tenant_id`.

| Table | Purpose | Scoping |
|-------|---------|---------|
| `connection` | Who you know — links an AppUser to crawled profiles | TenantBuMixin + app_user_id + FK -> crawled_profile |
| `contact_source` | Raw import records per source per user | TenantBuMixin + app_user_id |
| `import_job` | Upload/import tracking per user | TenantBuMixin + app_user_id |
| `enrichment_event` | Crawler cost tracking per user | TenantBuMixin + app_user_id |
| `search_session` | Conversational search sessions per user | TenantBuMixin + app_user_id |
| `search_turn` | Individual conversation turns within a search session | TenantBuMixin + session_id FK |
| `search_tag` | Profile tags created during search sessions | TenantBuMixin + app_user_id |

### Organization Tables

| Table | Purpose |
|-------|---------|
| `tenant` | Root grouping entity. One per org. |
| `bu` | Business unit within a tenant. Tenant:BU is 1:1 for now. |
| `app_user` | System-level user entity. Not scoped by tenant. |
| `app_user_tenant_role` | Maps users to tenant roles. |
| `enrichment_config` | Per-user enrichment settings (platform vs BYOK). FK -> app_user. |

### Funding / Startup Pipeline Tables (shared, no tenant/BU scoping)

| Table | Purpose |
|-------|---------|
| `funding_round` | Funding round data per company. Shared. |
| `growth_signal` | Revenue/headcount/metric signals per company. Shared. |
| `startup_tracking` | Per-company pipeline metadata (watching, vertical, ARR). Shared. 1:1 with company. |

### Infrastructure Tables

| Table | Purpose |
|-------|---------|
| `agent_run` | Tracks async agent executions with LLM metrics. Scoped via TenantBuMixin. |

---

## Organization Tables

### tenant

Root grouping entity. One per org/company.

```sql
CREATE TABLE tenant (
    -- id, audit fields inherited from BaseEntity (prefix: 'tenant')
    name              TEXT NOT NULL,
    description       TEXT
);
```

### bu

Business unit within a tenant. Tenant:BU is 1:1 for now — BU adds a future-proof scoping layer.

```sql
CREATE TABLE bu (
    -- id, audit fields inherited from BaseEntity (prefix: 'bu')
    tenant_id         TEXT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    description       TEXT
);
```

**Relationship:** Tenant -> BU is 1:Many with cascade delete. Each BU belongs to exactly one Tenant.

**Indexes:**
```sql
CREATE INDEX ix_bu_tenant ON bu(tenant_id);
```

### app_user

System-level user entity. Not scoped by tenant — AppUser sits above the tenant hierarchy. Association to tenants is via `AppUserTenantRoleEntity` (separate mapping table).

```sql
CREATE TABLE app_user (
    -- id, audit fields inherited from BaseEntity (prefix: 'usr')
    email             TEXT UNIQUE NOT NULL,
    name              TEXT,
    auth_provider_id  TEXT UNIQUE,                -- OAuth provider ID
    api_key_prefix    VARCHAR(8),                 -- first 8 chars for identification
    api_key_hash      TEXT,                       -- hashed API key

    -- Profile linkage
    own_crawled_profile_id TEXT REFERENCES crawled_profile(id) ON DELETE SET NULL,
        -- The user's own LinkedIn profile in the crawled_profile table.
        -- Used by affinity scorer for career overlap calculation.

    -- Preferences
    network_preferences    TEXT
        -- Free-text user preferences about their network.
        -- Injected into search agent system prompt to bias results.
);
```

**Note:** Auth middleware resolves `app_user_id` + `tenant_id` from the API key. The system user record (`sys_admin_1`) is created during seeding/migration for system-initiated operations.

**User-profile linkage design:** `own_crawled_profile_id` establishes a direct FK from the user to their own crawled profile, replacing the previous implicit approach of reverse-looking up `crawled_profile.source_app_user_id`. The explicit FK is unambiguous (source_app_user_id tracks cost attribution, not identity) and survives re-crawls triggered by other users.

**Indexes:**
```sql
CREATE UNIQUE INDEX ix_app_user_email ON app_user(email);
CREATE UNIQUE INDEX ix_app_user_auth_provider ON app_user(auth_provider_id) WHERE auth_provider_id IS NOT NULL;
CREATE INDEX ix_au_own_profile ON app_user(own_crawled_profile_id);
```

### app_user_tenant_role

Maps users to tenant roles. Enables multi-tenant user access.

```sql
CREATE TABLE app_user_tenant_role (
    -- id, audit fields inherited from BaseEntity (prefix: 'autr')
    app_user_id       TEXT NOT NULL REFERENCES app_user(id),
    tenant_id         TEXT NOT NULL REFERENCES tenant(id),
    role              VARCHAR(20) NOT NULL         -- e.g., 'admin', 'member'
);
```

**Indexes:**
```sql
CREATE INDEX ix_autr_app_user ON app_user_tenant_role(app_user_id);
CREATE INDEX ix_autr_tenant ON app_user_tenant_role(tenant_id);
```

### enrichment_config

Per-user enrichment settings. Controls whether the user uses the platform's Apify account or brings their own key (BYOK).

```sql
CREATE TABLE enrichment_config (
    -- id, audit fields inherited from BaseEntity (prefix: 'ec')
    app_user_id           TEXT NOT NULL REFERENCES app_user(id),
    enrichment_mode       TEXT NOT NULL DEFAULT 'platform',  -- 'platform' or 'byok'
    apify_key_encrypted   TEXT,                    -- Fernet-encrypted, NULL if platform mode
    apify_key_hint        TEXT                     -- last 4 chars for UI display
);
```

**Indexes:**
```sql
CREATE UNIQUE INDEX uq_enrichment_config_app_user_id ON enrichment_config(app_user_id);
```

---

## Shared Dimension Tables

### crawled_profile

One row per person. Shared across all users/tenants. Dedup key: normalized `linkedin_url`. Same row gets updated on re-crawl (upsert by `linkedin_url`), not a new row — `last_crawled_at` tracks freshness.

```sql
CREATE TABLE crawled_profile (
    -- id, audit fields inherited from BaseEntity (prefix: 'cp')
    linkedin_url          VARCHAR(500) UNIQUE NOT NULL,  -- normalized: https://www.linkedin.com/in/<slug>
    public_identifier     VARCHAR(255),              -- LinkedIn public ID (slug)

    -- Identity
    first_name            VARCHAR(255),
    last_name             VARCHAR(255),
    full_name             VARCHAR(500),              -- computed or stored for search convenience
    headline              TEXT,
    about                 TEXT,

    -- Location (structured from enrichment)
    location_city         VARCHAR(255),
    location_state        VARCHAR(255),
    location_country      VARCHAR(255),
    location_country_code VARCHAR(10),
    location_raw          VARCHAR(500),              -- original unstructured string

    -- LinkedIn metadata
    connections_count     INTEGER,
    follower_count        INTEGER,
    open_to_work          BOOLEAN,
    premium               BOOLEAN,

    -- Current position (denormalized for fast display)
    current_company_name  VARCHAR(500),
    current_position      VARCHAR(500),
    company_id            TEXT REFERENCES company(id),

    -- Classification (computed during enrichment)
    seniority_level       VARCHAR(100),              -- 'ic', 'senior', 'staff', 'director', 'vp', 'c_suite'
    function_area         VARCHAR(100),              -- 'engineering', 'product', 'sales', 'hr', etc.

    -- Dual embedding vectors
    embedding_openai      vector(1536),              -- OpenAI text-embedding-3-small
    embedding_nomic       vector(768),               -- nomic-embed-text-v1.5
    embedding_model       VARCHAR(64),               -- model that generated the active embedding
    embedding_dim         SMALLINT,                  -- dimension of the active embedding
    embedding_updated_at  TIMESTAMPTZ,               -- when embedding was last generated

    -- Search vectors
    search_vector         TEXT,                       -- tsvector placeholder (actual tsvector in migration)

    -- Enrichment state
    source_app_user_id    TEXT REFERENCES app_user(id),  -- who triggered the crawl. sys_admin_1 for system-initiated.
    data_source           VARCHAR(50) NOT NULL,       -- 'apify', 'netrows', 'csv_only'
    has_enriched_data     BOOLEAN NOT NULL DEFAULT FALSE,
    last_crawled_at       TIMESTAMPTZ,               -- when crawler last refreshed this profile
    profile_image_url     VARCHAR(1000),              -- URL to profile image
    raw_profile           TEXT                        -- lossless original crawler response (Text placeholder for JSONB)
);
```

**Re-crawl behavior:** When a profile is re-crawled (e.g., >90 days stale), the existing row is updated via upsert on `linkedin_url`. `last_crawled_at` is refreshed, `raw_profile` is overwritten, and derived fields (headline, current_position, etc.) are re-extracted. Previous raw data is not versioned — point-in-time is sufficient for v1.

**Indexes:**
```sql
-- B-tree indexes
CREATE UNIQUE INDEX ix_cp_linkedin_url ON crawled_profile(linkedin_url);
CREATE INDEX ix_cp_company_id ON crawled_profile(company_id);
CREATE INDEX ix_cp_current_company ON crawled_profile(current_company_name);
CREATE INDEX ix_cp_location ON crawled_profile(location_city, location_country_code);
CREATE INDEX ix_cp_seniority ON crawled_profile(seniority_level);
CREATE INDEX ix_cp_function ON crawled_profile(function_area);
CREATE INDEX ix_cp_has_enriched ON crawled_profile(has_enriched_data);
CREATE INDEX ix_cp_source_app_user ON crawled_profile(source_app_user_id);

-- Trigram GIN indexes (pg_trgm) for LIKE/ILIKE queries
CREATE INDEX ix_cp_full_name_trgm ON crawled_profile USING gin(full_name gin_trgm_ops);
CREATE INDEX ix_cp_current_company_trgm ON crawled_profile USING gin(current_company_name gin_trgm_ops);
CREATE INDEX ix_cp_headline_trgm ON crawled_profile USING gin(headline gin_trgm_ops);
CREATE INDEX ix_cp_current_position_trgm ON crawled_profile USING gin(current_position gin_trgm_ops);
CREATE INDEX ix_cp_location_city_trgm ON crawled_profile USING gin(location_city gin_trgm_ops);
CREATE INDEX ix_cp_location_raw_trgm ON crawled_profile USING gin(location_raw gin_trgm_ops);

-- HNSW indexes for pgvector approximate nearest-neighbor search
CREATE INDEX ix_cp_embedding_openai_hnsw ON crawled_profile USING hnsw(embedding_openai vector_cosine_ops);
CREATE INDEX ix_cp_embedding_nomic_hnsw ON crawled_profile USING hnsw(embedding_nomic vector_cosine_ops);
```

**LinkedIn URL normalization rule:**
Strip query params, trailing slashes, country prefixes, force lowercase, always include `www.` -> `https://www.linkedin.com/in/<slug>`. This is the global dedup key. Implemented in `backend/src/shared/utils/linkedin_url.py` (backend) and `extension/lib/profile/url.ts` (extension). Examples:
- `https://www.linkedin.com/in/JohnDoe/?originalSubdomain=uk` -> `https://www.linkedin.com/in/johndoe`
- `https://uk.linkedin.com/in/JohnDoe/` -> `https://www.linkedin.com/in/johndoe`
- `https://linkedin.com/in/janedoe` -> `https://www.linkedin.com/in/janedoe`

### experience

Work history. One row per job. Shared across tenants. FK to crawled_profile.

```sql
CREATE TABLE experience (
    -- id, audit fields inherited from BaseEntity (prefix: 'exp')
    crawled_profile_id      TEXT NOT NULL REFERENCES crawled_profile(id) ON DELETE CASCADE,

    -- Job data
    position                TEXT,
    position_normalized     TEXT,                    -- mapped via role_alias
    company_name            VARCHAR(500),
    company_id              TEXT REFERENCES company(id),
    company_linkedin_url    VARCHAR(500),
    employment_type         VARCHAR(50),             -- 'full_time', 'contract', etc.

    -- Dates
    start_date              DATE,
    start_year              INTEGER,
    start_month             INTEGER,
    end_date                DATE,                    -- NULL if current
    end_year                INTEGER,
    end_month               INTEGER,
    end_date_text           VARCHAR(50),             -- 'Present' or 'May 2022'
    is_current              BOOLEAN,                 -- nullable Boolean (SQLite compat, no GENERATED ALWAYS)

    -- Classification
    seniority_level         VARCHAR(100),
    function_area           VARCHAR(100),

    -- Other
    location                VARCHAR(500),
    description             TEXT,
    raw_experience          TEXT                     -- Text placeholder for JSONB
);
```

**Indexes:**
```sql
CREATE INDEX ix_exp_profile ON experience(crawled_profile_id);
CREATE INDEX ix_exp_company ON experience(company_id);
CREATE INDEX ix_exp_current ON experience(is_current);
CREATE INDEX ix_exp_dates ON experience(start_date, end_date);
CREATE INDEX ix_exp_profile_start ON experience(crawled_profile_id, start_date DESC NULLS FIRST);
CREATE INDEX ix_exp_company_profile ON experience(company_id, crawled_profile_id);

-- Trigram GIN indexes
CREATE INDEX ix_exp_company_name_trgm ON experience USING gin(company_name gin_trgm_ops);
CREATE INDEX ix_exp_position_trgm ON experience USING gin(position gin_trgm_ops);
```

### education

School records. Shared. FK to crawled_profile.

```sql
CREATE TABLE education (
    -- id, audit fields inherited from BaseEntity (prefix: 'edu')
    crawled_profile_id    TEXT NOT NULL REFERENCES crawled_profile(id) ON DELETE CASCADE,
    school_name           TEXT,
    school_linkedin_url   VARCHAR(500),
    degree                VARCHAR(255),
    field_of_study        VARCHAR(255),
    start_year            INTEGER,
    end_year              INTEGER,
    description           TEXT,
    raw_education         TEXT                       -- Text placeholder for JSONB
);
```

**Indexes:**
```sql
CREATE INDEX ix_edu_profile ON education(crawled_profile_id);
CREATE INDEX ix_edu_school ON education(school_name);

-- Trigram GIN indexes
CREATE INDEX ix_edu_school_trgm ON education USING gin(school_name gin_trgm_ops);
CREATE INDEX ix_edu_degree_trgm ON education USING gin(degree gin_trgm_ops);
```

### profile_skill

Skills per profile. Shared. FK to crawled_profile.

```sql
CREATE TABLE profile_skill (
    -- id, audit fields inherited from BaseEntity (prefix: 'psk')
    crawled_profile_id    TEXT NOT NULL REFERENCES crawled_profile(id) ON DELETE CASCADE,
    skill_name            VARCHAR(255) NOT NULL,
    endorsement_count     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (crawled_profile_id, skill_name)
);
```

**Indexes:**
```sql
CREATE INDEX ix_psk_profile ON profile_skill(crawled_profile_id);
CREATE INDEX ix_psk_skill ON profile_skill(skill_name);

-- Trigram GIN index
CREATE INDEX ix_psk_skill_trgm ON profile_skill USING gin(skill_name gin_trgm_ops);
```

### company

Canonical company records. Shared.

```sql
CREATE TABLE company (
    -- id, audit fields inherited from BaseEntity (prefix: 'co')
    canonical_name            VARCHAR(255) UNIQUE NOT NULL,
    normalized_name           VARCHAR(255) NOT NULL,

    -- LinkedIn identifiers
    linkedin_url              VARCHAR(500),
    universal_name            VARCHAR(255),

    -- Core metadata
    website                   VARCHAR(500),
    domain                    VARCHAR(255),
    industry                  VARCHAR(255),
    founded_year              INTEGER,
    hq_city                   VARCHAR(255),
    hq_country                VARCHAR(100),

    -- Size data (critical for affinity scoring normalization)
    employee_count_range      VARCHAR(50),
    estimated_employee_count  INTEGER,
    size_tier                 VARCHAR(20),            -- 'tiny', 'small', 'mid', 'large', 'enterprise'

    -- How many connections across ALL users work/worked here
    network_connection_count  INTEGER NOT NULL DEFAULT 0,

    -- Hierarchy
    parent_company_id         TEXT,                   -- self-referencing (no FK constraint in entity)

    -- Enrichment tracking
    enrichment_sources        TEXT[],
    enriched_at               TIMESTAMPTZ,

    -- External enrichment identifiers
    pdl_id                    VARCHAR(100),           -- People Data Labs company ID
    wikidata_id               VARCHAR(50)             -- Wikidata Q-number (e.g., Q95)
);
```

**Indexes:**
```sql
CREATE UNIQUE INDEX ix_co_canonical ON company(canonical_name);
CREATE INDEX ix_co_domain ON company(domain);
CREATE INDEX ix_co_industry ON company(industry);
CREATE INDEX ix_co_size_tier ON company(size_tier);
CREATE INDEX ix_co_parent ON company(parent_company_id);
CREATE INDEX ix_co_hq_country ON company(hq_country);

-- Trigram GIN indexes
CREATE INDEX ix_co_canonical_trgm ON company USING gin(canonical_name gin_trgm_ops);
CREATE INDEX ix_co_domain_trgm ON company USING gin(domain gin_trgm_ops);
```

### company_alias

Maps variant names to canonical company. Shared.

```sql
CREATE TABLE company_alias (
    -- id, audit fields inherited from BaseEntity (prefix: 'ca')
    alias_name   TEXT NOT NULL,
    company_id   TEXT NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    source       TEXT,                              -- 'auto', 'cleanco', 'rapidfuzz', 'llm', 'manual'
    UNIQUE (alias_name, company_id)
);
```

**Indexes:**
```sql
CREATE INDEX ix_ca_alias_name ON company_alias(alias_name);
CREATE INDEX ix_ca_company_id ON company_alias(company_id);

-- Trigram GIN index
CREATE INDEX ix_ca_alias_trgm ON company_alias USING gin(alias_name gin_trgm_ops);
```

### role_alias

Maps variant titles to canonical roles. Shared.

```sql
CREATE TABLE role_alias (
    -- id, audit fields inherited from BaseEntity (prefix: 'ra')
    alias_title      VARCHAR(255) UNIQUE NOT NULL,
    canonical_title  VARCHAR(255) NOT NULL,
    seniority_level  VARCHAR(100),
    function_area    VARCHAR(100)
);
```

**Indexes:**
```sql
CREATE UNIQUE INDEX ix_ra_alias_title ON role_alias(alias_title);
CREATE INDEX ix_ra_canonical_title ON role_alias(canonical_title);
CREATE INDEX ix_ra_seniority_level ON role_alias(seniority_level);
CREATE INDEX ix_ra_function_area ON role_alias(function_area);

-- Trigram GIN indexes
CREATE INDEX ix_ra_alias_trgm ON role_alias USING gin(alias_title gin_trgm_ops);
CREATE INDEX ix_ra_canonical_trgm ON role_alias USING gin(canonical_title gin_trgm_ops);
```

---

## Scoped Tables

All scoped tables use **TenantBuMixin** (provides `tenant_id` + `bu_id`) plus an explicit `app_user_id` FK for ownership.

### connection

The core scoped entity. Links an AppUser to shared crawled profiles. Contains affinity data with source tracking.

```sql
CREATE TABLE connection (
    -- id, audit fields inherited from BaseEntity (prefix: 'conn')
    -- tenant_id, bu_id inherited from TenantBuMixin
    app_user_id           TEXT NOT NULL REFERENCES app_user(id),
    crawled_profile_id    TEXT NOT NULL REFERENCES crawled_profile(id),

    -- Connection metadata
    connected_at          DATE,                     -- when the LinkedIn connection was made
    emails                TEXT,                      -- comma-separated email addresses
    phones                TEXT,                      -- comma-separated phone numbers
    tags                  TEXT,                      -- comma-separated structural tags
    sources               TEXT[],                    -- which import sources contributed (e.g., ['linkedin_csv', 'google_contacts'])
    source_details        TEXT,                      -- JSON string: per-source detail (Text placeholder for JSONB)

    -- Affinity scoring (computed, idempotent, regenerable)
    affinity_score        FLOAT,
    dunbar_tier           VARCHAR(50),               -- 'inner_circle', 'active', 'familiar', 'acquaintance'

    -- Individual affinity signals (stored for transparency + recomputation)
    affinity_source_count     FLOAT NOT NULL DEFAULT 0,   -- normalized: appears in N import sources
    affinity_recency          FLOAT NOT NULL DEFAULT 0,   -- normalized: how recent the connection
    affinity_career_overlap   FLOAT NOT NULL DEFAULT 0,   -- normalized: shared employers (months * size_factor)
    affinity_mutual_connections FLOAT NOT NULL DEFAULT 0,  -- normalized: mutual connections in same tenant
    affinity_external_contact   FLOAT NOT NULL DEFAULT 0,  -- external contact warmth signal
    affinity_embedding_similarity FLOAT NOT NULL DEFAULT 0, -- embedding similarity signal

    -- Recomputation tracking
    affinity_computed_at  TIMESTAMPTZ,
    affinity_version      INTEGER NOT NULL DEFAULT 0, -- increments on each recomputation

    -- Dedup key: one connection per person PER AppUser
    UNIQUE (app_user_id, crawled_profile_id)
);
```

**Note on OSS column types:** In the OSS codebase, `emails`, `phones`, and `tags` are stored as comma-separated `Text` columns (not PostgreSQL ARRAY). `source_details` is a `Text` column (placeholder for JSONB). Only `sources` uses `ARRAY(Text)`. This differs from the original internal schema where these were array/JSONB types.

**Why affinity is on connection (not separate table):**
Affinity is always needed with connections in queries — separate table means an extra JOIN on every search. The individual signal columns (`affinity_source_count`, `affinity_career_overlap`, etc.) make scores fully regenerable: if we improve the formula or add new signals (e.g., CRM interactions), we recompute `affinity_score` from the stored signals without re-fetching source data. New signal sources just add a new `affinity_*` column.

**Affinity formula (v2):**
```
affinity_score = affinity_career_overlap * 0.40
              + affinity_external_contact * 0.25
              + affinity_embedding_similarity * 0.15
              + affinity_source_count * 0.10
              + affinity_recency * 0.10
```

**Affinity signal normalization:**
- `affinity_source_count`: `min(len(sources) / 4.0, 1.0)` — caps at 4 sources
- `affinity_recency`: `max(0, 1.0 - (days_since_connection / (365 * 5)))` — linear decay over 5 years
- `affinity_career_overlap`: `min(total_overlap_months * size_factor / 36.0, 1.0)` where `size_factor = 1.0 / log2(employee_count + 2)`
- `affinity_mutual_connections`: `min(mutual_count / 10.0, 1.0)` — caps at 10 mutual connections within same tenant

**Dunbar tier thresholds (per user):**
- `inner_circle`: top 15 by affinity_score
- `active`: next 35 (ranks 16-50)
- `familiar`: next 100 (ranks 51-150)
- `acquaintance`: rest with affinity_score > 0

**Indexes:**
```sql
CREATE INDEX ix_conn_app_user ON connection(app_user_id);
CREATE INDEX ix_conn_tenant ON connection(tenant_id);
CREATE INDEX ix_conn_bu ON connection(bu_id);
CREATE INDEX ix_conn_app_user_profile ON connection(app_user_id, crawled_profile_id);
CREATE INDEX ix_conn_app_user_affinity ON connection(app_user_id, affinity_score DESC NULLS LAST);
CREATE INDEX ix_conn_tenant_affinity ON connection(tenant_id, affinity_score DESC NULLS LAST);
CREATE INDEX ix_conn_dunbar ON connection(app_user_id, dunbar_tier);
CREATE INDEX ix_conn_crawled_profile ON connection(crawled_profile_id);
CREATE INDEX idx_connection_user_profile ON connection(app_user_id, crawled_profile_id);  -- RLS composite
```

**RLS (defense-in-depth):**
```sql
ALTER TABLE connection ENABLE ROW LEVEL SECURITY;
ALTER TABLE connection FORCE ROW LEVEL SECURITY;

-- Read policy: users can only see their own connections
CREATE POLICY app_user_isolation ON connection FOR SELECT
    USING (app_user_id = NULLIF(current_setting('app.current_user_id', TRUE), ''));

-- Write policy: users can only write their own connections
CREATE POLICY app_user_write ON connection FOR ALL
    USING (true)
    WITH CHECK (app_user_id = NULLIF(current_setting('app.current_user_id', TRUE), ''));
```

### contact_source

Raw import records. Preserves original data from each import source before dedup. One row per person per source per import.

```sql
CREATE TABLE contact_source (
    -- id, audit fields inherited from BaseEntity (prefix: 'cs')
    -- tenant_id, bu_id inherited from TenantBuMixin
    app_user_id           TEXT NOT NULL REFERENCES app_user(id),
    import_job_id         TEXT NOT NULL REFERENCES import_job(id),

    -- Source identification
    source_type           TEXT NOT NULL,            -- 'linkedin_csv', 'google_contacts', 'icloud', 'office'
    source_file_name      TEXT,                     -- original uploaded file name

    -- Parsed contact data (standardized across all converters)
    first_name            TEXT,
    last_name             TEXT,
    full_name             TEXT,
    email                 TEXT,
    phone                 TEXT,
    company               TEXT,
    title                 TEXT,
    linkedin_url          TEXT,                     -- normalized, if available
    connected_at          DATE,                     -- LinkedIn connection date, if available

    -- Raw original record (lossless)
    raw_record            JSONB,                    -- uses JSONB directly (auto-compiled to JSON for SQLite)

    -- Dedup outcome
    connection_id         TEXT REFERENCES connection(id),  -- which golden record this mapped to (NULL if pending)
    dedup_status          TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'matched', 'ambiguous', 'new'
    dedup_method          TEXT,                     -- 'exact_url', 'exact_email', 'fuzzy_name', 'manual'
    dedup_confidence      FLOAT,                   -- 0.0-1.0

    -- Import origin label for external contact signal
    source_label          VARCHAR(50)              -- 'google_personal', 'google_work', 'icloud', 'office365'
);
```

**Indexes:**
```sql
CREATE INDEX ix_cs_app_user ON contact_source(app_user_id);
CREATE INDEX ix_cs_import_job ON contact_source(import_job_id);
CREATE INDEX ix_cs_connection ON contact_source(connection_id);
CREATE INDEX ix_cs_linkedin_url ON contact_source(linkedin_url) WHERE linkedin_url IS NOT NULL;
CREATE INDEX ix_cs_email ON contact_source(email) WHERE email IS NOT NULL;
CREATE INDEX ix_cs_dedup_status ON contact_source(dedup_status) WHERE dedup_status = 'pending';
```

### import_job

Tracks upload/import progress per user.

```sql
CREATE TABLE import_job (
    -- id, audit fields inherited from BaseEntity (prefix: 'ij')
    -- tenant_id, bu_id inherited from TenantBuMixin
    app_user_id       TEXT NOT NULL REFERENCES app_user(id),

    source_type       TEXT NOT NULL,                -- 'linkedin_csv', 'google_contacts', 'icloud', 'office'
    file_name         TEXT,
    file_size_bytes   INTEGER,

    status            TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'parsing', 'deduping', 'enriching', 'completed', 'failed'
    total_records     INTEGER NOT NULL DEFAULT 0,
    parsed_count      INTEGER NOT NULL DEFAULT 0,
    matched_count     INTEGER NOT NULL DEFAULT 0,   -- linked to existing connections
    new_count         INTEGER NOT NULL DEFAULT 0,   -- new connections created
    failed_count      INTEGER NOT NULL DEFAULT 0,
    enrichment_queued INTEGER NOT NULL DEFAULT 0,   -- profiles sent to crawler

    error_message     TEXT,
    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ
);
```

**Indexes:**
```sql
CREATE INDEX ix_ij_app_user ON import_job(app_user_id);
CREATE INDEX ix_ij_status ON import_job(status);
```

### enrichment_event

Cost tracking for profile enrichment per user.

```sql
CREATE TABLE enrichment_event (
    -- id, audit fields inherited from BaseEntity (prefix: 'ee')
    -- tenant_id, bu_id inherited from TenantBuMixin
    app_user_id        TEXT NOT NULL REFERENCES app_user(id),
    crawled_profile_id TEXT NOT NULL REFERENCES crawled_profile(id),

    event_type         TEXT NOT NULL,                -- 'crawled', 'cache_hit', 'failed', 'retry'
    enrichment_mode    TEXT NOT NULL,                -- 'platform', 'byok'
    crawler_name       TEXT,                         -- 'apify', 'netrows', etc.
    cost_estimate_usd  FLOAT NOT NULL DEFAULT 0,
    crawler_run_id     TEXT                          -- external run ID for traceability
);
```

**Indexes:**
```sql
CREATE INDEX ix_ee_app_user ON enrichment_event(app_user_id);
CREATE INDEX ix_ee_tenant ON enrichment_event(tenant_id);
CREATE INDEX ix_ee_profile ON enrichment_event(crawled_profile_id);
CREATE INDEX ix_ee_type ON enrichment_event(event_type);
```

### search_session

Conversational search sessions per user. Replaces the simpler `search_history` from the original spec with a multi-turn conversation model.

```sql
CREATE TABLE search_session (
    -- id, audit fields inherited from BaseEntity (prefix: 'ss')
    -- tenant_id, bu_id inherited from TenantBuMixin
    app_user_id       TEXT NOT NULL REFERENCES app_user(id),

    initial_query     TEXT NOT NULL,                -- first search query that started the session
    turn_count        INTEGER NOT NULL DEFAULT 1,   -- number of conversation turns
    last_active_at    TIMESTAMPTZ NOT NULL,          -- last activity timestamp
    is_saved          BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE = named saved session
    saved_name        TEXT                           -- name for saved sessions
);
```

**Indexes:**
```sql
CREATE INDEX ix_ss_app_user_latest ON search_session(app_user_id, last_active_at);
CREATE INDEX ix_ss_app_user_saved ON search_session(app_user_id, is_saved);
CREATE INDEX ix_ss_tenant ON search_session(tenant_id);
```

### search_turn

Individual conversation turns within a search session. Stores the full LLM transcript and structured results per turn.

```sql
CREATE TABLE search_turn (
    -- id, audit fields inherited from BaseEntity (prefix: 'sturn')
    -- tenant_id, bu_id inherited from TenantBuMixin
    session_id        TEXT NOT NULL REFERENCES search_session(id),
    turn_number       INTEGER NOT NULL,             -- 1-indexed turn number within session
    user_query        TEXT NOT NULL,                -- user query for this turn
    transcript        JSONB,                        -- full LLM messages array including tool calls/results
    results           JSONB,                        -- structured result set (profiles, scores, etc.)
    summary           TEXT                          -- LLM-generated summary, lazily populated
);
```

**Indexes:**
```sql
CREATE INDEX ix_sturn_session_turn ON search_turn(session_id, turn_number);
```

### search_tag

Profile tags created during search sessions. Allows users to tag profiles discovered during search for later retrieval.

```sql
CREATE TABLE search_tag (
    -- id, audit fields inherited from BaseEntity (prefix: 'stag')
    -- tenant_id, bu_id inherited from TenantBuMixin
    app_user_id        TEXT NOT NULL REFERENCES app_user(id),
    session_id         TEXT NOT NULL REFERENCES search_session(id),
    crawled_profile_id TEXT NOT NULL REFERENCES crawled_profile(id),
    tag_name           TEXT NOT NULL
);
```

**Indexes:**
```sql
CREATE INDEX ix_stag_app_user_tag ON search_tag(app_user_id, tag_name);
CREATE INDEX ix_stag_app_user_profile ON search_tag(app_user_id, crawled_profile_id);
CREATE INDEX ix_stag_session ON search_tag(session_id);
CREATE INDEX ix_stag_tenant ON search_tag(tenant_id);
```

---

## Funding / Startup Pipeline Tables

Shared tables (no tenant/BU scoping) for tracking startup funding and growth signals.

### funding_round

Funding round data per company.

```sql
CREATE TABLE funding_round (
    -- id, audit fields inherited from BaseEntity (prefix: 'fr')
    company_id        TEXT NOT NULL,                -- FK to company.id (no FK constraint in migration)
    round_type        VARCHAR(50) NOT NULL,         -- 'Seed', 'Series A', 'Series B', etc.
    announced_on      DATE,                         -- date the round was announced
    amount_usd        BIGINT,                       -- round amount in whole USD
    lead_investors    TEXT[],                        -- lead investor names
    all_investors     TEXT[],                        -- all investor names
    source_url        VARCHAR(500),                 -- URL of source article
    confidence        SMALLINT NOT NULL DEFAULT 5,  -- confidence score 1-10

    UNIQUE (company_id, round_type, amount_usd)
);
```

**Indexes:**
```sql
CREATE INDEX ix_fr_company ON funding_round(company_id);
CREATE INDEX ix_fr_announced ON funding_round(announced_on);
CREATE INDEX ix_fr_round_type ON funding_round(round_type);
```

### growth_signal

Revenue, headcount, and other metric signals per company.

```sql
CREATE TABLE growth_signal (
    -- id, audit fields inherited from BaseEntity (prefix: 'gs')
    company_id        TEXT NOT NULL,                -- FK to company.id (no FK constraint in migration)
    signal_type       VARCHAR(50) NOT NULL,         -- 'arr', 'mrr', 'revenue', 'headcount', etc.
    signal_date       DATE NOT NULL,                -- date signal was observed
    value_numeric     BIGINT,                       -- numeric value (USD, count)
    value_text        TEXT,                         -- human-readable description
    source_url        VARCHAR(500),                 -- URL where signal was found
    confidence        SMALLINT NOT NULL DEFAULT 5,  -- confidence score 1-10

    UNIQUE (company_id, signal_type, signal_date, source)  -- source from BaseEntity
);
```

**Indexes:**
```sql
CREATE INDEX ix_gs_company_date ON growth_signal(company_id, signal_date);
CREATE INDEX ix_gs_signal_type ON growth_signal(signal_type);
```

### startup_tracking

Per-company pipeline metadata. 1:1 with company. Tracks whether a company is being watched and denormalized funding/ARR data.

```sql
CREATE TABLE startup_tracking (
    -- id, audit fields inherited from BaseEntity (prefix: 'st')
    company_id         TEXT NOT NULL UNIQUE,         -- 1:1 FK to company.id
    watching           BOOLEAN NOT NULL DEFAULT FALSE, -- pipeline filter flag
    description        TEXT,                         -- startup description
    vertical           VARCHAR(100),                 -- 'AI Agents', 'Voice AI', 'Dev Tools', etc.
    sub_category       VARCHAR(100),                 -- finer classification
    funding_stage      VARCHAR(50),                  -- denormalized from funding_round
    total_raised_usd   BIGINT,                       -- denormalized sum
    last_funding_date  DATE,                         -- denormalized latest
    round_count        INTEGER NOT NULL DEFAULT 0,   -- denormalized count
    estimated_arr_usd  BIGINT,                       -- revenue estimate
    arr_signal_date    DATE,                         -- when ARR was estimated
    arr_confidence     SMALLINT                      -- confidence 1-10
);
```

**Indexes:**
```sql
CREATE UNIQUE INDEX ix_st_company ON startup_tracking(company_id);
CREATE INDEX ix_st_watching ON startup_tracking(watching) WHERE watching = true;
CREATE INDEX ix_st_vertical ON startup_tracking(vertical);
```

---

## Infrastructure Tables

### agent_run

Tracks async agent executions with LLM metrics for cost and performance analysis. Scoped via TenantBuMixin.

```sql
CREATE TABLE agent_run (
    -- id, audit fields inherited from BaseEntity (prefix: 'arn')
    -- id uses timestamped nanoid: Nanoid.make_timestamped_id('arn')
    -- tenant_id, bu_id inherited from TenantBuMixin
    agent_type        VARCHAR(100) NOT NULL,        -- type of agent (e.g., 'TASK_SUMMARIZER')
    status            VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
    started_at        TIMESTAMPTZ,                  -- when the agent started executing
    completed_at      TIMESTAMPTZ,                  -- when the agent finished executing
    error_message     TEXT,                         -- error message if the run failed
    input_params      JSONB,                        -- JSON input parameters for the agent run
    output            JSONB,                        -- JSON output from the agent run

    -- LLM tracking fields
    llm_input         JSONB,                        -- the processed input sent to the LLM
    llm_output        JSONB,                        -- the structured response from the LLM
    llm_cost_usd      FLOAT,                       -- cost of the LLM call in USD
    llm_latency_ms    INTEGER,                     -- time taken for the LLM call in milliseconds
    llm_metadata      JSONB                        -- model name, token counts, provider info
);
```

---

## Contact Source Converters

All contact imports are CSV/file uploads. No OAuth. Each source has a converter that maps source-specific columns to the standardized `contact_source` schema.

### Converter Interface

```python
class ContactConverter(ABC):
    source_type: str  # e.g., 'linkedin_csv'

    @abstractmethod
    def parse(self, file_content: bytes) -> list[ParsedContact]:
        """Parse uploaded file into standardized contacts."""
        pass

@dataclass
class ParsedContact:
    first_name: str | None
    last_name: str | None
    full_name: str | None
    email: str | None
    phone: str | None
    company: str | None
    title: str | None
    linkedin_url: str | None       # normalized
    connected_at: date | None
    raw_record: dict               # original row/record
```

### Converter Implementations

| Converter | Source Format | Key Fields Extracted | Notes |
|-----------|-------------|---------------------|-------|
| `LinkedInCsvConverter` | LinkedIn Connections CSV export | first_name, last_name, company, title, connected_at, linkedin_url | Primary source. URL is dedup key. |
| `GoogleContactsConverter` | Google Contacts CSV export | first_name, last_name, email, phone, company, title | Spike: need sample to confirm columns. |
| `ICloudConverter` | vCard (.vcf) export | first_name, last_name, email, phone, company, title | Spike: need sample to confirm vCard version. |
| `OfficeContactsConverter` | Outlook CSV export | first_name, last_name, email, phone, company, title, department | Spike: need sample to confirm columns. |

### Dedup Pipeline (contact_source -> connection)

After a converter produces `ParsedContact` records:

1. **Exact URL match** — if `linkedin_url` matches an existing `crawled_profile.linkedin_url`, link directly. Confidence: 1.0.
2. **Exact email match** — if `email` matches an existing `connection.emails` for this user, merge sources. Confidence: 1.0.
3. **Fuzzy name+company match** — RapidFuzz `token_sort_ratio` on `full_name` + `company` against existing connections. Threshold: 0.85. Confidence: 0.85-0.99.
4. **No match** — create new connection (with `crawled_profile_id` if LinkedIn URL found in shared profiles, or NULL pending enrichment). Dedup status: `new`.
5. **Ambiguous** — multiple fuzzy matches above threshold. Flag for manual review. Dedup status: `ambiguous`.

---

## Row-Level Security (RLS)

RLS is applied as defense-in-depth on the connection table and all profile-linked shared tables. The session variable `app.current_user_id` controls visibility.

### Connection Table (direct policy)

Users can only see/write connections where `app_user_id` matches the session variable.

### Profile-Linked Tables (EXISTS subquery policy)

The tables `crawled_profile`, `experience`, `education`, and `profile_skill` use an EXISTS subquery policy that checks whether the profile is linked to the current user via the `connection` table:

```sql
-- Applied to: crawled_profile, experience, education, profile_skill
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;

-- Read policy: visible only if the profile is connected to the current user
CREATE POLICY user_profiles ON <table> FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM connection
        WHERE connection.crawled_profile_id = <table>.<fk_col>
        AND connection.app_user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')
    ));

-- Write policy: allows all writes (no user check)
CREATE POLICY user_profiles_write ON <table> FOR ALL
    USING (true)
    WITH CHECK (true);
```

Where `<fk_col>` is `id` for `crawled_profile` and `crawled_profile_id` for the child tables.

---

## Relationship Diagram

```
                     SHARED (no tenant_id, no bu_id)
                +------------------------------+
                |                              |
                |   crawled_profile <-------+  |
                |     |                     |  |
                |     +-> experience         |  |
                |     +-> education          |  |
                |     +-> profile_skill      |  |
                |                           |  |
                |   company <-- company_alias |  |
                |     ^                        |
                |     | (FK from experience,    |
                |     |  crawled_profile)       |
                |                              |
                |   role_alias (standalone)     |
                +------------------------------+

                FUNDING / STARTUP PIPELINE (shared)
                +------------------------------+
                |                              |
                |   funding_round              |
                |   growth_signal              |
                |   startup_tracking           |
                |     (all FK -> company.id)    |
                |                              |
                +------------------------------+

                ORGANIZATION (system-level)
                +------------------------------+
                |                              |
                |   tenant                     |
                |     |                        |
                |     +-> bu                   |
                |                              |
                |   app_user (system-wide)     |
                |     |                        |
                |     +-> enrichment_config    |
                |     +-> app_user_tenant_role |
                |                              |
                +------------------------------+

      SCOPED (TenantBuMixin: tenant_id + bu_id + app_user_id FK)
                +------------------------------+
                |                              |
                |   connection ----------------+---> crawled_profile (FK)
                |     ^                        |
                |     |                        |
                |   contact_source             |
                |                              |
                |   import_job                 |
                |   enrichment_event ----------+---> crawled_profile (FK)
                |                              |
                |   search_session             |
                |     |                        |
                |     +-> search_turn          |
                |     +-> search_tag ----------+---> crawled_profile (FK)
                |                              |
                +------------------------------+

      INFRASTRUCTURE (TenantBuMixin)
                +------------------------------+
                |                              |
                |   agent_run                  |
                |                              |
                +------------------------------+
```

---

## Query Patterns

Users query in natural language — the LLM translates to SQL/vector queries. These patterns show the generated SQL. If the query engine can't handle a user's NL query, it should surface an error (not silently return nothing) so we can improve the engine.

### User-scoped search (default — my connections)

```sql
SELECT cp.*, c.affinity_score, c.dunbar_tier, c.sources
FROM crawled_profile cp
JOIN connection c ON c.crawled_profile_id = cp.id
WHERE c.app_user_id = :app_user_id
  AND c.is_active = TRUE
ORDER BY c.affinity_score DESC NULLS LAST;
```

### Team-scoped search (Phase 5 — tenant's combined network)

```sql
SELECT cp.*, c.affinity_score, c.dunbar_tier, c.sources
FROM crawled_profile cp
JOIN connection c ON c.crawled_profile_id = cp.id
WHERE c.tenant_id = :tenant_id
  AND c.is_active = TRUE
ORDER BY c.affinity_score DESC NULLS LAST;
```

### Vector search (user-scoped)

```sql
SELECT cp.*, c.affinity_score, c.dunbar_tier,
       1 - (cp.embedding_openai <=> :query_embedding) AS similarity
FROM crawled_profile cp
JOIN connection c ON c.crawled_profile_id = cp.id
WHERE c.app_user_id = :app_user_id
  AND c.is_active = TRUE
  AND 1 - (cp.embedding_openai <=> :query_embedding) > 0.7
ORDER BY cp.embedding_openai <=> :query_embedding
LIMIT 10;
```

### People Like X (user-scoped)

```sql
SELECT cp.*, c.affinity_score,
       1 - (cp.embedding_openai <=> :target_embedding) AS similarity
FROM crawled_profile cp
JOIN connection c ON c.crawled_profile_id = cp.id
WHERE c.app_user_id = :app_user_id
  AND cp.id != :target_profile_id
  AND c.is_active = TRUE
ORDER BY cp.embedding_openai <=> :target_embedding
LIMIT 10;
```

### Cost tracking summary (per user)

```sql
SELECT
    enrichment_mode,
    event_type,
    COUNT(*) AS event_count,
    SUM(cost_estimate_usd) AS total_cost,
    COUNT(*) FILTER (WHERE event_type = 'cache_hit') AS cache_hits
FROM enrichment_event
WHERE app_user_id = :app_user_id
GROUP BY enrichment_mode, event_type;
```

---

## Decisions

### Tenant->BU->AppUser hierarchy — 2026-03-26
**Chose:** TenantBuMixin (tenant_id + bu_id) for structural scoping, app_user_id FK for ownership on all scoped tables
**Over:** TenantUserMixin with user_id as both scope and owner
**Because:** Aligns with codebase patterns. Tenant+BU is the structural scope (future-proof for multi-BU orgs). AppUser is the real user identity (system-level, not scoped). Separation keeps the scoping mixin generic while ownership is explicit.

### AppUser-level default queries — 2026-03-26
**Chose:** Default queries filter by `app_user_id`
**Over:** Default queries filter by `bu_id` or `tenant_id + bu_id`
**Because:** AppUser is the real user. Day-to-day operations are "my connections, my imports." Tenant+BU scoping is structural. Team sharing (Phase 5) adds tenant-level queries on top — doesn't change the default.

### Enrichment config as separate table — 2026-03-26
**Chose:** `enrichment_config` table with app_user_id FK
**Over:** Enrichment fields on tenant table or app_user table
**Because:** AppUser is a system-level entity — LinkedOut-specific config shouldn't pollute it. Separate table keeps concerns clean and is easy to re-scope to tenant-level if org billing becomes the model later.

### Affinity embedded on connection vs separate table — 2026-03-23
**Chose:** Embed affinity columns directly on `connection` with individual signal columns
**Over:** Separate `affinity_scores` table (linkedin_intel pattern)
**Because:** One fewer JOIN in every search query. Individual signals stored for transparency, "Why This Person" explanations, and idempotent recomputation when the algorithm improves or new signal sources (CRM, etc.) are added.

### Singular table names — 2026-03-23
**Chose:** Singular names (`connection`, `experience`, `company`) matching codebase entity convention
**Over:** Plural names (`connections`, `experiences`, `companies`)
**Because:** Codebase uses singular because table names are modeled directly after entity class names. `ConnectionEntity` -> table `connection`.

### CSV upload for all contact sources (no OAuth) — 2026-03-23
**Chose:** File upload with per-source converters
**Over:** OAuth integration (Google People API, Microsoft Graph, etc.)
**Because:** Dramatically simpler. No Google verification (2-6 weeks). No API rate limits. User exports contacts themselves.

### Store all search history (no limit) — 2026-03-23
**Chose:** Store every search session, paginate in UI
**Over:** Cap at 20 recent searches
**Because:** Storage is cheap. Full history enables usage analytics, search pattern learning, and user can scroll back further.

### Conversational search sessions — 2026-04-09
**Chose:** `search_session` + `search_turn` multi-turn model
**Over:** Flat `search_history` table (one row per query)
**Because:** OSS search supports multi-turn conversations where the LLM refines results. A session groups related turns together, and each turn stores the full transcript and structured results. Tags link profiles to the session where they were discovered.

### Dual embedding columns — 2026-04-09
**Chose:** Two embedding columns (`embedding_openai` 1536-dim, `embedding_nomic` 768-dim) with metadata
**Over:** Single `embedding` column (1536-dim only)
**Because:** OSS supports multiple embedding providers. `embedding_model` and `embedding_dim` track which model generated the active embedding. HNSW indexes are created for both columns.

### data_source as crawler provenance — 2026-03-23
**Chose:** Use existing `data_source` column for both enrichment status and crawler identity (`'apify'`, `'netrows'`, `'csv_only'`)
**Over:** Adding a separate `crawler_name` column
**Because:** `data_source` already tracks provenance. `has_enriched_data` boolean independently answers "is it enriched?". No need for two columns.

---

## Not Included

- Chrome extension data flow (Phase 2 product — separate spec)
- ATS integration schema (Phase 3 product — separate spec)
- Payment/billing tables (post-beta — no billing in v1)
- Search result caching (premature optimization — add if needed)
- Full-text search index tuning (tsvector config — operational concern, not schema)
- CRM interaction signals on affinity (future — add `affinity_crm_interactions` column when needed)
- Soft delete implementation details (BaseEntity provides `deleted_at` — business rules for soft delete are service-layer concerns)
- Best hop / path-finding tables (not yet implemented)
