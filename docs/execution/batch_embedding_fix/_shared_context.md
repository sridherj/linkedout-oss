# Shared Context: Batch Embedding Fix

## Source Documents
- Plan: `/data/workspace/linkedout-oss/docs/plan/2026-04-13-batch-embedding-fix.collab.md`

## Project Background

`process_batch` in `post_enrichment.py` had a bug where `profile.experiences` was accessed on a `CrawledProfileEntity` — but that entity has no `experiences` relationship. This caused batch embeddings to silently fail (caught by a bare `except Exception`). The bug fix has already been applied: the code now queries `ExperienceEntity` directly via SQLAlchemy.

The remaining work is test-side only:
1. Harden existing mocks with `create_autospec` so attribute-access bugs like this are caught at test time
2. Add a new `TestProcessBatch` class with 10 tests covering the `process_batch()` method

## Codebase Conventions

- **Repo:** `/data/workspace/linkedout-oss`
- **Test runner:** `cd backend && python -m pytest tests/unit/enrichment_pipeline/test_post_enrichment.py -v`
- **Mock style:** Use `create_autospec(EntityClass, instance=True, spec_set=True)` for all entity mocks
- **Test organization:** One test class per logical unit, methods prefixed with `test_`
- **Imports:** Tests import from `linkedout.*` and `utilities.*` packages

## Key File Paths

| File | Role |
|------|------|
| `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` | Service under test — `process_batch()` and `process_enrichment_result()` |
| `backend/tests/unit/enrichment_pipeline/test_post_enrichment.py` | Test file to modify (only file changed by this plan) |
| `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py` | `CrawledProfileEntity` — the entity to autospec |
| `backend/src/linkedout/experience/entities/experience_entity.py` | `ExperienceEntity` — used in experience queries |
| `backend/src/utilities/llm_manager/embedding_provider.py` | `EmbeddingProvider` and `build_embedding_text` |
| `backend/src/utilities/llm_manager/embedding_factory.py` | `get_embedding_column_name` — imported locally inside `process_batch` |
| `backend/src/shared/utils/apify_archive.py` | `append_apify_archive_batch` — archive step |

## Data Schemas & Contracts

### `process_batch()` signature
```python
def process_batch(
    self,
    results: list[tuple[str, str, dict]],       # [(profile_id, linkedin_url, apify_data)]
    enrichment_event_ids: dict[str, str],         # {linkedin_url: event_id}
    skip_embeddings: bool = False,
    source: str = 'bulk_enrichment',
    redirects: dict[str, str] | None = None,
) -> tuple[int, int]:                             # (enriched_count, failed_count)
```

### `process_batch()` internal flow
1. Temporarily sets `self._embedding_provider = None`
2. Loops over results, calling `self.process_enrichment_result()` per profile
3. Restores `self._embedding_provider`
4. If embeddings enabled: queries each enriched profile + experiences, builds text, calls `embed()`, writes vectors
5. Archives successful entries via `append_apify_archive_batch()`

### Embedding step detail (Step 2 of process_batch)
Per profile, two sequential `session.execute()` calls:
1. `select(CrawledProfileEntity).where(id == profile_id)` → `.scalar_one_or_none()` → profile or None
2. `select(ExperienceEntity).where(crawled_profile_id == profile_id)` → `.scalars().all()` → list of experiences

## Pre-Existing Decisions
- Bug fix is already applied — do NOT modify `post_enrichment.py`
- All entity mocks must use `create_autospec(..., spec_set=True)` — no bare `MagicMock()` for entities
- Remove `profile.embedding = None` from existing mocks (entity has `embedding_openai`/`embedding_nomic`, not `embedding`)
- `get_embedding_column_name` must be patched at source: `utilities.llm_manager.embedding_factory.get_embedding_column_name`

## Sub-Phase Dependency Summary

| Sub-phase | Type | Depends On | Blocks | Can Parallel With |
|-----------|------|-----------|--------|-------------------|
| SP1: Harden mocks + batch tests | Sub-phase | None | None | — |
