# LinkedIn Slug Redirect Fix — Shared Context

**Plan:** `docs/plan/2026-04-13-slug-redirect-fix.collab.md`
**Project root:** `/data/workspace/linkedout-oss`
**Backend root:** `/data/workspace/linkedout-oss/backend`
**Source root:** `/data/workspace/linkedout-oss/backend/src`

## Goal

Fix LinkedIn slug redirect mismatches that cause enrichment failures and wasted Apify spend. When LinkedIn redirects a profile URL to a canonical form (e.g. `vikas-khatana-web-developer` → `vikas-khatana`), the pipeline must match the result, update the URL, and preserve the old URL for import dedup safety.

## Problem Summary

1. `_match_results()` in `bulk_enrichment.py` does exact-match only — redirected URLs don't match
2. Profile stays `has_enriched_data = false` → re-sent to Apify every run → wasted money
3. Naive URL update breaks re-import dedup (CSV still has old URL)

## Key Files

| File | Path | Role |
|------|------|------|
| `bulk_enrichment.py` | `src/linkedout/enrichment_pipeline/bulk_enrichment.py` | `_match_results()` (line 205) and `_process_batch_results()` (line 618) |
| `post_enrichment.py` | `src/linkedout/enrichment_pipeline/post_enrichment.py` | `_update_crawled_profile()` (line 194), `process_batch()` (line 274) |
| `crawled_profile_entity.py` | `src/linkedout/crawled_profile/entities/crawled_profile_entity.py` | Entity definition, 73 lines |
| `service.py` | `src/linkedout/import_pipeline/service.py` | `_run_merge()` (line 261), `_build_connection_lookups()` (line 211) |
| `linkedin_url.py` | `src/shared/utils/linkedin_url.py` | `normalize_linkedin_url()` — slug extraction used by matching |
| `001_baseline.py` | `migrations/versions/001_baseline.py` | Only existing migration |

## Key Functions

### `_match_results(batch_urls, apify_results)` (bulk_enrichment.py:205)
Currently returns `(matched: dict[str, dict], missing: list[str])`. Exact-match only via `normalize_linkedin_url()`. Called by `_process_batch_results()` at line 634.

### `_process_batch_results(...)` (bulk_enrichment.py:618)
Orchestrates matching → processing. Calls `_match_results()`, then for each matched URL calls `service.process_batch()`. Unmatched URLs logged as `missing_from_results` failures.

### `_update_crawled_profile(profile, data)` (post_enrichment.py:194)
Maps Apify fields to entity columns. Does NOT currently handle URL changes.

### `_run_merge(...)` (import_pipeline/service.py:261)
Dedup during import. Builds `existing_profiles` dict keyed by `normalize_linkedin_url(p.linkedin_url)`. Only checks `linkedin_url` — does not check `previous_linkedin_url`.

### `_build_connection_lookups(app_user_id)` (import_pipeline/service.py:211)
Loads connections joined with crawled_profiles. Returns `ConnectionLookupEntry` with `linkedin_url`. Only selects `CrawledProfileEntity.linkedin_url`.

### `normalize_linkedin_url(url)` (linkedin_url.py)
Returns `https://www.linkedin.com/in/<slug>` (lowercase, decoded). Returns None for invalid URLs.

## Dependency Chain

```
SP1 (Loguru Fix)  ─────────────────────────────────────┐
SP2 (Migration + Entity) ──┬── SP3 (Matching + URL Update) ──┬── SP4 (Import Dedup + Spec)
                            └──────────────────────────────────┘
```

SP1 is independent. SP2 must complete before SP3 and SP4. SP3 must complete before SP4.

## Conventions

- All new files get `# SPDX-License-Identifier: Apache-2.0` header
- Logger: loguru with `{}` formatting (NOT `%s`/`%d`)
- Tests: `pytest` with `tmp_path` fixture, mocks via `unittest.mock`
- Existing test files: `tests/unit/enrichment_pipeline/test_bulk_enrichment.py`, `tests/unit/enrichment_pipeline/test_post_enrichment.py`
- Alembic migrations in `backend/migrations/versions/`
- `rapidfuzz` is already a project dependency
