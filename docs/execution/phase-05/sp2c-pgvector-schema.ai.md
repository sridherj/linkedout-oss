# Sub-Phase 2c: pgvector Schema for Multi-Dimension Support

**Phase:** 5 — Embedding Provider Abstraction
**Plan task:** 5E (pgvector Schema)
**Dependencies:** None (Phase 2 entity patterns assumed available)
**Blocks:** sp3
**Can run in parallel with:** sp2a, sp2b, sp2d

## Objective
Modify the `crawled_profile` table to support embeddings from multiple providers with different dimensions. Rename the existing `embedding` column to `embedding_openai`, add `embedding_nomic vector(768)`, and add metadata columns. Create HNSW indexes for both embedding columns.

## Context
- Read shared context: `docs/execution/phase-05/_shared_context.md`
- Read plan (5E section): `docs/plan/phase-05-embedding-abstraction.md`
- Read entity: `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py`
- Read vector tool: `backend/src/linkedout/intelligence/tools/vector_tool.py`
- Read existing migrations: `backend/migrations/versions/` (check existing migration naming pattern)
- Cross-phase note: Phase 6 will create a fresh baseline migration. Design this as a clean Alembic migration that will later be absorbed into the baseline.
- **Agent reference:** Read `.claude/agents/entity-creation-agent.md` for entity modification conventions — column `comment` parameter, `DateTime(timezone=True)`, `Mapped[]` syntax, registration checklist (env.py, validate_orm.py, __init__.py). This sub-phase modifies an existing entity rather than creating a new one, but the same conventions apply.

## Deliverables

### 1. Alembic Migration: `backend/migrations/versions/XXXX_embedding_provider_metadata.py` (NEW)

Generate via: `cd backend && uv run alembic revision --autogenerate -m "embedding_provider_metadata"`

Then manually verify and adjust the generated migration. It must perform:

**Upgrade:**
```sql
-- Rename existing column
ALTER TABLE crawled_profile RENAME COLUMN embedding TO embedding_openai;

-- Add new columns
ALTER TABLE crawled_profile ADD COLUMN embedding_nomic vector(768);
ALTER TABLE crawled_profile ADD COLUMN embedding_model varchar(64);
ALTER TABLE crawled_profile ADD COLUMN embedding_dim smallint;
ALTER TABLE crawled_profile ADD COLUMN embedding_updated_at timestamptz;

-- Create HNSW indexes for both embedding columns
CREATE INDEX ix_cp_embedding_openai_hnsw ON crawled_profile
  USING hnsw (embedding_openai vector_cosine_ops);
CREATE INDEX ix_cp_embedding_nomic_hnsw ON crawled_profile
  USING hnsw (embedding_nomic vector_cosine_ops);

-- Drop old index if it exists (may have been named differently)
DROP INDEX IF EXISTS ix_cp_embedding_hnsw;
```

**Downgrade:**
```sql
DROP INDEX IF EXISTS ix_cp_embedding_openai_hnsw;
DROP INDEX IF EXISTS ix_cp_embedding_nomic_hnsw;
ALTER TABLE crawled_profile DROP COLUMN IF EXISTS embedding_nomic;
ALTER TABLE crawled_profile DROP COLUMN IF EXISTS embedding_model;
ALTER TABLE crawled_profile DROP COLUMN IF EXISTS embedding_dim;
ALTER TABLE crawled_profile DROP COLUMN IF EXISTS embedding_updated_at;
ALTER TABLE crawled_profile RENAME COLUMN embedding_openai TO embedding;
```

**Migration safety:**
- The rename preserves existing OpenAI embedding data
- New columns start as NULL — no data loss
- HNSW index creation on a populated table may take seconds to minutes depending on row count
- Downgrade path is defined and tested

### 2. Update Entity: `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py`

Replace the existing `embedding` column with the new schema:

```python
# REMOVE this line:
# embedding: Mapped[Optional[list]] = mapped_column(Vector(1536), nullable=True, comment='Vector embedding of profile data')

# ADD these lines:
embedding_openai: Mapped[Optional[list]] = mapped_column(
    Vector(1536), nullable=True, comment='OpenAI text-embedding-3-small vector'
)
embedding_nomic: Mapped[Optional[list]] = mapped_column(
    Vector(768), nullable=True, comment='nomic-embed-text-v1.5 vector'
)
embedding_model: Mapped[Optional[str]] = mapped_column(
    String(64), nullable=True, comment='Model that generated the active embedding'
)
embedding_dim: Mapped[Optional[int]] = mapped_column(
    SmallInteger, nullable=True, comment='Dimension of the active embedding'
)
embedding_updated_at: Mapped[Optional[datetime]] = mapped_column(
    DateTime(timezone=True), nullable=True, comment='When embedding was last generated'
)
```

Add `SmallInteger` to the SQLAlchemy imports.

### 3. Update Vector Search: `backend/src/linkedout/intelligence/tools/vector_tool.py`

The current SQL queries `cp.embedding`. Update to query the correct column based on the active provider.

**Key changes:**
- Import provider factory (or accept provider name as parameter)
- Determine which column to query: `embedding_openai` or `embedding_nomic`
- Update the `_SEARCH_SQL` template to use the correct column name
- Filter: only profiles that HAVE an embedding for the active provider (`embedding_col IS NOT NULL`)

Since the SQL is a raw string template, the simplest approach is two SQL constants or string formatting:

```python
def _get_search_sql(embedding_column: str) -> str:
    return f"""
    SELECT cp.id, cp.full_name, cp.headline, cp.current_position,
           cp.current_company_name, cp.location_city, cp.location_country,
           cp.linkedin_url, cp.public_identifier,
           c.id as connection_id, c.affinity_score, c.dunbar_tier, c.connected_at,
           cp.has_enriched_data,
           1 - (cp.{embedding_column} <=> CAST(:query_embedding AS vector)) AS similarity
    FROM crawled_profile cp
    JOIN connection c ON c.crawled_profile_id = cp.id
    WHERE cp.{embedding_column} IS NOT NULL
      AND 1 - (cp.{embedding_column} <=> CAST(:query_embedding AS vector)) > 0.25
    ORDER BY cp.{embedding_column} <=> CAST(:query_embedding AS vector)
    LIMIT :limit
    """

def _get_embedding_column() -> str:
    """Determine which embedding column to query based on configured provider."""
    # Import here to avoid circular deps
    from shared.config.config import backend_config
    provider = getattr(backend_config, 'LINKEDOUT_EMBEDDING_PROVIDER', 'openai')
    if provider == 'local':
        return 'embedding_nomic'
    return 'embedding_openai'
```

**Important:** The column name is determined from config, not from function parameters. This ensures the search always uses the provider the user has configured. The column name is one of two known values — this is NOT user input, so string formatting into SQL is safe here (not an injection risk).

### 4. Unit Tests

**`backend/tests/unit/crawled_profile/test_crawled_profile_entity.py`** — update or create:
- Verify `CrawledProfileEntity` has `embedding_openai`, `embedding_nomic`, `embedding_model`, `embedding_dim`, `embedding_updated_at` attributes
- Verify the old `embedding` attribute no longer exists

**`backend/tests/unit/intelligence/test_vector_tool.py`** — update or create:
- Test `_get_embedding_column()` returns `"embedding_openai"` when config is `"openai"`
- Test `_get_embedding_column()` returns `"embedding_nomic"` when config is `"local"`
- Test `_get_search_sql("embedding_openai")` contains correct column references

## Verification
1. `cd backend && uv run alembic upgrade head` — migration runs cleanly
2. `cd backend && uv run alembic downgrade -1` — downgrade works
3. `cd backend && uv run alembic upgrade head` — re-upgrade works
4. Verify schema in psql:
   ```sql
   \d crawled_profile
   -- Should show: embedding_openai vector(1536), embedding_nomic vector(768), etc.
   -- Should NOT show: embedding vector(1536) (old column name)
   ```
5. Verify indexes in psql:
   ```sql
   \di ix_cp_embedding_*
   -- Should show: ix_cp_embedding_openai_hnsw, ix_cp_embedding_nomic_hnsw
   ```
6. `cd backend && uv run pytest tests/unit/ -x --timeout=60` — all unit tests pass
7. If existing data exists: verify `embedding_openai` column contains the original embedding values (not NULL)

## Notes
- The column rename (`embedding` → `embedding_openai`) will break any code that references `cp.embedding` directly. This is intentional — sp3 updates all callers. Between sp2c and sp3, some code will be temporarily broken. This is acceptable because sub-phases are executed sequentially via the dependency graph.
- The HNSW index creation on an empty table (fresh install) is instant. On a populated table with embeddings, it may take a few seconds.
- Phase 6 will create a fresh baseline migration that absorbs this migration. Keep the migration clean and well-documented so the baseline merger can understand the intent.
