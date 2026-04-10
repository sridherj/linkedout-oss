# Sub-Phase 3: Provider Factory + Update Callers

**Phase:** 5 — Embedding Provider Abstraction
**Plan tasks:** 5D (Provider Factory), 5F (Update Embedding Generation Callers)
**Dependencies:** sp2a (OpenAI Provider), sp2b (Local Provider), sp2c (pgvector Schema)
**Blocks:** sp4
**Can run in parallel with:** sp2d

## Objective
Create the provider factory function that returns the configured embedding provider, then update all code that generates or reads embeddings to use the provider abstraction instead of directly instantiating `EmbeddingClient`.

## Context
- Read shared context: `docs/execution/phase-05/_shared_context.md`
- Read plan (5D + 5F sections): `docs/plan/phase-05-embedding-abstraction.md`
- Read OpenAI provider (created in sp2a): `backend/src/utilities/llm_manager/openai_embedding_provider.py`
- Read Local provider (created in sp2b): `backend/src/utilities/llm_manager/local_embedding_provider.py`
- Read updated entity (from sp2c): `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py`
- Read callers that need updating:
  - `backend/src/linkedout/crawled_profile/services/profile_enrichment_service.py`
  - `backend/src/dev_tools/generate_embeddings.py`
  - `backend/src/linkedout/intelligence/scoring/affinity_scorer.py`
  - `backend/src/linkedout/intelligence/tools/vector_tool.py` (already updated in sp2c for column selection, but verify it uses the factory for embedding queries)

## Deliverables

### 1. `backend/src/utilities/llm_manager/embedding_factory.py` (NEW)

```python
from utilities.llm_manager.embedding_provider import EmbeddingProvider

def get_embedding_provider(provider: str | None = None, model: str | None = None) -> EmbeddingProvider:
    """
    Return configured EmbeddingProvider instance.

    Args:
        provider: "openai" or "local". Defaults to config value.
        model: Override model name. Defaults to provider's default.
    """
    if provider is None:
        from shared.config.config import backend_config
        provider = getattr(backend_config, 'LINKEDOUT_EMBEDDING_PROVIDER', 'openai')
        # Also read model override from config if not specified
        if model is None:
            model = getattr(backend_config, 'LINKEDOUT_EMBEDDING_MODEL', '') or None

    if provider == "openai":
        from utilities.llm_manager.openai_embedding_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider(model=model)
    elif provider == "local":
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider
        return LocalEmbeddingProvider(model=model)
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider!r}. "
            f"Use 'openai' or 'local'. "
            f"Set LINKEDOUT_EMBEDDING_PROVIDER in config.yaml or environment."
        )
```

Requirements:
- Lazy imports (no unnecessary dependency loading — don't import sentence-transformers when provider is openai)
- Clear error for unknown provider names
- Reads defaults from Phase 2 config system
- Config is read once per call (not cached — allows runtime config changes)

### 2. Update `backend/src/utilities/llm_manager/__init__.py`

Export the factory and ABC:
```python
from utilities.llm_manager.embedding_factory import get_embedding_provider
from utilities.llm_manager.embedding_provider import EmbeddingProvider
```

### 3. Update `backend/src/linkedout/crawled_profile/services/profile_enrichment_service.py`

**Current** (~line 41):
```python
self._embedding_client = embedding_client
```

**Change:**
- Replace `Optional[EmbeddingClient]` with `Optional[EmbeddingProvider]` in `__init__`
- If no provider passed, use `get_embedding_provider()` to get the configured one
- When writing embeddings, write to the correct column based on provider:
  - `provider.model_name().startswith("nomic")` → `embedding_nomic`
  - Otherwise → `embedding_openai`
- Set metadata columns: `embedding_model`, `embedding_dim`, `embedding_updated_at`

**Helper function** (add to service or as standalone utility):
```python
def get_embedding_column_name(provider: EmbeddingProvider) -> str:
    """Return the entity column name for the given provider."""
    if "nomic" in provider.model_name().lower():
        return "embedding_nomic"
    return "embedding_openai"
```

### 4. Update `backend/src/dev_tools/generate_embeddings.py`

This is the biggest change — this file becomes the implementation behind `linkedout embed`.

**Changes:**
- Replace `client = EmbeddingClient()` with `provider = get_embedding_provider(provider_name)`
- Where `--provider` CLI flag is passed, use it to override config
- Write to correct column: `embedding_openai` or `embedding_nomic` (not just `embedding`)
- When `--force` is used, clear the target column for all rows and re-embed
- Batch API mode remains OpenAI-specific (check `isinstance(provider, OpenAIEmbeddingProvider)` before offering batch mode)
- Update the `update_embeddings()` function to accept the column name:
  ```python
  def update_embeddings(results, column_name="embedding_openai", model_name="", dimension=0, batch_size=500):
      # UPDATE crawled_profile SET {column_name} = ..., embedding_model = ..., embedding_dim = ..., embedding_updated_at = NOW() WHERE id = :pid
  ```
- Update `fetch_profiles_needing_embeddings()` to query the correct column:
  ```python
  # WHERE has_enriched_data = TRUE AND {column_name} IS NULL
  ```

### 5. Update `backend/src/linkedout/intelligence/scoring/affinity_scorer.py`

**Current** (~line 24 area): The affinity scorer likely references `embedding` somewhere for similarity calculation.

**Change:**
- Find where embedding similarity is computed
- Read from the active provider's column (`embedding_openai` or `embedding_nomic`)
- If profile has no embedding for the active provider, skip embedding component of affinity (don't fail, just score 0 for that component)
- Use the same `get_embedding_column_name()` helper

### 6. Verify `vector_tool.py` Integration

sp2c already updated `vector_tool.py` to query the correct column. Verify:
- The column selection logic works end-to-end
- Query-time embedding uses the factory to get the provider for `embed_text(query)`
- Update `search_profiles()` to use `get_embedding_provider()` instead of `EmbeddingClient()`:
  ```python
  # Old:
  client = embedding_client or EmbeddingClient()
  query_embedding = client.embed_text(query)
  # New:
  provider = embedding_provider or get_embedding_provider()
  query_embedding = provider.embed_single(query)
  ```

### 7. Unit Tests

**`backend/tests/unit/llm_manager/test_embedding_factory.py`** (NEW):
- Returns `OpenAIEmbeddingProvider` when config is `"openai"`
- Returns `LocalEmbeddingProvider` when config is `"local"`
- Explicit `provider` parameter overrides config
- Unknown provider raises `ValueError` with helpful message
- `model` parameter is passed through to provider

**Update existing tests** that reference `EmbeddingClient` directly:
- Verify no test creates `EmbeddingClient()` directly outside of the OpenAI provider tests
- Update test fixtures/mocks if they reference the old `embedding` column name

## Verification
1. `cd backend && uv run python -c "from utilities.llm_manager import get_embedding_provider; p = get_embedding_provider('openai'); print(p.model_name(), p.dimension())"` prints `text-embedding-3-small 1536`
2. `cd backend && uv run pytest tests/unit/llm_manager/test_embedding_factory.py -v` passes
3. No direct `EmbeddingClient()` instantiation outside of `openai_embedding_provider.py` and `embedding_client.py`:
   ```bash
   grep -r "EmbeddingClient()" backend/src/ --include="*.py" | grep -v "openai_embedding_provider\|embedding_client\|test_"
   # Should return empty
   ```
4. No references to the old `embedding` column (should all be `embedding_openai` or `embedding_nomic`):
   ```bash
   grep -rn "\.embedding[^_]" backend/src/linkedout/ --include="*.py" | grep -v "embedding_openai\|embedding_nomic\|embedding_model\|embedding_dim\|embedding_updated\|embedding_client\|embedding_provider\|embedding_factory\|embedding_progress"
   # Should return empty or only false positives
   ```
5. `cd backend && uv run pytest tests/unit/ -x --timeout=60` — all unit tests pass

## Notes
- This sub-phase has the most cross-cutting changes. Every file that touches embeddings gets updated.
- The `get_embedding_column_name()` helper should be consistent everywhere — define it once, import it.
- After this sub-phase, the abstraction is complete. No code outside `openai_embedding_provider.py` should know about `EmbeddingClient` directly.
- The `profile_enrichment_service.py` change is smaller than it looks — it already accepts an optional client. We're just changing the type.
