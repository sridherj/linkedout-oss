# SP4: Backend LLM & Embedding Constants Extraction

**Sub-phase:** 4 of 7
**Plan task:** 4D (Backend LLM & Embedding Constants Extraction)
**Dependencies:** SP3 (config.py has been modified — build on it)
**Estimated complexity:** L (largest sub-phase — ~15 config fields, 5 file refactors, dimension validation logic)
**Changes code:** Yes

---

## Objective

Move all LLM model names, embedding dimensions, retry/timeout policies, and batch sizes from scattered locations into the central config via nested pydantic models (`LLMConfig`, `EmbeddingConfig`, `RetryConfig`, etc.).

---

## Steps

### 1. Create nested config models in config.py

Add these models to `backend/src/shared/config/config.py`:

**`LLMConfig(BaseModel)`:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | `str` | `gpt-5.2-2025-12-11` | Primary LLM model name |
| `search_model` | `str` | `gpt-5.4-mini` | Search/lightweight LLM model |
| `timeout_seconds` | `float` | `120.0` | LLM request timeout |
| `retry_max_attempts` | `int` | `3` | Max retry attempts for LLM calls |
| `retry_min_wait` | `float` | `2.0` | Min backoff wait (seconds) |
| `retry_max_wait` | `float` | `30.0` | Max backoff wait (seconds) |
| `rate_limit_rpm` | `int` | `60` | Requests per minute rate limit |
| `prompt_cache_ttl_seconds` | `int` | `300` | Prompt cache TTL |
| `summarize_beyond_n_turns` | `int` | `4` | Conversation turns before summarization |

**`EmbeddingConfig(BaseModel)`:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | `str` | `text-embedding-3-small` | Embedding model name |
| `dimensions` | `int` | `1536` | Embedding vector dimensions |
| `chunk_size` | `int` | `5000` | Records per embedding batch |
| `batch_timeout_seconds` | `int` | `7200` | Batch processing timeout |
| `batch_poll_interval_seconds` | `int` | `30` | Batch status poll interval |

**`ExternalAPIConfig(BaseModel)`:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `retry_max_attempts` | `int` | `3` | Max retry attempts for external APIs |
| `timeout_seconds` | `float` | `30.0` | External API request timeout |

Add to `LinkedOutSettings`:
```python
llm: LLMConfig = LLMConfig()
embedding: EmbeddingConfig = EmbeddingConfig()
external_api: ExternalAPIConfig = ExternalAPIConfig()
```

**Note:** Check if `LinkedOutSettings` already has `embedding_provider`, `embedding_model`, `llm_provider`, `llm_model` fields from Phase 2. If so, consolidate — move them into the nested models and update any existing references. The nested model is the canonical location.

### 2. Add embedding dimension validation

Add a startup validator in `LinkedOutSettings` or `EmbeddingConfig`:
- If `embedding_provider` is `local` (nomic), default dimensions to `768`
- If `embedding_provider` is `openai`, default dimensions to `1536`
- If dimensions are explicitly set by the user, respect that value
- On startup, if the configured dimensions don't match the provider's expected dimensions, log a **WARNING**: "Embedding dimensions (X) don't match expected dimensions for provider Y (Z). Existing embeddings may be incompatible. Run `linkedout embed --force` to re-embed."

### 3. Update `retry_policy.py`

In `backend/src/shared/infra/reliability/retry_policy.py`:
- Replace hardcoded `RetryConfig` instances with values read from config
- The module may define default `RetryConfig` dataclasses/namedtuples. Update them to read from `LLMConfig` and `ExternalAPIConfig` as appropriate.

### 4. Update `timeout_policy.py`

In `backend/src/shared/infra/reliability/timeout_policy.py`:
- Replace hardcoded `TimeoutConfig` instances with values read from config

### 5. Update `embedding_client.py`

In `backend/src/utilities/llm_manager/embedding_client.py`:
- Replace hardcoded model name, dimensions, batch polling interval, and batch timeout with config reads

### 6. Update `generate_embeddings.py`

In `backend/src/dev_tools/generate_embeddings.py`:
- Replace hardcoded chunk size and batch timeout with config reads

### 7. Document pgvector dimension constant

In `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py`:
- The pgvector column dimension (`1536`) is a **schema-level constant** that requires a migration to change
- Do NOT externalize — add a comment explaining this:
  ```python
  # Embedding dimension is fixed at schema level. Changing this requires an Alembic migration
  # to ALTER the pgvector column. This is NOT a runtime-configurable value.
  # See: docs/plan/phase-04-constants-externalization.md (task 4D)
  embedding = Column(Vector(1536))  # matches LINKEDOUT_EMBEDDING_DIMENSIONS default
  ```

### 8. Add LLM/embedding sections to config.yaml template

```yaml
# ── LLM ──────────────────────────────────────────────────
# llm:
#   model: gpt-5.2-2025-12-11            # Primary LLM model
#   search_model: gpt-5.4-mini           # Lightweight model for search
#   timeout_seconds: 120.0               # Request timeout
#   retry_max_attempts: 3                # Max retries on failure
#   rate_limit_rpm: 60                   # Requests per minute
#   prompt_cache_ttl_seconds: 300        # Prompt cache TTL
#   summarize_beyond_n_turns: 4          # Turns before summarization

# ── Embeddings ───────────────────────────────────────────
# embedding:
#   model: text-embedding-3-small        # Embedding model (or nomic-embed-text-v1.5 for local)
#   dimensions: 1536                     # Vector dimensions (768 for nomic, 1536 for OpenAI)
#   chunk_size: 5000                     # Records per batch
#   batch_timeout_seconds: 7200          # Batch processing timeout (2 hours)

# ── External API Defaults ────────────────────────────────
# external_api:
#   retry_max_attempts: 3
#   timeout_seconds: 30.0
```

---

## Verification

- [ ] `LLMConfig`, `EmbeddingConfig`, and `ExternalAPIConfig` models exist in `config.py`
- [ ] `LinkedOutSettings` has `llm`, `embedding`, and `external_api` fields
- [ ] No duplicate fields — if Phase 2 already added `embedding_model`, `llm_model` etc., they're consolidated into nested models
- [ ] `retry_policy.py` reads from config, no hardcoded retry values
- [ ] `timeout_policy.py` reads from config, no hardcoded timeout values
- [ ] `embedding_client.py` reads model name, dimensions, polling from config
- [ ] `generate_embeddings.py` reads chunk size and timeout from config
- [ ] Embedding dimension validation warns on mismatch (check with a test or manual verification)
- [ ] `crawled_profile_entity.py` has a comment documenting the schema-level dimension constant
- [ ] Default values match previously hardcoded values exactly
- [ ] Backend boots without errors with default config
- [ ] Run: `grep -rn "gpt-5\|gpt-4\|text-embedding" backend/src/ --include="*.py" | grep -v config.py | grep -v __pycache__` — zero results

---

## Notes

- This is the largest sub-phase. Read all 5 files before making changes to understand the full picture.
- The `retry_policy.py` and `timeout_policy.py` files may use dataclasses or named constants internally. The goal is that their *default values* come from config, not that the internal structure changes.
- For the embedding dimension validation, use a `model_validator` on `LinkedOutSettings` that runs after all fields are loaded. This lets it see both `embedding_provider` and `embedding.dimensions`.
- Verify that the model names in the table above (`gpt-5.2-2025-12-11`, `gpt-5.4-mini`) match what's actually in the code. Read the actual files.
