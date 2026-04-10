# Sub-Phase 7: Fresh Baseline Migration

**Phase:** 6 — Code Cleanup for OSS
**Plan task:** Decision Q3 (Alembic migration baseline)
**Dependencies:** sp2 (project_mgmt removed — know which tables are gone), sp3 (Procrastinate removed)
**Blocks:** sp9
**Can run in parallel with:** sp6, sp8

## Objective
Replace the entire Alembic migration history with a single fresh baseline migration for the OSS launch. The baseline includes all current tables (minus `project_mgmt` and `procrastinate_*`), all indexes, and required extensions. All old migration files are deleted.

## Context
- Read shared context: `docs/execution/phase-06/_shared_context.md`
- Read plan (Decision Q3): `docs/plan/phase-06-code-cleanup.md`
- Read current entity files to understand the target schema:
  - `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py`
  - `backend/src/linkedout/connection/entities/connection_entity.py`
  - `backend/src/linkedout/gmail_contacts/entities/` (if exists)
  - `backend/src/organization/entities/` (tenant, BU, enrichment config)
  - All entity files in `backend/src/linkedout/*/entities/`
- Read existing migrations: `backend/migrations/versions/`
- Read migration config: `backend/migrations/env.py`
- Read Phase 5 embedding decision: `docs/decision/2026-04-07-embedding-model-selection.md` — dual-column schema

## Deliverables

### 1. Catalog Current Schema

Before writing the migration, catalog what the schema should look like:

**Step 1:** List all SQLAlchemy entity files:
```bash
find backend/src/ -name "*_entity.py" -o -name "*_model.py" | sort
```

**Step 2:** For each entity, note the table name and columns. The baseline must create all of these.

**Step 3:** Identify what's excluded:
- `project_mgmt` tables (project, task, label, priority, project_summary, agent_run if only used there)
- `procrastinate_*` tables (jobs, events, periodic_defers, workers)

**Step 4:** Identify extensions needed:
- `vector` (pgvector)
- `pg_trgm` (trigram search)

**Step 5:** Identify indexes needed:
- HNSW indexes on embedding columns (per Phase 5 decision)
- GIN index on `search_vector` (pg_trgm full-text search)
- Standard B-tree indexes on foreign keys and frequently queried columns

### 2. Delete All Old Migration Files

```bash
# List what's there
ls backend/migrations/versions/

# Delete all migration files
rm backend/migrations/versions/*.py
```

Keep `backend/migrations/` directory structure intact:
- `backend/migrations/env.py` — keep (already cleaned of Procrastinate exclusions in sp3)
- `backend/migrations/script.py.mako` — keep (template)
- `backend/migrations/versions/` — empty it, then add baseline

### 3. Create Fresh Baseline Migration

Create `backend/migrations/versions/001_baseline.py` (use Alembic's revision ID format):

The migration should:

```python
"""Fresh baseline migration for LinkedOut OSS.

Replaces entire migration history. Creates all tables, indexes,
and extensions from scratch.

Revision ID: 001_baseline
Revises: None
Create Date: 2026-04-07
"""
```

**Extensions:**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

**Tables to create** (derive from entity files):
- All `linkedout.*` domain tables (crawled_profile, connection, gmail contacts, etc.)
- All `organization.*` tables (tenant, business_unit, enrichment_config)
- All `shared.*` tables (if any exist outside auth)
- Include Phase 5 dual-column embedding schema:
  - `embedding_openai vector(1536)`
  - `embedding_nomic vector(768)`
  - `embedding_model varchar(64)`
  - `embedding_dim smallint`
  - `embedding_updated_at timestamptz`

**Tables to DROP IF EXISTS** (cleanup of externally-created tables):
```sql
DROP TABLE IF EXISTS procrastinate_jobs CASCADE;
DROP TABLE IF EXISTS procrastinate_events CASCADE;
DROP TABLE IF EXISTS procrastinate_periodic_defers CASCADE;
DROP TABLE IF EXISTS procrastinate_workers CASCADE;
```

**Indexes to create:**
- HNSW indexes on `embedding_openai` and `embedding_nomic` columns
- GIN index on `search_vector` using `gin_trgm_ops`
- Standard B-tree indexes on foreign keys
- Any other indexes found in the old migrations

**RLS policies:**
- Include RLS policy setup from `d1e2f3a4b5c6_enable_rls_policies.py`
- This is critical — RLS is core to the auth model (documented in sp1)

**One-way only:**
- `def downgrade():` should raise `NotImplementedError("Downgrade not supported for baseline migration")`

### 4. Update Alembic Config

In `backend/migrations/env.py`:
- Ensure `target_metadata` points to the correct `Base.metadata`
- Remove any `include_object` filters that excluded `procrastinate_*` or `project_mgmt` tables (sp3 may have already done the Procrastinate part)
- Verify `version_table` setting if customized

### 5. Generate and Validate

```bash
cd backend

# Generate the migration using autogenerate as a reference (don't use it directly — write manually)
uv run alembic revision --autogenerate -m "baseline_check" --rev-id temp_check

# Compare autogenerate output with your manual baseline
# Delete the autogenerate migration after comparison
rm backend/migrations/versions/temp_check_*.py
```

## Verification
1. `ls backend/migrations/versions/` shows only the baseline migration file
2. `cd backend && uv run alembic heads` shows exactly one head
3. Against a fresh database: `cd backend && uv run alembic upgrade head` succeeds without errors
4. After migration: all expected tables exist, no `project_mgmt` or `procrastinate_*` tables
5. After migration: `SELECT * FROM pg_extension WHERE extname = 'vector'` returns a row
6. After migration: HNSW indexes exist on embedding columns
7. After migration: RLS policies are enabled on appropriate tables
8. `cd backend && uv run alembic check` reports no pending changes (schema matches models)

## Notes
- **This is a destructive operation for existing databases.** Users with existing data will need to dump and restore. This is acceptable for OSS launch — there are no external users yet.
- The baseline migration should be readable as a "here's the entire schema" document. Use clear section comments.
- If Phase 5 entity changes haven't been applied yet (dual embedding columns), include them anyway — the baseline should reflect the target state.
- The `agent_run` table: if sp2 determined it's only used by `project_mgmt`, exclude it from the baseline. If it's used elsewhere, include it.
- Use `op.create_table()` and `op.create_index()` Alembic operations, not raw SQL (except for extensions and RLS which require raw SQL).
