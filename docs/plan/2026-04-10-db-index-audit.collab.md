# Database Index Audit & Optimization Plan

## Context
A search query using `ILIKE '%engineer%'` and `ILIKE '%san francisco%'` on `crawled_profile` revealed that despite `pg_trgm` being enabled (migration `489c03d99a7d`), **zero trigram GIN indexes exist**. Every `ILIKE '%pattern%'` query does a sequential scan. This triggered a full audit of all tables, indexes, and query patterns.

**Scale:** ~22.5K connections, ~22.5K crawled profiles, ~150K experiences, ~62K role aliases.

---

## Executive Summary

| Metric | Count |
|--------|-------|
| Total tables | 22+ |
| Total existing indexes | ~55 |
| Missing trigram GIN indexes | 12 columns |
| Missing FK indexes | 8 |
| Indexes needing sort-direction fix | 2 |
| Missing standalone join indexes | 1 |

**Extensions available:** `pg_trgm` (enabled), `pgvector` (enabled, HNSW index exists on `crawled_profile.embedding`).

---

## Table-by-Table Inventory

### 1. crawled_profile (CRITICAL — most queried table)

**Scoping:** shared (no tenant/BU)
**Entity:** `src/linkedout/crawled_profile/entities/crawled_profile_entity.py`
**Est. rows:** ~22.5K

#### Current Indexes
| Index | Columns | Type | Unique |
|-------|---------|------|--------|
| `ix_cp_linkedin_url` | `linkedin_url` | btree | yes |
| `ix_cp_company_id` | `company_id` | btree | no |
| `ix_cp_current_company` | `current_company_name` | btree | no |
| `ix_cp_location` | `location_city, location_country_code` | btree composite | no |
| `ix_cp_seniority` | `seniority_level` | btree | no |
| `ix_cp_function` | `function_area` | btree | no |
| `ix_cp_has_enriched` | `has_enriched_data` | btree | no |
| `ix_cp_embedding_hnsw` | `embedding` | HNSW (vector_cosine_ops) | no |

#### Gaps
1. **No trigram GIN indexes** — `full_name`, `current_company_name`, `headline`, `current_position`, `location_city`, `location_raw` are all queried with `ILIKE '%pattern%'`. Btree indexes cannot help with leading-wildcard patterns.
2. **Missing FK index on `source_app_user_id`** — FK to `app_user.id`, no index.
3. **`ix_cp_current_company` is btree** — useless for ILIKE; needs trigram GIN replacement or addition.
4. **`ix_cp_location` is btree composite** — useless for `ILIKE '%san francisco%'` on `location_city`.

#### Query Sources
- `intro_tool.py:40` — `cp.current_company_name ILIKE :pattern`
- `search_controller.py` — LLM-generated SQL with ILIKE on headline, current_position, location_city, location_raw
- `crawled_profile_repository.py:49,51` — ORM ILIKE on full_name, current_company_name
- `dashboard/repository.py:45,57,73,89` — GROUP BY on function_area, seniority_level, location_city, current_company_name
- `network_tool.py:28-85` — GROUP BY current_company_name, seniority_level
- `vector_tool.py:22` — ORDER BY embedding <=> (covered by HNSW)
- `schema_context.py` — exposes all columns to LLM, so any column can appear in generated SQL

#### Recommendations
```sql
-- P0: Trigram GIN indexes for ILIKE queries
CREATE INDEX CONCURRENTLY ix_cp_full_name_trgm ON crawled_profile USING gin (full_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_current_company_trgm ON crawled_profile USING gin (current_company_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_headline_trgm ON crawled_profile USING gin (headline gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_current_position_trgm ON crawled_profile USING gin (current_position gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_location_city_trgm ON crawled_profile USING gin (location_city gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_location_raw_trgm ON crawled_profile USING gin (location_raw gin_trgm_ops);

-- P1: Missing FK index
CREATE INDEX CONCURRENTLY ix_cp_source_app_user ON crawled_profile (source_app_user_id);
```

---

### 2. connection (CRITICAL — every search JOINs through this)

**Scoping:** TenantBuMixin (tenant_id, bu_id)
**Entity:** `src/linkedout/connection/entities/connection_entity.py`
**Est. rows:** ~22.5K

#### Current Indexes
| Index | Columns | Type | Unique |
|-------|---------|------|--------|
| `uq_conn_app_user_profile` | `app_user_id, crawled_profile_id` | unique constraint | yes |
| `ix_conn_app_user` | `app_user_id` | btree | no |
| `ix_conn_tenant` | `tenant_id` | btree | no |
| `ix_conn_bu` | `bu_id` | btree | no |
| `ix_conn_app_user_profile` | `app_user_id, crawled_profile_id` | btree composite | no |
| `ix_conn_app_user_affinity` | `app_user_id, affinity_score` | btree composite | no |
| `ix_conn_tenant_affinity` | `tenant_id, affinity_score` | btree composite | no |
| `ix_conn_dunbar` | `app_user_id, dunbar_tier` | btree composite | no |

#### Gaps
1. **No standalone `crawled_profile_id` index** — every tool JOIN pattern is `JOIN connection c ON c.crawled_profile_id = cp.id`. The composite `ix_conn_app_user_profile` has `app_user_id` first, so Postgres can't use it efficiently when filtering only on `crawled_profile_id`.
2. **Affinity indexes lack sort direction** — entity comment on line 51-52 says "Add DESC NULLS LAST in the Alembic migration for PostgreSQL" but this was never done. Queries use `ORDER BY c.affinity_score DESC NULLS LAST` (intro_tool.py:45,77; search_controller.py:145).

#### Query Sources
- `vector_tool.py:16` — `JOIN connection c ON c.crawled_profile_id = cp.id`
- `profile_tool.py:42-58` — `WHERE c.id = :conn_id` (PK, fine)
- `intro_tool.py:45,77` — `ORDER BY c.affinity_score DESC NULLS LAST`
- `search_controller.py:145` — same affinity sort
- `network_tool.py` — GROUP BY on dunbar_tier
- `connection_repository.py` — FilterSpec on app_user_id, crawled_profile_id, dunbar_tier, affinity_score range
- RLS policy subquery — `WHERE app_user_id = current_setting('app.current_user_id')` (covered by `ix_conn_app_user`)

#### Recommendations
```sql
-- P0: Standalone FK index for JOINs
CREATE INDEX CONCURRENTLY ix_conn_crawled_profile ON connection (crawled_profile_id);

-- P1: Replace affinity indexes with proper sort direction
DROP INDEX CONCURRENTLY ix_conn_app_user_affinity;
CREATE INDEX CONCURRENTLY ix_conn_app_user_affinity ON connection (app_user_id, affinity_score DESC NULLS LAST);

DROP INDEX CONCURRENTLY ix_conn_tenant_affinity;
CREATE INDEX CONCURRENTLY ix_conn_tenant_affinity ON connection (tenant_id, affinity_score DESC NULLS LAST);
```

---

### 3. experience

**Scoping:** shared
**Entity:** `src/linkedout/experience/entities/experience_entity.py`
**Est. rows:** ~150K

#### Current Indexes
| Index | Columns | Type |
|-------|---------|------|
| `ix_exp_profile` | `crawled_profile_id` | btree |
| `ix_exp_company` | `company_id` | btree |
| `ix_exp_current` | `is_current` | btree |
| `ix_exp_dates` | `start_date, end_date` | btree composite |

#### Gaps
1. **No trigram GIN on `company_name`** — `intro_tool.py:71` uses `ILIKE` on `e.company_name`.
2. **Missing composite for alumni query** — `search_controller.py` self-joins experience on `company_id` for warm intro paths. A composite `(company_id, crawled_profile_id)` would help.
3. **Timeline query needs composite** — `profile_tool.py:108` uses `ORDER BY e.start_date DESC NULLS FIRST` filtered by `crawled_profile_id`.

#### Query Sources
- `profile_tool.py:101-111` — `WHERE e.crawled_profile_id = :id ORDER BY e.start_date DESC NULLS FIRST`
- `career_tool.py:41-54` — `WHERE e.crawled_profile_id IN (...) ORDER BY crawled_profile_id, start_date ASC`
- `intro_tool.py:63-79` — `JOIN experience` filtered by company
- `search_controller.py:136-147` — self-join `e1.company_id = e2.company_id`
- `affinity_scorer.py:159-200` — `WHERE crawled_profile_id = ... AND company_id IS NOT NULL`

#### Recommendations
```sql
-- P1: Trigram GIN for company name ILIKE
CREATE INDEX CONCURRENTLY ix_exp_company_name_trgm ON experience USING gin (company_name gin_trgm_ops);

-- P1: Composite for timeline queries
CREATE INDEX CONCURRENTLY ix_exp_profile_start ON experience (crawled_profile_id, start_date DESC NULLS FIRST);

-- P2: Composite for alumni/warm-intro self-join
CREATE INDEX CONCURRENTLY ix_exp_company_profile ON experience (company_id, crawled_profile_id);
```

---

### 4. education

**Scoping:** shared
**Entity:** `src/linkedout/education/entities/education_entity.py`
**Est. rows:** ~40K

#### Current Indexes
| Index | Columns | Type |
|-------|---------|------|
| `ix_edu_profile` | `crawled_profile_id` | btree |
| `ix_edu_school` | `school_name` | btree |

#### Gaps
1. **No trigram GIN on `school_name`, `degree`** — both queried with ILIKE in `education_repository.py:45,47`.

#### Recommendations
```sql
-- P1
CREATE INDEX CONCURRENTLY ix_edu_school_trgm ON education USING gin (school_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_edu_degree_trgm ON education USING gin (degree gin_trgm_ops);
```

---

### 5. company

**Scoping:** shared (no RLS)
**Entity:** `src/linkedout/company/entities/company_entity.py`

#### Current Indexes
| Index | Columns | Type | Unique |
|-------|---------|------|--------|
| `ix_co_canonical` | `canonical_name` | btree | yes |
| `ix_co_domain` | `domain` | btree | no |
| `ix_co_industry` | `industry` | btree | no |
| `ix_co_size_tier` | `size_tier` | btree | no |

#### Gaps
1. **No trigram GIN on `canonical_name`, `domain`** — `company_repository.py:47,49` and `company_tool.py:43` use ILIKE.
2. **Missing `parent_company_id` FK index** — self-referential FK, no index.
3. **Missing `hq_country` index** — filtered in `company_repository.py:55`.

#### Recommendations
```sql
-- P0
CREATE INDEX CONCURRENTLY ix_co_canonical_trgm ON company USING gin (canonical_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_co_domain_trgm ON company USING gin (domain gin_trgm_ops);

-- P2
CREATE INDEX CONCURRENTLY ix_co_parent ON company (parent_company_id);
CREATE INDEX CONCURRENTLY ix_co_hq_country ON company (hq_country);
```

---

### 6. company_alias

**Entity:** `src/linkedout/company_alias/entities/company_alias_entity.py`

#### Current Indexes
| Index | Columns | Type |
|-------|---------|------|
| `ix_ca_alias_name` | `alias_name` | btree |
| `ix_ca_company_id` | `company_id` | btree |
| `uq_ca_alias_company` | `alias_name, company_id` | unique |

#### Gaps
- **No trigram GIN on `alias_name`** — `company_alias_repository.py:44` uses ILIKE.

#### Recommendations
```sql
-- P1
CREATE INDEX CONCURRENTLY ix_ca_alias_trgm ON company_alias USING gin (alias_name gin_trgm_ops);
```

---

### 7. profile_skill

**Entity:** `src/linkedout/profile_skill/entities/profile_skill_entity.py`

#### Current Indexes
| Index | Columns | Type |
|-------|---------|------|
| `ix_psk_profile` | `crawled_profile_id` | btree |
| `ix_psk_skill` | `skill_name` | btree |
| `uq_psk_profile_skill` | `crawled_profile_id, skill_name` | unique |

#### Gaps
- **No trigram GIN on `skill_name`** — `profile_skill_repository.py:44` uses ILIKE.

#### Recommendations
```sql
-- P1
CREATE INDEX CONCURRENTLY ix_psk_skill_trgm ON profile_skill USING gin (skill_name gin_trgm_ops);
```

---

### 8. role_alias

**Entity:** `src/linkedout/role_alias/entities/role_alias_entity.py`

#### Current Indexes
| Index | Columns | Type | Unique |
|-------|---------|------|--------|
| `ix_ra_alias_title` | `alias_title` | btree | yes |
| `ix_ra_canonical_title` | `canonical_title` | btree | no |
| `ix_ra_seniority_level` | `seniority_level` | btree | no |
| `ix_ra_function_area` | `function_area` | btree | no |

#### Gaps
- **No trigram GIN on `alias_title`, `canonical_title`** — `role_alias_repository.py` uses ILIKE on both.

#### Recommendations
```sql
-- P1
CREATE INDEX CONCURRENTLY ix_ra_alias_trgm ON role_alias USING gin (alias_title gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_ra_canonical_trgm ON role_alias USING gin (canonical_title gin_trgm_ops);
```

---

### 9. contact_source

**Entity:** `src/linkedout/contact_source/entities/contact_source_entity.py`

#### Current Indexes (well-indexed with partial indexes)
| Index | Columns | Type | Notes |
|-------|---------|------|-------|
| `ix_cs_app_user` | `app_user_id` | btree | |
| `ix_cs_import_job` | `import_job_id` | btree | |
| `ix_cs_linkedin_url` | `linkedin_url` | btree | WHERE linkedin_url IS NOT NULL |
| `ix_cs_email` | `email` | btree | WHERE email IS NOT NULL |
| `ix_cs_dedup_status` | `dedup_status` | btree | WHERE dedup_status = 'pending' |

#### Gaps
- **Missing `connection_id` FK index** — FK to `connection.id`, used in `affinity_scorer.py:159-200`.

#### Recommendations
```sql
-- P1
CREATE INDEX CONCURRENTLY ix_cs_connection ON contact_source (connection_id);
```

---

### 10-12. search_session, search_history, search_tag

All use TenantBuMixin but don't index `tenant_id`/`bu_id`. Session tables have good composite indexes for their primary query patterns.

#### Gaps
- Missing `tenant_id`, `bu_id` indexes on all three (only matters if querying by tenant without app_user_id).

#### Recommendations
```sql
-- P2: Only if tenant-scoped queries are added
CREATE INDEX CONCURRENTLY ix_ss_tenant ON search_session (tenant_id);
CREATE INDEX CONCURRENTLY ix_sh_tenant ON search_history (tenant_id);
CREATE INDEX CONCURRENTLY ix_stag_tenant ON search_tag (tenant_id);
```

---

### 13. app_user_tenant_role

**Entity:** `src/organization/entities/app_user_tenant_role_entity.py`

#### Current Indexes: NONE

#### Gaps
- **Missing both FK indexes** — `app_user_id` and `tenant_id` have no indexes. Used in auth lookups.

#### Recommendations
```sql
-- P1
CREATE INDEX CONCURRENTLY ix_autr_app_user ON app_user_tenant_role (app_user_id);
CREATE INDEX CONCURRENTLY ix_autr_tenant ON app_user_tenant_role (tenant_id);
```

---

### 14. app_user

**Entity:** `src/organization/entities/app_user_entity.py`

Has unique constraints on `email` and `auth_provider_id` (implicit unique indexes).

#### Gaps
- **Missing `own_crawled_profile_id` FK index**.

#### Recommendations
```sql
-- P2
CREATE INDEX CONCURRENTLY ix_au_own_profile ON app_user (own_crawled_profile_id);
```

---

### 15-17. funding_round, growth_signal, startup_tracking

**Status: Adequate.** These pipeline tables have appropriate indexes for their query patterns.

---

### 18-22. Pipeline tables (from migration 489c03d99a7d)

`pipeline_state`, `raw_feed_item`, `extracted_company`, `discovery_signal`, `pipeline_failed_item`, `news_article`, `news_company_mention` — indexes created in migration, adequate for current usage.

---

## Prioritized Action Plan

### P0 — First Migration (high-impact, search-blocking)

These fix sequential scans on the most common query patterns.

```sql
-- Prerequisite: pg_trgm already enabled (migration 489c03d99a7d)

-- crawled_profile: 6 trigram GIN indexes
CREATE INDEX CONCURRENTLY ix_cp_full_name_trgm ON crawled_profile USING gin (full_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_current_company_trgm ON crawled_profile USING gin (current_company_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_headline_trgm ON crawled_profile USING gin (headline gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_current_position_trgm ON crawled_profile USING gin (current_position gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_location_city_trgm ON crawled_profile USING gin (location_city gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_cp_location_raw_trgm ON crawled_profile USING gin (location_raw gin_trgm_ops);

-- company: 2 trigram GIN indexes
CREATE INDEX CONCURRENTLY ix_co_canonical_trgm ON company USING gin (canonical_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_co_domain_trgm ON company USING gin (domain gin_trgm_ops);

-- connection: standalone FK for JOIN performance
CREATE INDEX CONCURRENTLY ix_conn_crawled_profile ON connection (crawled_profile_id);
```

**Total: 9 indexes. Expected impact: 10-100x speedup on all ILIKE searches.**

### P1 — Second Migration (important gaps)

```sql
-- Remaining trigram GIN indexes
CREATE INDEX CONCURRENTLY ix_exp_company_name_trgm ON experience USING gin (company_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_edu_school_trgm ON education USING gin (school_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_edu_degree_trgm ON education USING gin (degree gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_psk_skill_trgm ON profile_skill USING gin (skill_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_ca_alias_trgm ON company_alias USING gin (alias_name gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_ra_alias_trgm ON role_alias USING gin (alias_title gin_trgm_ops);
CREATE INDEX CONCURRENTLY ix_ra_canonical_trgm ON role_alias USING gin (canonical_title gin_trgm_ops);

-- Affinity sort direction fix (drop + recreate)
DROP INDEX CONCURRENTLY ix_conn_app_user_affinity;
CREATE INDEX CONCURRENTLY ix_conn_app_user_affinity ON connection (app_user_id, affinity_score DESC NULLS LAST);
DROP INDEX CONCURRENTLY ix_conn_tenant_affinity;
CREATE INDEX CONCURRENTLY ix_conn_tenant_affinity ON connection (tenant_id, affinity_score DESC NULLS LAST);

-- Missing FK indexes
CREATE INDEX CONCURRENTLY ix_cp_source_app_user ON crawled_profile (source_app_user_id);
CREATE INDEX CONCURRENTLY ix_cs_connection ON contact_source (connection_id);
CREATE INDEX CONCURRENTLY ix_autr_app_user ON app_user_tenant_role (app_user_id);
CREATE INDEX CONCURRENTLY ix_autr_tenant ON app_user_tenant_role (tenant_id);

-- Composite for timeline queries
CREATE INDEX CONCURRENTLY ix_exp_profile_start ON experience (crawled_profile_id, start_date DESC NULLS FIRST);
```

**Total: 16 index operations.**

### P2 — Later (nice to have)

```sql
-- TenantBuMixin FK indexes on secondary tables
CREATE INDEX CONCURRENTLY ix_ss_tenant ON search_session (tenant_id);
CREATE INDEX CONCURRENTLY ix_sh_tenant ON search_history (tenant_id);
CREATE INDEX CONCURRENTLY ix_stag_tenant ON search_tag (tenant_id);

-- Composite for alumni/warm-intro self-join
CREATE INDEX CONCURRENTLY ix_exp_company_profile ON experience (company_id, crawled_profile_id);

-- Other missing FKs
CREATE INDEX CONCURRENTLY ix_co_parent ON company (parent_company_id);
CREATE INDEX CONCURRENTLY ix_co_hq_country ON company (hq_country);
CREATE INDEX CONCURRENTLY ix_au_own_profile ON app_user (own_crawled_profile_id);
```

---

## RLS Performance Notes

The RLS policies on `crawled_profile`, `experience`, `education`, `profile_skill` use a subquery:
```sql
USING (crawled_profile_id IN (
  SELECT crawled_profile_id FROM connection
  WHERE app_user_id = current_setting('app.current_user_id')::uuid
))
```

This subquery is covered by `ix_conn_app_user_profile (app_user_id, crawled_profile_id)` — no gap here. The new standalone `ix_conn_crawled_profile` will additionally help the JOIN side of queries that go through RLS.

If connection count per user grows significantly (>50K), consider materializing the profile ID list.

---

## Implementation Notes

- **Use `CREATE INDEX CONCURRENTLY`** — avoids locking tables during index creation. Cannot run inside a transaction, so each index needs its own Alembic migration step or use `op.execute()` outside transaction.
- **Naming convention** — follows existing pattern: `ix_{table_prefix}_{column_hint}` for btree, `ix_{table_prefix}_{column_hint}_trgm` for trigram GIN.
- **SQLite compatibility** — GIN/trigram indexes are PostgreSQL-only. Entity `__table_args__` should NOT include these; they belong in Alembic migrations with PostgreSQL dialect checks.
- **Existing btree indexes on ILIKE columns** (e.g., `ix_cp_current_company`) can be kept — they still help equality and prefix-match queries. The trigram GIN indexes are additive.

## Verification

After applying each migration:
1. `EXPLAIN ANALYZE` the original trigger query to confirm GIN index usage
2. Run `precommit-tests` to ensure no regressions
3. Check `pg_stat_user_indexes` after a day to verify new indexes are being used
