# Sub-Phase 2a: OpenAI Embedding Provider

**Phase:** 5 — Embedding Provider Abstraction
**Plan task:** 5B (OpenAI Provider)
**Dependencies:** sp1 (Provider ABC + Config)
**Blocks:** sp3
**Can run in parallel with:** sp2b, sp2c, sp2d

## Objective
Wrap the existing `EmbeddingClient` in an `OpenAIEmbeddingProvider` that implements the `EmbeddingProvider` ABC. Preserve all existing functionality (real-time and Batch API) while conforming to the new interface.

## Context
- Read shared context: `docs/execution/phase-05/_shared_context.md`
- Read plan (5B section): `docs/plan/phase-05-embedding-abstraction.md`
- Read existing embedding client: `backend/src/utilities/llm_manager/embedding_client.py`
- Read ABC (created in sp1): `backend/src/utilities/llm_manager/embedding_provider.py`
- Read config: `backend/src/shared/config/config.py`

## Deliverables

### 1. `backend/src/utilities/llm_manager/openai_embedding_provider.py` (NEW)

Implement `OpenAIEmbeddingProvider(EmbeddingProvider)`:

```python
class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: str | None = None, dimensions: int | None = None):
        # Read model/dimensions from config if not specified
        # Default: model="text-embedding-3-small", dimensions=1536
        # Instantiate internal EmbeddingClient
        ...
```

**ABC method implementations:**
- `embed(texts)` → delegates to `EmbeddingClient.embed_batch()` (real-time API, handles chunking)
- `embed_single(text)` → delegates to `EmbeddingClient.embed_text()`
- `dimension()` → returns configured dimensions (default 1536)
- `model_name()` → returns configured model (default `"text-embedding-3-small"`)
- `estimate_time(count)` → `"~{count // 100} minutes"` for real-time, `"~{count // 1000} minutes"` for Batch API
- `estimate_cost(count)` → estimate based on ~500 tokens/profile, OpenAI pricing (~$0.02/1M tokens). Return human-readable string like `"~$0.04 for {count} profiles"`.

**Provider-specific methods (NOT on the ABC):**
- `embed_batch_async(items, ...)` → exposes Batch API methods (`create_batch_file`, `submit_batch`, `poll_batch`)
- `cancel_batch(batch_id)` → exposes `cancel_and_get_results`

**Requirements:**
- Reads `OPENAI_API_KEY` from config (via Phase 2 config system)
- Raises clear error with actionable message if API key not configured
- Logs operations via loguru with `component="cli"`, `operation="embed"`
- Preserve `build_embedding_text()` accessibility — import from the ABC module (sp1 extracted it)

### 2. Update `backend/src/utilities/llm_manager/embedding_client.py`

Minimal changes only:
- Update `build_embedding_text` static method to delegate to the standalone function from sp1's `embedding_provider.py`, maintaining backward compatibility
- Do NOT change the client's API — it remains the internal implementation detail used by `OpenAIEmbeddingProvider`

### 3. Unit Tests: `backend/tests/unit/llm_manager/test_openai_embedding_provider.py` (NEW)

Test with mocked OpenAI API:
- `embed([text])` returns vectors of correct dimension (1536)
- `embed_single(text)` returns a single vector
- `dimension()` returns 1536 (or configured value)
- `model_name()` returns `"text-embedding-3-small"` (or configured value)
- `estimate_time(4000)` returns a reasonable string
- `estimate_cost(4000)` returns a non-None cost estimate string
- Raises clear error if `OPENAI_API_KEY` is not set
- Empty text handling: `embed([])` returns `[]`, `embed([""])` raises or returns zero vector

## Verification
1. `cd backend && uv run python -c "from utilities.llm_manager.openai_embedding_provider import OpenAIEmbeddingProvider; print('import ok')"` succeeds
2. `cd backend && uv run pytest tests/unit/llm_manager/test_openai_embedding_provider.py -v` passes
3. Existing embedding client tests still pass (no regressions)
4. `cd backend && uv run pytest tests/unit/ -x --timeout=60` — all unit tests pass

## Notes
- The `OpenAIEmbeddingProvider` is a thin wrapper. The real logic stays in `EmbeddingClient`. Don't duplicate code.
- Batch API methods are provider-specific because only OpenAI supports them. They live on the concrete class, not the ABC.
- The existing `generate_embeddings.py` still directly uses `EmbeddingClient` for now — sp3 will update callers.
