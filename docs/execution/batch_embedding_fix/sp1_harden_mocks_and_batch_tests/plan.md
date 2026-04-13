# Sub-phase 1: Harden Existing Mocks + Add TestProcessBatch

> **Pre-requisite:** Read `docs/execution/batch_embedding_fix/_shared_context.md` before starting this sub-phase.
> **Working directory:** `/data/workspace/linkedout-oss`

## Objective

Harden the existing test mocks in `test_post_enrichment.py` to use `create_autospec` (preventing silent attribute-access bugs like the one that hid the batch embedding failure), then add comprehensive test coverage for `process_batch()` via a new `TestProcessBatch` class with 10 tests.

## Dependencies
- **Requires completed:** None
- **Assumed codebase state:** Bug fix in `post_enrichment.py` is already applied (ExperienceEntity query replaces `profile.experiences`)

## Scope

**In scope:**
- Switch 3 `MagicMock()` usages to `create_autospec(CrawledProfileEntity, instance=True, spec_set=True)` in existing test classes
- Remove `profile.embedding = None` from `_make_profile_mock()` methods (would fail with `spec_set=True`)
- Add new `TestProcessBatch` class with 10 tests

**Out of scope (do NOT do these):**
- Modifying `post_enrichment.py` — the bug fix is already applied
- Changing `TestEmbeddingTextFormat` — it tests `EmbeddingClient`, not entity mocks
- Adding tests beyond the 10 specified in the plan

## Files to Create/Modify

| File | Action | Current State |
|------|--------|---------------|
| `backend/tests/unit/enrichment_pipeline/test_post_enrichment.py` | Modify | Contains 3 test classes, 12 tests. Uses bare `MagicMock()` for profile entities. |

## Detailed Steps

### Step 1.1: Update imports

Add `create_autospec` to the existing `unittest.mock` import and add entity imports:

```python
from unittest.mock import MagicMock, create_autospec, patch

from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.enrichment_pipeline.post_enrichment import PostEnrichmentService
```

Also add these imports needed by TestProcessBatch (can go at top or inside the class):

```python
from linkedout.experience.entities.experience_entity import ExperienceEntity
from utilities.llm_manager.embedding_provider import EmbeddingProvider
```

### Step 1.2: Harden `TestPostEnrichmentService._make_profile_mock()` (line ~90)

**Before:**
```python
def _make_profile_mock(self):
    """Create a profile mock with string attributes for search_vector compatibility."""
    profile = MagicMock()
    profile.has_enriched_data = False
    profile.id = 'cp_001'
    profile.full_name = None
    profile.headline = None
    profile.about = None
    profile.search_vector = None
    profile.embedding = None
    return profile
```

**After:**
```python
def _make_profile_mock(self):
    """Create a profile mock with string attributes for search_vector compatibility."""
    profile = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
    profile.has_enriched_data = False
    profile.id = 'cp_001'
    profile.full_name = None
    profile.headline = None
    profile.about = None
    profile.search_vector = None
    return profile
```

Key changes:
- `MagicMock()` → `create_autospec(CrawledProfileEntity, instance=True, spec_set=True)`
- Removed `profile.embedding = None` (entity has `embedding_openai`/`embedding_nomic`, not `embedding` — would raise `AttributeError` with `spec_set=True`)

### Step 1.3: Harden inline mock in `test_cache_hit_skips_enrichment` (line ~191)

**Before:**
```python
def test_cache_hit_skips_enrichment(self):
    session = MagicMock()
    profile = MagicMock()
    profile.has_enriched_data = True
    profile.last_crawled_at = datetime.now(timezone.utc) - timedelta(days=30)
    profile.id = 'cp_001'
```

**After:**
```python
def test_cache_hit_skips_enrichment(self):
    session = MagicMock()
    profile = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
    profile.has_enriched_data = True
    profile.last_crawled_at = datetime.now(timezone.utc) - timedelta(days=30)
    profile.id = 'cp_001'
```

### Step 1.4: Harden `TestURLRedirectUpdate._make_profile_mock()` (line ~242)

**Before:**
```python
def _make_profile_mock(self, linkedin_url='https://www.linkedin.com/in/johndoe'):
    profile = MagicMock()
    profile.has_enriched_data = False
    profile.id = 'cp_001'
    profile.linkedin_url = linkedin_url
    profile.previous_linkedin_url = None
    profile.full_name = None
    profile.headline = None
    profile.about = None
    profile.search_vector = None
    profile.embedding = None
    return profile
```

**After:**
```python
def _make_profile_mock(self, linkedin_url='https://www.linkedin.com/in/johndoe'):
    profile = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
    profile.has_enriched_data = False
    profile.id = 'cp_001'
    profile.linkedin_url = linkedin_url
    profile.previous_linkedin_url = None
    profile.full_name = None
    profile.headline = None
    profile.about = None
    profile.search_vector = None
    return profile
```

### Step 1.5: Run existing tests — verify no regressions

```bash
cd /data/workspace/linkedout-oss/backend && python -m pytest tests/unit/enrichment_pipeline/test_post_enrichment.py -v
```

All 12 existing tests must pass. If any fail due to `spec_set=True` catching attribute access on non-existent attributes, that reveals a real mock-vs-entity mismatch — fix the test (not the spec).

### Step 1.6: Add `TestProcessBatch` class

Add a new test class at the end of the file (after `TestEmbeddingTextFormat`). This class tests `process_batch()` which has 3 internal steps:
1. Per-profile DB writes via `process_enrichment_result()` (with embedding disabled)
2. Batch embedding (query profiles + experiences, build text, embed, write vectors)
3. Batch JSONL archive

**Mocking strategy:**
- `process_enrichment_result` — patch on the service instance (already tested elsewhere)
- `session.execute` — mock to return `create_autospec` entity mocks
- `embedding_provider` — `create_autospec(EmbeddingProvider, instance=True, spec_set=True)`
- `build_embedding_text` — patch at `linkedout.enrichment_pipeline.post_enrichment.build_embedding_text`
- `get_embedding_column_name` — patch at **source module**: `utilities.llm_manager.embedding_factory.get_embedding_column_name`
- `append_apify_archive_batch` — patch at `linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch`

**For the embedding step's `session.execute` calls:** Each profile triggers 2 sequential calls:
1. `select(CrawledProfileEntity)...` → result with `.scalar_one_or_none()` returning profile mock
2. `select(ExperienceEntity)...` → result with `.scalars().all()` returning experience list

Use `session.execute.side_effect` with a list of result mocks:
```python
profile_result = MagicMock()
profile_result.scalar_one_or_none.return_value = mock_profile
exp_result = MagicMock()
exp_result.scalars.return_value.all.return_value = [mock_exp]
session.execute.side_effect = [profile_result, exp_result]  # per profile
```

**The 10 tests:**

| # | Test name | Step | What it verifies |
|---|-----------|------|-----------------|
| 1 | `test_happy_path_returns_counts_and_embeds` | All | 2 profiles succeed → (2,0), embed called with 2 texts, archive called |
| 2 | `test_partial_failure_counts` | 1 | 1 succeeds, 1 raises → (1,1), only 1 gets embedding |
| 3 | `test_skip_embeddings_flag` | 2 | `skip_embeddings=True` → embed never called, counts still correct |
| 4 | `test_no_embedding_provider` | 2 | provider is `None` → embed step skipped entirely |
| 5 | `test_embedding_includes_experiences` | 2 | Experience query returns rows → `build_embedding_text` receives correct `exp_dicts` |
| 6 | `test_embedding_with_no_experiences` | 2 | Empty experience list → still builds text from name/headline/about |
| 7 | `test_embedding_failure_logs_and_continues` | 2 | `embed()` raises → `_log_failed_embedding_entry` called per profile, method doesn't crash |
| 8 | `test_profile_missing_at_embedding_time` | 2 | `scalar_one_or_none` returns `None` → skipped gracefully |
| 9 | `test_empty_embedding_text_skipped` | 2 | Profile with all-None fields → not sent to embedding provider |
| 10 | `test_archive_only_successful_profiles` | 3 | 1 success + 1 failure → archive batch has 1 entry |

**Important implementation notes for each test:**

**Test 1 (happy path):** Set up 2 profiles in `results`. Patch `process_enrichment_result` as a no-op. Set up `session.execute.side_effect` with 4 result mocks (2 per profile: profile query + experience query). `build_embedding_text` returns non-empty strings. `embed()` returns 2 vectors. Assert `(2, 0)` returned, `embed` called once with 2 texts, `append_apify_archive_batch` called with 2 entries.

**Test 2 (partial failure):** Patch `process_enrichment_result` with `side_effect = [None, Exception("boom")]`. The second profile raises during Step 1. Assert `(1, 1)` returned. Session.execute side_effect should only have 2 entries (1 profile query + 1 exp query) since only 1 profile succeeds.

**Test 3 (skip embeddings):** Call with `skip_embeddings=True`. Assert `embed` never called. Assert `(N, 0)` returned.

**Test 4 (no provider):** Create service with `embedding_provider=None`. Assert embed step skipped entirely (no `session.execute` calls for profile lookup in the embedding step).

**Test 5 (experiences included):** Set up experience mock with `company_name='Acme'` and `position='Engineer'`. Assert `build_embedding_text` called with a dict containing `'experiences': [{'company_name': 'Acme', 'title': 'Engineer'}]`.

**Test 6 (no experiences):** Experience query returns empty list. Assert `build_embedding_text` still called with `'experiences': []`.

**Test 7 (embedding failure):** `embed()` raises `RuntimeError`. Assert method returns without crashing. Assert `_log_failed_embedding_entry` called for each profile.

**Test 8 (profile missing):** `scalar_one_or_none` returns `None` for one profile. Assert it's skipped — no `build_embedding_text` call for that profile.

**Test 9 (empty text):** `build_embedding_text` returns `'   '` (whitespace-only). Assert that profile is not added to the embed batch.

**Test 10 (archive):** 1 success + 1 failure. Assert `append_apify_archive_batch` called with 1 entry (only the successful profile).

### Step 1.7: Run all tests

```bash
cd /data/workspace/linkedout-oss/backend && python -m pytest tests/unit/enrichment_pipeline/test_post_enrichment.py -v
```

## Verification

### Automated Tests (permanent)
- All 12 existing tests in `TestPostEnrichmentService`, `TestURLRedirectUpdate`, and `TestEmbeddingTextFormat` pass
- All 10 new tests in `TestProcessBatch` pass
- Total: 22 tests passing

### Validation Scripts (temporary)
```bash
# Verify autospec catches invalid attributes (sanity check)
cd /data/workspace/linkedout-oss/backend && python -c "
from unittest.mock import create_autospec
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
p = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
try:
    _ = p.experiences
    print('FAIL: spec_set did not catch .experiences')
except AttributeError:
    print('OK: spec_set correctly blocks .experiences')
"
```

### Manual Checks
```bash
# Count test methods to confirm 22 total
cd /data/workspace/linkedout-oss/backend && python -m pytest tests/unit/enrichment_pipeline/test_post_enrichment.py --collect-only -q
```

### Success Criteria
- [ ] All 12 pre-existing tests pass (no regressions from autospec change)
- [ ] All 10 new `TestProcessBatch` tests pass
- [ ] `create_autospec` with `spec_set=True` is used for all entity mocks (no bare `MagicMock()` for entities)
- [ ] No `profile.embedding` assignments remain in mock helpers
- [ ] Test #5 specifically validates the experience query works correctly

## Execution Notes

- **`process_enrichment_result` uses `session.begin_nested()`**: In the mock, `session.begin_nested()` needs to return a context manager. `MagicMock()` handles this automatically, but be aware if you see context manager errors.
- **`get_embedding_column_name` import location**: This is imported *inside* `process_batch()` at runtime (line 350 of `post_enrichment.py`). Patch at the **source module** `utilities.llm_manager.embedding_factory.get_embedding_column_name`, NOT at `linkedout.enrichment_pipeline.post_enrichment.get_embedding_column_name` (which doesn't exist as a module-level name).
- **`self._embedding_provider` swap**: `process_batch` temporarily sets `self._embedding_provider = None` then restores it. Tests that check the embedding step need to ensure the provider is set *before* calling `process_batch` — the method restores it internally.
- **`spec_set=True` strictness**: If a test sets an attribute that doesn't exist on the entity, it will raise `AttributeError`. This is intentional — it catches mock/entity drift. Fix by using real attribute names from the entity class.
