---
feature: database-indexing
module: backend/migrations
linked_files:
  - backend/migrations/versions/001_baseline.py
version: 1
last_verified: "2026-04-09"
---

# Database Indexing Strategy

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Define where indexes live, how they're named, and when each index type is required. The core rule: PostgreSQL-specific indexes (GIN, HNSW) belong in Alembic migrations only — never in entity `__table_args__` — to preserve SQLite compatibility for unit tests.

## Behaviors

### Index Placement

- **Cross-database indexes (btree)**: Defined in the baseline migration via `op.create_index(...)`. These work on both PostgreSQL and SQLite. Verify the index appears in both PostgreSQL and SQLite test databases.

- **PostgreSQL-specific indexes (GIN, HNSW)**: Defined in migrations only, using `op.execute()` with raw SQL. Must NOT appear in entity `__table_args__`. Verify unit tests using SQLite still pass when these indexes exist in migrations.

- **Single baseline migration**: Unlike the internal repo which accumulated indexes across multiple migrations, OSS consolidates all indexes into `001_baseline.py`. New indexes added after baseline should follow the same migration-only pattern in separate migration files.

### Naming Convention

- **Btree indexes**: `ix_{table_prefix}_{column_hint}` — e.g., `ix_cp_linkedin_url`, `ix_conn_app_user`
- **Trigram GIN indexes**: `ix_{table_prefix}_{column_hint}_trgm` — e.g., `ix_cp_full_name_trgm`
- **HNSW vector indexes**: `ix_{table_prefix}_{column_hint}_hnsw` — e.g., `ix_cp_embedding_openai_hnsw`
- **Composite indexes**: `ix_{table_prefix}_{col1}_{col2}` — e.g., `ix_exp_company_profile`

Table prefixes: `cp` = crawled_profile, `conn` = connection, `exp` = experience, `edu` = education, `co` = company, `ca` = company_alias, `ra` = role_alias, `psk` = profile_skill, `cs` = contact_source, `autr` = app_user_tenant_role, `au` = app_user, `ss` = search_session, `stag` = search_tag, `fr` = funding_round, `gs` = growth_signal, `st` = startup_tracking, `ij` = import_job, `ee` = enrichment_event.

### When to Add Indexes

- **ILIKE columns**: Every column queried with `ILIKE '%pattern%'` MUST have a trigram GIN index. Btree indexes cannot help with leading-wildcard patterns. Requires `pg_trgm` extension (enabled in baseline migration).

- **Foreign key columns**: Every FK column SHOULD have a btree index unless the column is already the leading column in a composite index. Missing FK indexes cause sequential scans on JOINs and cascade deletes.

- **Sort columns**: Indexes on columns used in `ORDER BY ... DESC NULLS LAST` should specify the matching sort direction in the index definition. Mismatched sort direction forces PostgreSQL to do an explicit sort step.

- **Composite indexes**: Add when a query filters on one column and sorts/filters on another in the same table. The filter column should be the leading column.

### RLS Interaction

- RLS policies on profile-linked tables (crawled_profile, experience, education, profile_skill) use `EXISTS` with a correlated subquery against the `connection` table. This form lets the planner use GIN/btree indexes to narrow candidate rows first, then do cheap index probes on `connection` to check visibility.

- The `EXISTS` subquery is covered by `ix_conn_app_user_profile (app_user_id, crawled_profile_id)` and `idx_connection_user_profile (app_user_id, crawled_profile_id)` — composite B-tree indexes that satisfy the correlated lookup in a single index probe.

### Current Index Inventory (001_baseline.py)

All indexes are defined in the single baseline migration. Key counts:

| Category | Count | Examples |
|----------|-------|---------|
| Btree (crawled_profile) | 8 | `ix_cp_linkedin_url` (unique), `ix_cp_company_id`, `ix_cp_location` (composite) |
| Btree (company) | 6 | `ix_co_canonical` (unique), `ix_co_domain`, `ix_co_industry` |
| Btree (company_alias) | 2 | `ix_ca_alias_name`, `ix_ca_company_id` |
| Btree (connection) | 9 | `ix_conn_app_user`, `ix_conn_app_user_profile` (composite), affinity sort indexes |
| Btree (experience) | 6 | `ix_exp_profile`, `ix_exp_company`, `ix_exp_company_profile` (composite) |
| Btree (education) | 2 | `ix_edu_profile`, `ix_edu_school` |
| Btree (profile_skill) | 2 | `ix_psk_profile`, `ix_psk_skill` |
| Btree (role_alias) | 4 | `ix_ra_alias_title` (unique), `ix_ra_canonical_title` |
| Btree (import_job) | 2 | `ix_ij_app_user`, `ix_ij_status` |
| Btree (contact_source) | 5 | `ix_cs_app_user`, `ix_cs_linkedin_url`, `ix_cs_email` |
| Btree (enrichment_event) | 4 | `ix_ee_app_user`, `ix_ee_profile`, `ix_ee_type` |
| Btree (search tables) | 6 | `ix_ss_app_user_latest`, `ix_stag_app_user_tag` |
| Btree (app_user/auth) | 3 | `ix_au_own_profile`, `ix_autr_app_user` |
| Btree (funding/startup) | 5 | `ix_fr_company`, `ix_st_company` (unique) |
| Trigram GIN (crawled_profile) | 5 | `ix_cp_full_name_trgm`, `ix_cp_headline_trgm` |
| Trigram GIN (company) | 2 | `ix_co_canonical_trgm`, `ix_co_domain_trgm` |
| Trigram GIN (experience) | 2 | `ix_exp_company_name_trgm`, `ix_exp_position_trgm` |
| Trigram GIN (education) | 2 | `ix_edu_school_trgm`, `ix_edu_degree_trgm` |
| Trigram GIN (profile_skill) | 1 | `ix_psk_skill_trgm` |
| Trigram GIN (company_alias) | 1 | `ix_ca_alias_trgm` |
| Trigram GIN (role_alias) | 2 | `ix_ra_alias_trgm`, `ix_ra_canonical_trgm` |
| HNSW vector (crawled_profile) | 2 | `ix_cp_embedding_openai_hnsw`, `ix_cp_embedding_nomic_hnsw` |

### Query Pattern Anti-Patterns (for LLM-generated SQL)

GIN trigram indexes only help when the planner can push the ILIKE filter into a single-table scan. These patterns defeat the indexes:

| Anti-Pattern | Why It's Slow | Fix |
|---|---|---|
| `WHERE cp.X ILIKE '%Y%' OR e.X ILIKE '%Y%'` (OR across joined tables) | Planner can't push filter to either GIN index; falls back to seq scan + nested loop | Split into `UNION` of two simple queries |
| `SELECT DISTINCT` with multi-table JOINs | Hash aggregation on exploded row set | Use `UNION` (implicit dedup) or `GROUP BY pk` |
| `LEFT JOIN experience` without narrowing filter | Explodes rows before filtering | Use `INNER JOIN` with filter, or query `crawled_profile` first |
| 20+ chained `ILIKE` with `OR` | Bitmap OR of many GIN scans becomes expensive | Split into batches of ~5 per UNION branch |

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-04-02 | GIN index placement | Migration-only | Entity `__table_args__` | SQLite has no GIN support; unit tests would fail |
| 2026-04-02 | Keep existing btree indexes alongside GIN | Additive | Replace btree with GIN | Btree still serves equality and prefix-match queries |
| 2026-04-02 | Affinity index sort direction | DESC NULLS LAST | Default ASC | Matches actual query patterns (`ORDER BY affinity_score DESC NULLS LAST`) |
| 2026-04-02 | RLS policy form | EXISTS (correlated) | IN (subquery) | IN causes planner to hash profile IDs and prefer seq scan, ignoring GIN indexes. EXISTS lets planner use GIN first, then cheap index probe for visibility |
| 2026-04-07 | Single baseline migration | Consolidate all indexes | Incremental migration files | OSS starts fresh; no existing databases to migrate |

## Not Included

- Partial indexes (e.g., `WHERE is_active = true`) — not needed at current scale
- Expression indexes (e.g., `lower(full_name)`) — trigram GIN handles case-insensitive search
- Index maintenance or REINDEX scheduling
- Materialized views for RLS optimization (EXISTS policy change addressed the planner issue)
- Write-path performance tuning for GIN index maintenance
- `CONCURRENTLY` pattern for index creation (baseline runs on fresh databases; future migrations should use `CONCURRENTLY` with `autocommit_block()`)
