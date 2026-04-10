# Sub-Phase 1: Foundation — Provider ABC + Config Wiring

**Phase:** 5 — Embedding Provider Abstraction
**Plan tasks:** 5A (Provider Interface), 5I (Config Wiring)
**Dependencies:** Phase 2 (Env & Config) must be complete
**Blocks:** sp2a, sp2b
**Can run in parallel with:** sp2c, sp2d

## Objective
Create the `EmbeddingProvider` ABC that all embedding providers will implement, and ensure the config system has the embedding provider fields wired. This is the foundational contract that decouples the codebase from any specific embedding API.

## Context
- Read shared context: `docs/execution/phase-05/_shared_context.md`
- Read plan (5A + 5I sections): `docs/plan/phase-05-embedding-abstraction.md`
- Read existing config: `backend/src/shared/config/config.py`
- Read config decision: `docs/decision/env-config-design.md`
- Read existing embedding client (for API surface reference): `backend/src/utilities/llm_manager/embedding_client.py`

## Deliverables

### 1. `backend/src/utilities/llm_manager/embedding_provider.py` (NEW)

Define the `EmbeddingProvider` ABC with these 6 abstract methods:

```python
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

Requirements:
- No external dependencies in this file (pure interface)
- Complete type hints on all methods
- Docstrings explaining the contract for each method
- Keep `build_embedding_text()` as a standalone function in this file (shared utility used by all providers, extracted from `EmbeddingClient.build_embedding_text()`)

### 2. Config Wiring Verification

Check that `backend/src/shared/config/config.py` has these fields (Phase 2 may have already added them):

| Field | Env Var | Default | Description |
|-------|---------|---------|-------------|
| `embedding_provider` | `LINKEDOUT_EMBEDDING_PROVIDER` | `"openai"` | `"openai"` or `"local"` |
| `embedding_model` | `LINKEDOUT_EMBEDDING_MODEL` | `""` (empty = provider default) | Override model name |

If these fields exist: verify env var override works and YAML mapping is correct.
If these fields are missing: add them to the pydantic-settings model.

Add startup validation:
- If `embedding_provider` is not `"openai"` or `"local"`, raise a clear error.
- If `embedding_provider` is `"openai"` and `OPENAI_API_KEY` is not configured, log a warning (not an error — key may only be needed at embed time).
- No `"auto"` mode. If the field is empty/unset, default to `"openai"`.

### 3. Unit Test: `backend/tests/unit/llm_manager/test_embedding_provider.py` (NEW)

Test the ABC contract:
- Verify `EmbeddingProvider` cannot be instantiated directly (it's abstract)
- Create a minimal concrete subclass that implements all 6 methods, verify it instantiates correctly
- Verify `build_embedding_text()` produces expected output for sample profile dicts (port existing test coverage if any)

### 4. Unit Test: `backend/tests/unit/test_config_embedding.py` (NEW)

Test config wiring:
- `LINKEDOUT_EMBEDDING_PROVIDER=local` env var sets provider to "local"
- `embedding_provider: local` in YAML sets provider to "local"
- Env var overrides YAML value
- Invalid provider value raises clear error

## Verification
1. `cd backend && uv run python -c "from utilities.llm_manager.embedding_provider import EmbeddingProvider; print('ABC imported')"` succeeds
2. `cd backend && uv run python -c "from utilities.llm_manager.embedding_provider import build_embedding_text; print(build_embedding_text({'full_name': 'Test', 'headline': 'Engineer'}))"` prints `Test | Engineer`
3. `cd backend && uv run pytest tests/unit/llm_manager/test_embedding_provider.py -v` passes
4. `cd backend && uv run pytest tests/unit/test_config_embedding.py -v` passes
5. Existing tests still pass: `cd backend && uv run pytest tests/unit/ -x --timeout=60`

## Notes
- `build_embedding_text()` is currently a `@staticmethod` on `EmbeddingClient`. Extract it as a standalone function in `embedding_provider.py` (or a shared utils module). Both the ABC and the existing `EmbeddingClient` should use the same function. Update `EmbeddingClient.build_embedding_text` to delegate to the new standalone function for backward compatibility.
- The config changes here are minimal — Phase 2 likely already created most of the config infrastructure. This task verifies and fills gaps.
