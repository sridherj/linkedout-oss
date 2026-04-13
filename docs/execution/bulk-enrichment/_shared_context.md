# Bulk Enrichment Pipeline — Shared Context

**Plan:** `docs/plan/2026-04-13-bulk-enrichment.collab.md`
**Project root:** `/data/workspace/linkedout-oss`
**Backend root:** `/data/workspace/linkedout-oss/backend`
**Source root:** `/data/workspace/linkedout-oss/backend/src`

## Goal

Replace one-at-a-time sync enrichment with a batched async pipeline. Same code path for 1 profile (extension) or 5000 (CLI).

## Hard Requirements

- **R1: Never Lose Paid Data** — Every byte Apify returns must be persisted to disk (`results/{run_id}.json`) before any other processing. If process crashes, data is recoverable. This applies to successful runs AND failed/aborted/timed-out runs (partial dataset still fetched).
- **R2: Crash Recovery at Any Point** — Pipeline resumable after crash at any stage via append-only JSONL state file. No crash scenario requires re-calling Apify for data already received.
- **R3: Idempotency** — Re-running or resuming produces no duplicates. State file tracks submissions; `PostEnrichmentService` does race-condition re-check; query filter selects only `has_enriched_data = false`.

## API Facts

| Fact | Detail |
|------|--------|
| Async run | `POST /v2/acts/{actorId}/runs` — accepts N URLs in `queries` |
| Result matching | Each dataset item has `linkedinUrl` field — no ordering guarantee |
| Partial results | FAILED/ABORTED/TIMED-OUT runs still have partial data in `defaultDatasetId` |
| `defaultDatasetId` | Allocated at run creation, always present regardless of run status |

## Key Files (Pre-Existing)

| File | Path | Role |
|------|------|------|
| `apify_client.py` | `src/linkedout/enrichment_pipeline/apify_client.py` | Apify HTTP client, key rotation, error hierarchy |
| `post_enrichment.py` | `src/linkedout/enrichment_pipeline/post_enrichment.py` | `PostEnrichmentService.process_enrichment_result()` — per-profile DB writes |
| `profile_enrichment_service.py` | `src/linkedout/crawled_profile/services/profile_enrichment_service.py` | `ProfileEnrichmentService.enrich()` — structured rows, search_vector, embedding |
| `enrich.py` | `src/linkedout/commands/enrich.py` | CLI command — currently serial sync enrichment |
| `settings.py` | `src/shared/config/settings.py` | `EnrichmentConfig` pydantic model |
| `apify_archive.py` | `src/shared/utils/apify_archive.py` | `append_apify_archive()` — single-entry JSONL archive |
| `embedding_progress.py` | `src/utilities/embedding_progress.py` | `EmbeddingProgress` — reference for state file pattern |
| `embedding_provider.py` | `src/utilities/llm_manager/embedding_provider.py` | `EmbeddingProvider` ABC, `build_embedding_text()`, `embed()` (batch), `embed_single()` |

## Key Classes and Methods

### `LinkedOutApifyClient` (apify_client.py)
- `enrich_profile_sync(url)` → single profile, sync, 300s timeout
- `enrich_profiles_async(urls)` → starts async run, returns `run_id`
- `poll_run(run_id)` → polls until SUCCEEDED, raises on FAILED/ABORTED/TIMED-OUT
- `fetch_results(dataset_id)` → returns `list[dict]`

### `KeyHealthTracker` (apify_client.py)
- `next_key()` → round-robin healthy key
- `mark_exhausted(key)` → 402 handling (exists but uncalled)
- `mark_invalid(key)` → 401/403 handling (exists but uncalled)

### Error Hierarchy (apify_client.py)
- `ApifyError` (base) → `ApifyCreditExhaustedError` (402), `ApifyRateLimitError` (429), `ApifyAuthError` (401/403), `AllKeysExhaustedError`

### `PostEnrichmentService` (post_enrichment.py)
- `process_enrichment_result(apify_data, event_id, linkedin_url, source)` — per-profile: archive → race check → update profile → enrich() → update event

### `ProfileEnrichmentService` (profile_enrichment_service.py)
- `enrich(profile_id, request)` — delete+insert rows, search_vector, embedding (if provider given)
- `_generate_embedding(profile, request)` — calls `embed_single()`, logs failures to JSONL

### `EmbeddingProvider` (embedding_provider.py)
- `embed(texts: list[str]) → list[list[float]]` — batch embedding
- `embed_single(text: str) → list[float]` — single embedding
- `build_embedding_text(profile_dict) → str` — constructs embedding input text

## Dependency Chain

```
SP1 (Foundation) → SP2 (Core Pipeline) → SP3 (Integration) → SP4 (Tests)
```

Linear. Each builds on the prior sub-phase's artifacts.

## Conventions

- All new files get `# SPDX-License-Identifier: Apache-2.0` header
- Logger: `get_logger(__name__, component="enrichment")`
- Tests: `pytest` with `tmp_path` fixture, mocks via `unittest.mock`
- Config: Pydantic `BaseModel` in `settings.py`
- Existing test files for reference: `tests/unit/enrichment_pipeline/`, `tests/unit/shared/utils/test_apify_archive.py`
