# Seed Pipeline: SQLite to pg_dump Migration — Shared Context

**Project:** LinkedOut OSS
**Plan:** `docs/plan/2026-04-09-seed-sqlite-to-pgdump.md`
**Date:** 2026-04-09

---

## Project Overview

LinkedOut is an AI-native professional network intelligence tool. The backend is Python/FastAPI with PostgreSQL + pgvector. The seed data pipeline provides reference data (companies, funding rounds, etc.) for bootstrapping new installations.

**Repo:** `sridherj/linkedout-oss`
**Monorepo structure:** `backend/` (Python), `extension/` (Chrome/WXT), `skills/`, `seed-data/`, `docs/`

---

## Migration Goal

Replace SQLite as the intermediate format in the seed data pipeline with pg_dump/pg_restore. This eliminates ~640 lines of type conversion code and the entire "impedance mismatch" bug class (boolean casting, array serialization, column naming differences).

**Non-goal:** Change what seed data contains (still 6 company/reference tables).

---

## Core Pattern: Staging Schema

Both export and import use `_seed_staging` as a staging schema:

### Export flow (maintainer-only)
```
PostgreSQL (production) → _seed_staging schema (filtered data) → pg_dump → .dump files
```

### Import flow (user-facing)
```
.dump file → pg_restore → _seed_staging schema → SQL upsert per table → public schema
```

### Column intersection (schema version safety)
The upsert uses the **intersection** of staging and public columns — only columns present in BOTH schemas. This handles version skew gracefully.

```sql
SELECT column_name FROM information_schema.columns
WHERE table_schema = '_seed_staging' AND table_name = :table
INTERSECT
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = :table
```

### pg_restore error handling
Exit codes: 0 = success, 1 = warnings (expected with `--clean --if-exists` when tables don't exist yet). Only exit code >= 2 is a real failure. This matches the pattern in `linkedout.demo.db_utils.restore_demo_dump()`.

---

## Decisions (from plan)

| # | Question | Decision |
|---|----------|----------|
| 1 | Import approach | Staging schema + SQL upsert |
| 2 | Export approach | Staging schema per tier |
| 3 | Test fixture | Require PG to generate, commit `.dump` |
| 4 | Demo fixture | Fix alongside seed (Phase 1) |
| 5 | Backward compat | None (pre-1.0 OSS) |
| 6 | db_url for subprocess | `get_config().database_url` (not `session.get_bind().url`) |
| 7 | CREATE SCHEMA in import | Remove — let pg_restore handle it; keep only `DROP SCHEMA IF EXISTS` |

---

## Seed Data Scale

- **Core tier:** ~47K companies (companies with experience data from crawled profiles)
- **Full tier:** ~218K companies (companies with employee count, funding, or size tier)
- 6 tables: `company`, `company_alias`, `role_alias`, `funding_round`, `startup_tracking`, `growth_signal`
- Released as `seed-v0.1.0` on GitHub Releases

---

## Key Constants and Patterns

- `SEED_TABLES` — ordered list of 6 tables
- `IMPORT_ORDER` — FK-safe import ordering
- `TIER_COMPANY_FILTER` — SQL subqueries for core/full tier filtering
- `TABLE_FILTER_COLUMN` — FK column per table for filtering (role_alias has None = export all)
- `SYSTEM_USER_ID` — used for RLS bypass in sessions
- `db_session_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID)` — session pattern
- `get_config().database_url` — how to get DATABASE_URL for subprocess calls

---

## Phase Dependency Graph

```
sp1 (demo fixture) ──┐
                      ├──► sp3 (import rewrite) ──► sp4 (test fixture) ──► sp5 (test updates) ──► sp6 (docs/specs)
sp2 (export rewrite) ─┘
```

sp1 and sp2 are independent and can run in parallel. All subsequent sub-phases are sequential.
