# Shared Context: Phase 05 — Embedding Provider Abstraction

## Goal
Support pluggable embedding providers so users can choose between OpenAI embeddings (fast, paid) and local nomic-embed-text-v1.5 (free, slower). The current codebase is hardcoded to OpenAI's `text-embedding-3-small` at 1536 dimensions. This phase introduces a provider abstraction, adds the nomic local provider, handles variable vector dimensions in pgvector, and makes `linkedout embed` resumable and idempotent.

## Key Artifacts
- **Phase plan (source of truth):** `docs/plan/phase-05-embedding-abstraction.md`
- **CLI surface decision:** `docs/decision/cli-surface.md`
- **Config design decision:** `docs/decision/env-config-design.md`
- **Logging strategy decision:** `docs/decision/logging-observability-strategy.md`
- **Queue strategy decision:** `docs/decision/queue-strategy.md`
- **Embedding model decision:** `docs/decision/2026-04-07-embedding-model-selection.md`
- **Data directory decision:** `docs/decision/2026-04-07-data-directory-convention.md`

## Architecture Overview

### Embedding System (Current State)
The embedding system is currently hardcoded to OpenAI:
- `EmbeddingClient` in `backend/src/utilities/llm_manager/embedding_client.py` wraps the OpenAI API
- Supports real-time single/batch embedding and OpenAI Batch API for large-scale processing
- `CrawledProfileEntity` has a single `embedding vector(1536)` column
- `vector_tool.py` does semantic search via cosine distance on that column
- `generate_embeddings.py` is the CLI script that orchestrates embedding generation
- `profile_enrichment_service.py` embeds profiles during enrichment pipeline

### Embedding System (Target State)
```
EmbeddingProvider (ABC)
  ├── OpenAIEmbeddingProvider  (wraps existing EmbeddingClient)
  └── LocalEmbeddingProvider   (nomic-embed-text-v1.5 via sentence-transformers + ONNX)

get_embedding_provider(provider?, model?) → EmbeddingProvider  (factory)

crawled_profile table:
  embedding_openai vector(1536)   ← renamed from `embedding`
  embedding_nomic vector(768)     ← new column
  embedding_model varchar(64)     ← tracks active provider
  embedding_dim smallint          ← tracks dimension
  embedding_updated_at timestamptz

~/linkedout-data/state/embedding_progress.json  ← resumability state
~/linkedout-data/reports/embed-*.json           ← operation reports
```

### Module Structure (Target)
```
backend/src/utilities/llm_manager/
├── __init__.py                     (export factory)
├── embedding_provider.py           (ABC — NEW)
├── openai_embedding_provider.py    (OpenAI impl — NEW)
├── local_embedding_provider.py     (Nomic impl — NEW)
├── embedding_factory.py            (factory function — NEW)
├── embedding_client.py             (existing — kept as internal impl detail)
├── llm_client.py                   (existing — untouched)
├── llm_factory.py                  (existing — untouched)
└── ...

backend/src/utilities/
├── embedding_progress.py           (progress tracking — NEW)
└── ...
```

## Codebase Conventions
- **Build system:** `uv run` for Python commands. Dependencies in `backend/requirements.txt`.
- **ORM:** SQLAlchemy 2.0 with `Mapped[]` type annotations. Alembic for migrations.
- **Entities:** Domain entities in `backend/src/linkedout/<domain>/entities/`. Base class: `BaseEntity` from `common.entities.base_entity`.
- **Services:** Business logic in `backend/src/linkedout/<domain>/services/`.
- **CLI:** Click commands in `backend/src/dev_tools/`. Will be rewired to `linkedout` namespace.
- **Logging:** loguru via `get_logger()` from `shared.utilities.logger`. Bind `component` and `operation` fields. No JSON log format — structured data goes to `~/linkedout-data/reports/` and `~/linkedout-data/metrics/`.
- **Config:** pydantic-settings via `backend/src/shared/config/config.py`. Env vars override YAML. Prefix: `LINKEDOUT_`.
- **DB sessions:** `db_session_manager.get_session(DbSessionType.READ|WRITE, app_user_id=...)` context manager.
- **Tests:** pytest in `backend/tests/`. Unit tests mock external APIs. Integration tests use real DB.
- **pgvector:** `pgvector.sqlalchemy.Vector` type for embedding columns. HNSW indexes for search performance.
- **System user:** `SYSTEM_USER_ID` from `dev_tools.db.fixed_data` for CLI operations.

## Key File Paths

| File | Purpose |
|------|---------|
| `backend/src/utilities/llm_manager/embedding_client.py` | Existing OpenAI embedding client — wrap, don't replace |
| `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py` | Profile entity with `embedding vector(1536)` column |
| `backend/src/linkedout/intelligence/tools/vector_tool.py` | Semantic search — queries `embedding` column with cosine distance |
| `backend/src/linkedout/crawled_profile/services/profile_enrichment_service.py` | Enrichment pipeline — instantiates `EmbeddingClient` directly (~line 41) |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | Affinity scoring — reads embedding similarity |
| `backend/src/dev_tools/generate_embeddings.py` | Current embedding generation script — becomes `linkedout embed` |
| `backend/src/shared/config/config.py` | Configuration singleton via pydantic-settings |
| `backend/src/dev_tools/db/fixed_data.py` | `SYSTEM_USER_ID` and other fixed system data |
| `backend/src/shared/infra/db/db_session_manager.py` | DB session management |
| `backend/migrations/` | Alembic migrations directory |

## Data Schemas

### Current `crawled_profile` (Relevant Columns)
```sql
embedding vector(1536)          -- OpenAI text-embedding-3-small
search_vector text              -- tsvector for full-text search
has_enriched_data boolean       -- gate for embedding generation
```

### Target `crawled_profile` (After Migration)
```sql
embedding_openai vector(1536)   -- renamed from 'embedding'
embedding_nomic vector(768)     -- new column
embedding_model varchar(64)     -- 'text-embedding-3-small' or 'nomic-embed-text-v1.5'
embedding_dim smallint          -- 1536 or 768
embedding_updated_at timestamptz -- when embedding was last generated
search_vector text              -- unchanged
has_enriched_data boolean       -- unchanged
```

### Progress State File (`~/linkedout-data/state/embedding_progress.json`)
```json
{
  "provider": "local",
  "model": "nomic-embed-text-v1.5",
  "dimension": 768,
  "total_profiles": 4012,
  "completed_profiles": 2847,
  "last_processed_id": "cp_abc123def",
  "started_at": "2026-04-07T14:23:05Z",
  "updated_at": "2026-04-07T14:45:00Z",
  "status": "in_progress"
}
```

### Config Fields (from env-config-design.md)
```yaml
# ~/linkedout-data/config/config.yaml
embedding_provider: openai   # openai | local — MUST be explicit, no auto
# embedding_model: text-embedding-3-small   # override if needed
```

Env vars: `LINKEDOUT_EMBEDDING_PROVIDER`, `LINKEDOUT_EMBEDDING_MODEL`.

## Pre-Existing Decisions

1. **No `auto` mode for provider selection.** User must explicitly choose `openai` or `local` during setup. Error with guidance if `LINKEDOUT_EMBEDDING_PROVIDER` is unset.
2. **Real-time API is the default for OpenAI.** `--batch` flag available for cost-conscious users. Cost difference on 4K profiles is negligible.
3. **nomic-embed-text-v1.5 is the local model.** Not MiniLM. 768 dimensions. Apache 2.0. ~275MB model download.
4. **Model download during setup.** Download happens during setup, not during `linkedout embed`. Never surprise users with a 275MB download.
5. **Separate embedding columns per provider.** Not re-embed-on-switch, not separate table. Profiles can have embeddings from both providers simultaneously.
6. **Dual-column cleanup deferred.** 50MB is negligible. No `--cleanup` flag in v1.
7. **HNSW indexes in migration.** Required for acceptable query performance.
8. **Failed embeddings in `~/linkedout-data/reports/`.** Operation artifact, not log stream.
9. **No Procrastinate.** Embedding runs synchronously in CLI. Progress bar for user visibility.
10. **Cross-phase: Phase 6 fresh baseline migration.** The schema additions go into the baseline migration, not as incremental migrations. Design the Alembic migration with this in mind.
11. **Cross-phase: Phase 9 setup flow.** Setup asks user to choose provider explicitly. If local chosen, setup downloads nomic model synchronously.
12. **Operation result pattern:** Progress → Summary → Gaps → Next steps → Report path. Enforced by `OperationReport` class.

## Build Order

```
sp1 (Foundation: ABC + Config)
  ↓
sp2a (OpenAI Provider)  ─┐
sp2b (Local Provider)    ├── all parallel, depend on sp1
sp2c (pgvector Schema)   │   (sp2c has no internal deps)
sp2d (Progress Tracking) ┘   (sp2d has no internal deps)
  ↓
sp3 (Factory + Update Callers)  ── depends on sp2a, sp2b, sp2c
  ↓
sp4 (CLI Command + Tests)  ── depends on sp3, sp2d
```

## Phase Dependency Summary

| Sub-Phase | Depends On | Blocks | Can Parallel With |
|-----------|-----------|--------|-------------------|
| sp1 | Phase 2 (config system) | sp2a, sp2b | sp2c, sp2d |
| sp2a | sp1 | sp3 | sp2b, sp2c, sp2d |
| sp2b | sp1 | sp3 | sp2a, sp2c, sp2d |
| sp2c | None (Phase 2 entity patterns) | sp3 | sp2a, sp2b, sp2d |
| sp2d | None | sp4 | sp2a, sp2b, sp2c |
| sp3 | sp2a, sp2b, sp2c | sp4 | sp2d |
| sp4 | sp3, sp2d | None | None |

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When writing provider classes, factory function, CLI command |
| `.claude/skills/pytest-best-practices/SKILL.md` | When writing tests for providers and CLI — naming, AAA pattern |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating new modules (`embedding_provider.py`, `openai_embedding_provider.py`, `local_embedding_provider.py`, `embedding_factory.py`) |
| `.claude/skills/mvcs-compliance/SKILL.md` | When modifying `profile_enrichment_service.py` and `vector_tool.py` — service layer rules |

### Agents (sub-phase specific)
| Agent | Sub-Phase | When to Invoke |
|-------|-----------|---------------|
| `.claude/agents/entity-creation-agent.md` | sp2c (pgvector schema) | Reference for entity modification patterns — adding columns, column comments, `DateTime(timezone=True)`, SQLAlchemy 2.0 `Mapped[]` syntax. Note: not creating a new entity, but modifying `CrawledProfileEntity` — use as a checklist for entity conventions. |
| `.claude/agents/integration-test-creator-agent.md` | sp4 (CLI + tests) | Reference for integration test patterns, fixtures, DB-backed test setup |

### Notes
- The `entity-creation-agent` checklist for column comments, timezone-aware datetimes, and JSONB usage applies when modifying the crawled_profile entity in sp2c
- sp2b (local provider) involves model download logic — no specific agent, but follow Python best practices skill for error handling patterns
