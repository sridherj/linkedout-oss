# Fix: Batch embedding failure + add test coverage

## Context

`process_batch` in `post_enrichment.py` has a bug at line 362 where `profile.experiences` is accessed on a `CrawledProfileEntity` — but that entity has no `experiences` relationship. This means **batch embeddings have never worked** since the code was written. The `except Exception` at line 384 silently catches it, logs an error, and moves on.

This is a money-losing bug: Apify enrichment costs per profile, and embedding API calls cost per batch. We pay for enrichment but don't get searchable vectors out of it.

The unit tests missed it because:
1. `_make_profile_mock()` uses bare `MagicMock()` (no spec) — any attribute access silently succeeds
2. The batch embedding path in `process_batch()` has **zero test coverage**

## Changes

### 1. Bug fix (already applied, needs import)

**File:** `backend/src/linkedout/enrichment_pipeline/post_enrichment.py`

- Add import: `from linkedout.experience.entities.experience_entity import ExperienceEntity` (done)
- Replace `profile.experiences` with explicit query (done):
  ```python
  experiences = self._session.execute(
      select(ExperienceEntity).where(
          ExperienceEntity.crawled_profile_id == profile_id
      )
  ).scalars().all()
  ```

### 2. Harden existing mocks with `create_autospec`

**File:** `backend/tests/unit/enrichment_pipeline/test_post_enrichment.py`

Both `_make_profile_mock()` methods (line 90 in `TestPostEnrichmentService`, line 242 in `TestURLRedirectUpdate`) use bare `MagicMock()`. Switch to `create_autospec(CrawledProfileEntity, instance=True, spec_set=True)`.

Note: the existing mock sets `profile.embedding = None` but the entity has `embedding_openai`/`embedding_nomic`, not `embedding`. Remove that line since no test asserts on it and it would fail with `spec_set=True`.

Also harden the inline `MagicMock()` in `test_cache_hit_skips_enrichment` (line 191) — it creates its own profile mock outside `_make_profile_mock()`. Switch to `create_autospec(CrawledProfileEntity, instance=True, spec_set=True)` for consistency.

### 3. New test class: `TestProcessBatch`

**File:** `backend/tests/unit/enrichment_pipeline/test_post_enrichment.py`

Tests for `process_batch()` — the method with 3 steps:
1. Per-profile DB writes via `process_enrichment_result()` (embedding disabled)
2. Batch embedding (query profiles + experiences, build text, embed, write vectors)
3. Batch JSONL archive

**Mocking strategy:**
- `process_enrichment_result` — patch on the service instance (it's already tested elsewhere; we want to isolate `process_batch` logic)
- `session.execute` — mock to return `create_autospec` entity mocks for profile/experience queries. **Note:** Step 2 makes 2 sequential `execute` calls per profile:
    1. `select(CrawledProfileEntity).where(id == profile_id)` → `.scalar_one_or_none()` returns profile or `None`
    2. `select(ExperienceEntity).where(crawled_profile_id == profile_id)` → `.scalars().all()` returns list of experiences

    Use `session.execute.side_effect` to return different result objects per call. Example pattern:
    ```python
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = mock_profile
    exp_result = MagicMock()
    exp_result.scalars.return_value.all.return_value = [mock_exp]
    session.execute.side_effect = [profile_result, exp_result]  # per profile
    ```
- `embedding_provider` — `create_autospec(EmbeddingProvider, instance=True, spec_set=True)`
- `build_embedding_text` — patch at module level to control return values
- `get_embedding_column_name` — patch at **source module** `utilities.llm_manager.embedding_factory.get_embedding_column_name` (NOT `linkedout.enrichment_pipeline.post_enrichment.get_embedding_column_name` — it's a local import inside `process_batch` at line 350, so the module-level name doesn't exist). Return `'embedding_openai'`.
- `append_apify_archive_batch` — patch at module level

**Tests (10):**

| # | Test name | Step | What it verifies |
|---|-----------|------|-----------------|
| 1 | `test_happy_path_returns_counts_and_embeds` | All | 2 profiles succeed → (2,0), embed called with 2 texts, archive called |
| 2 | `test_partial_failure_counts` | 1 | 1 succeeds, 1 raises → (1,1), only 1 gets embedding |
| 3 | `test_skip_embeddings_flag` | 2 | `skip_embeddings=True` → embed never called, counts still correct |
| 4 | `test_no_embedding_provider` | 2 | provider is `None` → embed step skipped entirely |
| 5 | `test_embedding_includes_experiences` | 2 | Experience query returns rows → `build_embedding_text` receives correct exp_dicts |
| 6 | `test_embedding_with_no_experiences` | 2 | Empty experience list → still builds text from name/headline/about |
| 7 | `test_embedding_failure_logs_and_continues` | 2 | `embed()` raises → `_log_failed_embedding_entry` called per profile, method doesn't crash |
| 8 | `test_profile_missing_at_embedding_time` | 2 | `scalar_one_or_none` returns `None` → skipped gracefully |
| 9 | `test_empty_embedding_text_skipped` | 2 | Profile with all-None fields → not sent to embedding provider |
| 10 | `test_archive_only_successful_profiles` | 3 | 1 success + 1 failure → archive batch has 1 entry |

All entity mocks use `create_autospec(..., spec_set=True)`.

## Files to modify

1. `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` — import added (done)
2. `backend/tests/unit/enrichment_pipeline/test_post_enrichment.py` — harden mocks + add `TestProcessBatch`

## Verification

```bash
cd backend && python -m pytest tests/unit/enrichment_pipeline/test_post_enrichment.py -v
```

Confirm:
- All existing tests still pass (no regressions from autospec change)
- All 10 new tests pass
- Test #5 specifically validates that the experience query works correctly (would have caught the original bug)
