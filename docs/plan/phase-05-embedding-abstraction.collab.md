# Phase 5: Embedding Provider Abstraction — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Draft — pending SJ review
**Dependencies:** Phase 2 (Env & Config), Phase 3 (Logging & Observability), Phase 4 (Constants Externalization)
**Can parallel with:** Phase 6 (Code Cleanup)

---

## Phase Overview

### Goal

Support pluggable embedding providers so users can choose between OpenAI embeddings (fast, paid) and local nomic-embed-text-v1.5 (free, slower). The current codebase is hardcoded to OpenAI's `text-embedding-3-small` at 1536 dimensions. This phase introduces a provider abstraction, adds the nomic local provider, handles variable vector dimensions in pgvector, and makes `linkedout embed` resumable and idempotent.

### What This Phase Delivers

1. An `EmbeddingProvider` ABC that both OpenAI and nomic providers implement
2. A local nomic-embed-text-v1.5 provider using sentence-transformers + ONNX
3. A pgvector schema that supports multiple embedding dimensions (1536 for OpenAI, 768 for nomic)
4. A resumable, idempotent `linkedout embed` CLI command with progress tracking
5. Config wiring so users pick their provider during setup or via config.yaml
6. Output artifacts (reports) for every embedding operation per Phase 3 patterns

### What This Phase Does NOT Deliver

- Matryoshka dimension flexibility (future optimization)
- Automatic provider switching detection (users run `linkedout embed --force` when switching)
- Streaming/SSE progress for API endpoints (CLI progress only)

---

## Integration Points with Phase 0 Decisions

| Decision Doc | Constraint Applied |
|--------------|--------------------|
| `docs/decision/cli-surface.md` | `linkedout embed` command with `--provider`, `--force`, `--resume`, `--dry-run` flags. Flat namespace. |
| `docs/decision/env-config-design.md` | `LINKEDOUT_EMBEDDING_PROVIDER` (openai\|local), `LINKEDOUT_EMBEDDING_MODEL` override. Config in `~/linkedout-data/config/config.yaml`. |
| `docs/decision/logging-observability-strategy.md` | loguru logging with `component="cli"`, `operation="embed"`. Operation result pattern: Progress -> Summary -> Gaps -> Next steps -> Report path. Reports to `~/linkedout-data/reports/`. |
| `docs/decision/queue-strategy.md` | No Procrastinate. Embedding runs synchronously in CLI. Progress bar for user visibility. |
| `docs/decision/2026-04-07-embedding-model-selection.md` | nomic-embed-text-v1.5 as default local model (not MiniLM). 768 dimensions. Apache 2.0. ~275MB model download. |
| `docs/decision/2026-04-07-data-directory-convention.md` | State files in `~/linkedout-data/state/`. Reports in `~/linkedout-data/reports/`. |

---

## Detailed Task Breakdown

### 5A. Provider Interface (ABC)

**Complexity:** S
**File targets:**
- Create: `backend/src/utilities/llm_manager/embedding_provider.py`

**Description:**
Define the `EmbeddingProvider` abstract base class that all embedding providers implement. This is the contract that decouples the rest of the codebase from any specific embedding API.

**Implementation:**

```python
# backend/src/utilities/llm_manager/embedding_provider.py
from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of vectors."""
        ...

    @abstractmethod
    def embed_single(self, text: str) -> list[float]:
        """Embed a single text. Returns one vector."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension for this provider/model."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model identifier."""
        ...

    @abstractmethod
    def estimate_time(self, count: int) -> str:
        """Human-readable time estimate for embedding `count` texts."""
        ...

    @abstractmethod
    def estimate_cost(self, count: int) -> str | None:
        """Human-readable cost estimate, or None if free."""
        ...
```

**Acceptance criteria:**
- [ ] ABC defined with all 6 methods
- [ ] Type hints are complete
- [ ] No external dependencies in this file (pure interface)
- [ ] Docstrings explain the contract for each method

---

### 5B. OpenAI Provider (Default)

**Complexity:** M
**File targets:**
- Create: `backend/src/utilities/llm_manager/openai_embedding_provider.py`
- Modify: `backend/src/utilities/llm_manager/embedding_client.py` (extract reusable logic, keep as internal implementation detail)

**Description:**
Wrap the existing `EmbeddingClient` in an `OpenAIEmbeddingProvider` that implements the ABC. The existing Batch API support (`create_batch_file`, `submit_batch`, `poll_batch`) is preserved and exposed through a `embed_batch_async` method for large-scale operations.

**Implementation details:**
- `embed()` delegates to existing `EmbeddingClient.embed_batch()` (real-time API, chunked)
- `embed_single()` delegates to existing `EmbeddingClient.embed_text()`
- `dimension()` returns config value (default 1536 for text-embedding-3-small)
- `model_name()` returns config value (default "text-embedding-3-small")
- `estimate_time()`: ~1000 profiles/minute via Batch API, ~100/minute via real-time
- `estimate_cost()`: Based on OpenAI pricing (~$0.02 per 1M tokens, estimate ~500 tokens per profile)
- Keep `build_embedding_text()` static method as-is (shared across providers)
- Preserve Batch API methods as provider-specific capabilities (not on the ABC — only OpenAI supports this)
- Reads `OPENAI_API_KEY` from config (via Phase 2 config system)
- Produces report artifact: `~/linkedout-data/reports/embed-openai-YYYYMMDD-HHMMSS.json`

**Acceptance criteria:**
- [ ] Implements all 6 ABC methods
- [ ] Existing EmbeddingClient functionality preserved (no regressions)
- [ ] Batch API methods available as provider-specific capabilities
- [ ] Raises clear error if `OPENAI_API_KEY` not configured
- [ ] Logs embedding operations via loguru with `component="cli"`, `operation="embed"`
- [ ] Unit tests with mocked OpenAI API

---

### 5C. Local Nomic Provider (Fallback)

**Complexity:** M
**File targets:**
- Create: `backend/src/utilities/llm_manager/local_embedding_provider.py`
- Modify: `backend/requirements.txt` (add `sentence-transformers`, `onnxruntime`)

**Description:**
Implement `LocalEmbeddingProvider` using sentence-transformers with nomic-embed-text-v1.5. ONNX backend for faster CPU inference. Lazy model loading — model is downloaded on first use, not at import time.

**Implementation details:**
- Model: `nomic-ai/nomic-embed-text-v1.5` via sentence-transformers
- Dimensions: 768 (fixed for v1 — Matryoshka flexibility deferred)
- ONNX backend: Use `onnxruntime` for ~2-3x speedup over PyTorch on CPU
- Lazy loading: Model loaded on first `embed()` call, cached for session
- Model cache location: `~/linkedout-data/models/` (configurable via `LINKEDOUT_DATA_DIR`)
- `embed()` processes in batches of 32 (sentence-transformers default, configurable)
- `embed_single()` wraps `embed([text])[0]`
- `dimension()` returns 768
- `model_name()` returns "nomic-embed-text-v1.5"
- `estimate_time()`: Benchmark during implementation. Expected ~5-10 profiles/second on modern CPU. Estimate: "~7 minutes for 4,000 profiles" (adjust based on actual benchmarks)
- `estimate_cost()` returns `None` (free)
- Produces report artifact: `~/linkedout-data/reports/embed-local-YYYYMMDD-HHMMSS.json`
- Graceful error if model download fails (network issues) with actionable message

**New dependencies:**
- `sentence-transformers>=3.0.0` — model loading and inference
- `onnxruntime>=1.18.0` — ONNX CPU backend
- These are **optional** dependencies: only required if `LINKEDOUT_EMBEDDING_PROVIDER=local`. Import lazily and give clear error if missing.

**Acceptance criteria:**
- [ ] Implements all 6 ABC methods
- [ ] Model downloads lazily on first use to `~/linkedout-data/models/`
- [ ] ONNX backend used for inference
- [ ] Works without GPU (CPU-only)
- [ ] No error on `import` if sentence-transformers not installed (lazy import)
- [ ] Clear error message if user selects `local` provider but dependencies not installed
- [ ] Produces 768-dimensional vectors
- [ ] Logs model download progress and embedding operations
- [ ] Unit tests with small model or mocked inference

---

### 5D. Provider Factory

**Complexity:** S
**File targets:**
- Create: `backend/src/utilities/llm_manager/embedding_factory.py`
- Modify: `backend/src/utilities/llm_manager/__init__.py` (export factory)

**Description:**
Factory function that returns the configured `EmbeddingProvider` instance based on config. Single point of provider instantiation.

**Implementation:**

```python
# backend/src/utilities/llm_manager/embedding_factory.py
from utilities.llm_manager.embedding_provider import EmbeddingProvider

def get_embedding_provider(provider: str | None = None, model: str | None = None) -> EmbeddingProvider:
    """
    Return configured EmbeddingProvider instance.
    
    Args:
        provider: "openai" or "local". Defaults to config value.
        model: Override model name. Defaults to provider's default.
    """
    # Read from config if not specified
    provider = provider or settings.embedding_provider  # from Phase 2 config
    
    if provider == "openai":
        from utilities.llm_manager.openai_embedding_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(model=model)
    elif provider == "local":
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider
        return LocalEmbeddingProvider(model=model)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}. Use 'openai' or 'local'.")
```

**Acceptance criteria:**
- [ ] Returns correct provider based on config
- [ ] Lazy imports (no unnecessary dependency loading)
- [ ] Clear error for unknown provider names
- [ ] Reads defaults from Phase 2 config system

---

### 5E. pgvector Schema for Multi-Dimension Support

**Complexity:** L
**File targets:**
- Create: `backend/migrations/versions/XXXX_embedding_provider_metadata.py` (new Alembic migration)
- Modify: `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py` (add metadata columns)
- Modify: `backend/src/linkedout/intelligence/tools/vector_tool.py` (handle variable dimensions in search)

**Description:**
The current schema has a single `embedding vector(1536)` column. We need to support both 1536 (OpenAI) and 768 (nomic) dimensions. After evaluating the options from the plan:

**Chosen approach: Separate columns per provider with metadata.**

Rationale:
- Option (a) "re-embed all on switch" is expensive and blocks provider experimentation
- Option (b) "separate columns" allows querying with either provider's embeddings without re-embedding everything
- Option (c) "separate table" adds join overhead to every query

**Schema changes:**

```sql
-- New columns on crawled_profile
ALTER TABLE crawled_profile ADD COLUMN embedding_nomic vector(768);
ALTER TABLE crawled_profile ADD COLUMN embedding_model varchar(64);
ALTER TABLE crawled_profile ADD COLUMN embedding_dim smallint;
ALTER TABLE crawled_profile ADD COLUMN embedding_updated_at timestamptz;

-- Rename existing column for clarity
ALTER TABLE crawled_profile RENAME COLUMN embedding TO embedding_openai;

-- HNSW indexes for both
CREATE INDEX ix_cp_embedding_openai_hnsw ON crawled_profile 
  USING hnsw (embedding_openai vector_cosine_ops);
CREATE INDEX ix_cp_embedding_nomic_hnsw ON crawled_profile 
  USING hnsw (embedding_nomic vector_cosine_ops);

-- Drop old index name if it conflicts
DROP INDEX IF EXISTS ix_cp_embedding_hnsw;
```

**Entity changes:**

```python
# In crawled_profile_entity.py
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

**Search logic changes in `vector_tool.py`:**

```python
# Determine which embedding column to query based on configured provider
provider = get_embedding_provider()
if provider.model_name().startswith("nomic"):
    embedding_col = CrawledProfileEntity.embedding_nomic
else:
    embedding_col = CrawledProfileEntity.embedding_openai

# Filter: only profiles that HAVE an embedding for the active provider
query = query.filter(embedding_col.isnot(None))
# Order by cosine similarity
query = query.order_by(embedding_col.cosine_distance(query_vector))
```

**Migration safety:**
- The migration renames `embedding` → `embedding_openai` (preserving existing data)
- Existing HNSW index is recreated with new column name
- New `embedding_nomic` column starts as NULL for all rows
- No data loss, no downtime

> **Design ceiling (review finding 2026-04-07):** The dual-column approach is capped at 2 providers. If a third provider is ever needed, migrate to a separate `embedding` table with (profile_id, provider, vector) rows. This is an acceptable trade-off for v1 simplicity — 2 providers (OpenAI + local nomic) covers all planned use cases.

**Acceptance criteria:**
- [ ] Alembic migration runs cleanly on existing databases (preserves OpenAI embeddings)
- [ ] Entity model reflects new schema
- [ ] `vector_tool.py` queries the correct column based on active provider
- [ ] HNSW indexes exist for both embedding columns
- [ ] Profiles can have embeddings from one or both providers simultaneously
- [ ] `embedding_model` and `embedding_dim` track what generated each embedding
- [ ] Migration is reversible (downgrade path defined)

---

### 5F. Update Embedding Generation Callers

**Complexity:** M
**File targets:**
- Modify: `backend/src/linkedout/crawled_profile/services/profile_enrichment_service.py` (use provider factory)
- Modify: `backend/src/dev_tools/generate_embeddings.py` (use provider factory, write to correct column)
- Modify: `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` (read from correct column)

**Description:**
Update all code that generates or reads embeddings to use the provider abstraction instead of directly instantiating `EmbeddingClient`.

**Changes:**

1. **`profile_enrichment_service.py`** (~line 180-205):
   - Replace `EmbeddingClient()` instantiation with `get_embedding_provider()`
   - Write to the correct column based on provider (`embedding_openai` or `embedding_nomic`)
   - Set `embedding_model`, `embedding_dim`, `embedding_updated_at` metadata columns

2. **`generate_embeddings.py`** (CLI tool):
   - This becomes the implementation behind `linkedout embed`
   - Replace direct `EmbeddingClient` usage with `get_embedding_provider()`
   - Respect `--provider` flag (override config)
   - Write to correct column based on provider
   - When `--force` is used, clear the target column and re-embed all
   - Batch API mode remains OpenAI-specific (not available for local provider)

3. **`affinity_scorer.py`** (~line 24):
   - Embedding similarity calculation must read from the active provider's column
   - If profile has no embedding for active provider, skip embedding component of affinity (don't fail)

**Acceptance criteria:**
- [ ] No direct `EmbeddingClient` instantiation outside the OpenAI provider
- [ ] Enrichment pipeline writes to correct column
- [ ] CLI tool respects `--provider` flag
- [ ] Affinity scorer reads from correct column
- [ ] No regressions in existing enrichment flow

---

### 5G. Progress Tracking & Resumability

**Complexity:** M
**File targets:**
- Create: `backend/src/utilities/embedding_progress.py`
- Modify: `backend/src/dev_tools/generate_embeddings.py` (integrate progress tracking)

**Description:**
Both providers write progress to `~/linkedout-data/state/embedding_progress.json` so embedding operations can be interrupted and resumed without re-processing completed profiles.

**State file format:**

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

**Implementation details:**
- Progress file written after each batch (e.g., every 32 profiles for local, every 500 for OpenAI)
- On startup, `linkedout embed` checks for existing progress file
  - If found and `status=in_progress`: resume from `last_processed_id`
  - If found and `status=completed`: skip (already done, unless `--force`)
  - If not found: start fresh
- Query profiles ordered by ID, filter `WHERE id > last_processed_id`
- Never re-embed profiles that already have an embedding for the active provider (idempotent)
- `--force` flag clears the progress file and re-embeds all
- On completion, set `status=completed` and write final report artifact

**Acceptance criteria:**
- [ ] Progress file written to `~/linkedout-data/state/embedding_progress.json`
- [ ] Resuming from interrupted state works correctly (no duplicates, no gaps)
- [ ] `--force` starts fresh
- [ ] Idempotent: running `linkedout embed` on fully-embedded DB is a no-op
- [ ] Progress bar shows correct position when resuming

---

### 5H. `linkedout embed` CLI Command

**Complexity:** M
**File targets:**
- Modify: `backend/src/dev_tools/generate_embeddings.py` (refactor into the `linkedout embed` command)
- Modify: CLI registration (wherever the `linkedout` Click group is defined — depends on Phase 6E progress)

**Description:**
Wire the embedding pipeline into the `linkedout embed` CLI command per `docs/decision/cli-surface.md`. This is the user-facing command that combines the provider factory, progress tracking, and operation result pattern.

**CLI contract (from cli-surface.md):**

```
linkedout embed [OPTIONS]

Options:
  --provider PROVIDER   Embedding provider: openai, local (default: from config; no 'auto' — must be explicit)
  --dry-run             Report what would be embedded, do not run
  --resume              Resume from last checkpoint (default: true)
  --force               Re-embed all profiles, even those with current embeddings
```

**Output follows the Operation Result Pattern (from logging-observability-strategy.md):**

```
$ linkedout embed

Embedding profiles with nomic-embed-text-v1.5 (768d, local)...
Estimated time: ~7 minutes for 4,012 profiles

  [===================>          ] 2,847/4,012 profiles (71%)  ETA: 2m 30s

Results:
  Embedded:   4,000 profiles
  Skipped:    12 (already embedded with nomic-embed-text-v1.5)
  Failed:     0
  Provider:   nomic-embed-text-v1.5 (768d)
  Duration:   6m 42s

Next steps:
  -> Run `linkedout compute-affinity` to update affinity scores

Report saved: ~/linkedout-data/reports/embed-local-20260407-142305.json
```

**Logging integration:**
- Uses loguru with `component="cli"`, `operation="embed"`
- Logs to `~/linkedout-data/logs/cli.log`
- Metrics event written to `~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl`

**Acceptance criteria:**
- [ ] `linkedout embed` works end-to-end with both providers
- [ ] `--dry-run` reports counts without modifying DB
- [ ] `--force` re-embeds all profiles
- [ ] `--provider` overrides config
- [ ] Progress bar with ETA
- [ ] Operation result pattern: Progress -> Summary -> Gaps -> Next steps -> Report path
- [ ] Report artifact written to `~/linkedout-data/reports/`
- [ ] Metrics event recorded
- [ ] Works for 0 profiles (no-op with message)

---

### 5I. Config Wiring

**Complexity:** S
**File targets:**
- Modify: `backend/src/shared/config/config.py` (ensure embedding config fields exist — may already be done by Phase 2)
- Verify: `docs/decision/env-config-design.md` fields are wired

**Description:**
Ensure the embedding provider selection is wired through the Phase 2 config system. This task may be partially complete after Phase 2 — verify and fill gaps.

**Config fields (from env-config-design.md):**

| Variable | Default | Description |
|----------|---------|-------------|
| `LINKEDOUT_EMBEDDING_PROVIDER` | `openai` | `openai` or `local` |
| `LINKEDOUT_EMBEDDING_MODEL` | (provider default) | Override model name |

**YAML mapping:**
```yaml
# ~/linkedout-data/config/config.yaml
embedding_provider: openai   # openai | local
# embedding_model: text-embedding-3-small   # override if needed
```

**Onboarding guidance (for Phase 9 setup skill to use):**
- OpenAI: Fast (Batch API, ~minutes for 4K profiles, ~$0.01). Requires OPENAI_API_KEY.
- Local nomic: Free, no API key. Slower (~7 min for 4K profiles on CPU). ~275MB model download on first use.
- Default: must be explicitly set during setup (resolved decision Q2 — no auto-detection). Error if not configured.

**Acceptance criteria:**
- [ ] `LINKEDOUT_EMBEDDING_PROVIDER` env var works
- [ ] `config.yaml` `embedding_provider` field works
- [ ] Env var overrides YAML value
- [ ] No `auto` mode — provider must be explicitly configured. Error with guidance if unset.
- [ ] Config validation: warn if `openai` selected but no API key

---

## Testing Strategy

### Unit Tests

| Test | File | What It Validates |
|------|------|-------------------|
| Provider ABC contract | `tests/unit/llm_manager/test_embedding_provider.py` | Both providers implement all ABC methods |
| OpenAI provider | `tests/unit/llm_manager/test_openai_embedding_provider.py` | Mocked OpenAI API calls, correct dimensions, error handling |
| Local provider | `tests/unit/llm_manager/test_local_embedding_provider.py` | Mocked sentence-transformers, correct dimensions, lazy loading |
| Provider factory | `tests/unit/llm_manager/test_embedding_factory.py` | Returns correct provider based on config |
| Progress tracking | `tests/unit/test_embedding_progress.py` | Save/load/resume state file, idempotency |
| Embed CLI | `tests/unit/cli/test_embed_command.py` | Dry-run, force, resume flags, output format |

### Integration Tests (Real DB)

| Test | What It Validates |
|------|-------------------|
| Schema migration | Migration runs on existing DB, preserves OpenAI embeddings in renamed column |
| OpenAI embed + search | End-to-end: embed profile with OpenAI, search returns it (mocked API, real DB) |
| Local embed + search | End-to-end: embed profile with nomic, search returns it (real model if CI has resources, else mocked) |
| Provider switch | Embed with OpenAI, switch to local, re-embed with `--force`, search works |
| Resume after interrupt | Embed 50%, interrupt, resume, verify no duplicates |

### What We Don't Test

- Real OpenAI API calls (too slow, costs money) — mock the API
- GPU inference (OSS targets CPU only)
- Matryoshka dimensions (deferred)

---

## Exit Criteria Verification Checklist

- [ ] Both `openai` and `local` providers produce embeddings and write to the correct pgvector column
- [ ] `linkedout embed` is resumable: interrupt mid-run, restart, no duplicates
- [ ] `linkedout embed` is idempotent: running on fully-embedded DB is a no-op
- [ ] `linkedout embed --force` re-embeds all profiles
- [ ] `linkedout embed --dry-run` reports counts without writing
- [ ] Progress tracked in `~/linkedout-data/state/embedding_progress.json`
- [ ] Embedding output reports written to `~/linkedout-data/reports/` with precise counts
- [ ] Switching providers (config change + `linkedout embed --force`) works without data loss
- [ ] Semantic search (`vector_tool.py`) queries the correct column for the active provider
- [ ] Affinity scoring reads from the correct embedding column
- [ ] No `EmbeddingClient` instantiated directly outside the OpenAI provider
- [ ] All existing tests pass (no regressions)
- [ ] New unit + integration tests pass

---

## Estimated Complexity Summary

| Task | Complexity | Estimated Effort |
|------|-----------|------------------|
| 5A. Provider Interface (ABC) | S | ~1 hour |
| 5B. OpenAI Provider | M | ~3 hours |
| 5C. Local Nomic Provider | M | ~4 hours (includes benchmarking) |
| 5D. Provider Factory | S | ~30 minutes |
| 5E. pgvector Schema | L | ~4 hours (migration + entity + search logic) |
| 5F. Update Callers | M | ~3 hours |
| 5G. Progress Tracking | M | ~3 hours |
| 5H. `linkedout embed` CLI | M | ~3 hours |
| 5I. Config Wiring | S | ~1 hour |
| **Total** | | **~22 hours** |

---

## Task Dependency Graph

```
5A (Provider ABC)
  ├── 5B (OpenAI Provider)
  ├── 5C (Local Nomic Provider)
  └── 5D (Provider Factory)  ── depends on 5B + 5C
        └── 5F (Update Callers)  ── depends on 5D + 5E
              └── 5H (linkedout embed CLI)  ── depends on 5F + 5G

5E (pgvector Schema)  ── can start in parallel with 5A-5D
5G (Progress Tracking)  ── can start in parallel with 5A-5E
5I (Config Wiring)  ── can start anytime (depends on Phase 2)
```

**Parallelizable:** 5A → (5B, 5C in parallel) → 5D. Meanwhile 5E, 5G, 5I can proceed independently. 5F and 5H are the integration points that depend on everything else.

---

## Resolved Decisions (2026-04-07, SJ)

1. **Batch API default:** **Real-time API is the default.** `--batch` flag available for cost-conscious users with large datasets. Better UX — instant progress bar. Cost difference on 4K profiles is negligible.

2. **Provider selection:** **No `auto` mode — explicit choice required.** User picks during setup, config must be set. Error with guidance if `LINKEDOUT_EMBEDDING_PROVIDER` is unset. If OpenAI key is present, always leverage OpenAI (including for query-time embeddings).

3. **Nomic model download:** **During setup, synchronous with progress bar.** Download happens right after user picks local provider. `linkedout embed` should never surprise users with a 275MB download.

4. **Failed embeddings location:** **`~/linkedout-data/reports/`** — operation artifact, not a log stream. Consistent with other operation reports.

5. **Dual-column cleanup:** **Defer.** 50MB is negligible. No `--cleanup` flag in v1. Power users can run SQL directly.

6. **HNSW index:** **Include in migration.** Fresh installs = empty table (instant). Upgrades pay a one-time build cost. Required for acceptable query performance.

### Cross-Phase Decisions Affecting This Phase

- **Phase 6 (fresh baseline migration):** The HNSW index creation and dual-column schema will be part of the single fresh baseline migration that replaces the entire Alembic history. Design the schema additions with this in mind — they go into the baseline, not as incremental migrations.
- **Phase 9 (setup flow):** Setup asks user to choose provider explicitly. If local chosen, setup downloads nomic model synchronously before proceeding to `linkedout embed`.
