# Sub-Phase 2b: Local Nomic Embedding Provider

**Phase:** 5 — Embedding Provider Abstraction
**Plan task:** 5C (Local Nomic Provider)
**Dependencies:** sp1 (Provider ABC + Config)
**Blocks:** sp3
**Can run in parallel with:** sp2a, sp2c, sp2d

## Objective
Implement `LocalEmbeddingProvider` using sentence-transformers with nomic-embed-text-v1.5 and ONNX backend for CPU inference. The model loads lazily on first use. Dependencies are optional — the provider gives a clear error if `sentence-transformers` is not installed.

## Context
- Read shared context: `docs/execution/phase-05/_shared_context.md`
- Read plan (5C section): `docs/plan/phase-05-embedding-abstraction.md`
- Read ABC (created in sp1): `backend/src/utilities/llm_manager/embedding_provider.py`
- Read embedding model decision: `docs/decision/2026-04-07-embedding-model-selection.md`
- Read data directory decision: `docs/decision/2026-04-07-data-directory-convention.md`

## Deliverables

### 1. `backend/src/utilities/llm_manager/local_embedding_provider.py` (NEW)

Implement `LocalEmbeddingProvider(EmbeddingProvider)`:

```python
class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: str | None = None):
        # Default model: "nomic-ai/nomic-embed-text-v1.5"
        # Model is NOT loaded here — lazy loading on first embed() call
        self._model_name = model or "nomic-ai/nomic-embed-text-v1.5"
        self._model = None  # loaded lazily
        ...
```

**ABC method implementations:**
- `embed(texts)` → process in batches of 32 via sentence-transformers. Lazy-load model on first call.
- `embed_single(text)` → wraps `embed([text])[0]`
- `dimension()` → returns 768 (fixed for v1 — Matryoshka flexibility deferred)
- `model_name()` → returns `"nomic-embed-text-v1.5"`
- `estimate_time(count)` → estimate based on ~5-10 profiles/second on CPU. E.g., `"~7 minutes for 4,000 profiles"`
- `estimate_cost(count)` → returns `None` (free)

**Lazy model loading:**
```python
def _ensure_model_loaded(self):
    if self._model is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError(
            "Local embedding provider requires 'sentence-transformers' and 'onnxruntime'. "
            "Install with: pip install sentence-transformers onnxruntime"
        )
    # Load with ONNX backend for CPU performance
    # Cache to ~/linkedout-data/models/ (via LINKEDOUT_DATA_DIR config)
    cache_dir = os.path.expanduser(settings.data_dir) + "/models"
    self._model = SentenceTransformer(
        self._model_name,
        backend="onnx",
        model_kwargs={"file_name": "onnx/model_quantized.onnx"},
        cache_folder=cache_dir,
    )
```

**Requirements:**
- No error on `import local_embedding_provider` if sentence-transformers is not installed (lazy import)
- Clear error message if user selects `local` provider but dependencies aren't installed
- Produces 768-dimensional vectors
- ONNX backend used for inference (`onnxruntime`)
- Works without GPU (CPU-only)
- Model downloads to `~/linkedout-data/models/` (configurable via `LINKEDOUT_DATA_DIR`)
- Logs model download progress and embedding operations via loguru with `component="cli"`, `operation="embed"`
- Graceful error if model download fails (network issues) with actionable message

### 2. Update `backend/requirements.txt`

Add optional dependencies (with a comment explaining they're optional):

```
# Optional: local embedding provider (nomic-embed-text-v1.5)
# Install if using LINKEDOUT_EMBEDDING_PROVIDER=local
# sentence-transformers>=3.0.0
# onnxruntime>=1.18.0
```

These are commented out in requirements.txt. The setup flow (Phase 9) will install them conditionally when user picks `local` provider. For now, document the requirement.

Alternatively, if the project uses `pyproject.toml` with extras:
```toml
[project.optional-dependencies]
local-embeddings = ["sentence-transformers>=3.0.0", "onnxruntime>=1.18.0"]
```

Check what the project uses and follow the existing pattern.

### 3. Unit Tests: `backend/tests/unit/llm_manager/test_local_embedding_provider.py` (NEW)

Test with mocked sentence-transformers:
- `dimension()` returns 768
- `model_name()` returns `"nomic-embed-text-v1.5"`
- `estimate_time(4000)` returns reasonable string
- `estimate_cost(4000)` returns `None`
- Lazy loading: model is not loaded on `__init__`, only on first `embed()` call
- Import error handling: when `sentence-transformers` is not installed, importing the module works fine, but calling `embed()` raises `ImportError` with a clear message
- `embed([text])` returns vectors of dimension 768 (mock the model's encode method)
- `embed_single(text)` returns a single 768-dim vector
- `embed([])` returns `[]`
- Empty text handling

## Verification
1. `cd backend && uv run python -c "from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider; print('import ok')"` succeeds (even without sentence-transformers installed)
2. `cd backend && uv run pytest tests/unit/llm_manager/test_local_embedding_provider.py -v` passes
3. `cd backend && uv run pytest tests/unit/ -x --timeout=60` — all unit tests pass

## Notes
- The model is ~275MB. It downloads on first use to `~/linkedout-data/models/`. The setup flow (Phase 9) will handle downloading it during onboarding.
- sentence-transformers handles model caching automatically via `cache_folder` parameter.
- The ONNX quantized model (`model_quantized.onnx`) gives ~2-3x speedup over PyTorch on CPU.
- Matryoshka dimension flexibility (using fewer than 768 dims) is deferred — hardcode 768 for v1.
- Batch size of 32 is the sentence-transformers default. It's reasonable for CPU inference.
