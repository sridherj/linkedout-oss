# LinkedIn Slug Redirect Fix

**Date:** 2026-04-13
**Status:** Draft
**Depends on:** v0.4.0 bulk enrichment pipeline (landed)

## Problem

### The bug

LinkedIn periodically resolves profile slugs to a canonical form. Examples observed in production:

| DB URL (from CSV import) | Apify-returned URL | Cause |
|---|---|---|
| `vikas-khatana-web-developer` | `vikas-khatana` | Suffix stripped |
| `hiral-talsaniya-🥇-6448b5173` | `hiraltalsaniya` | Emoji + suffix stripped |
| `dhirendra-singh-%e3%83%87%e3%82%a3%e3%83%ab-578b761ba` | `dhirendra-singh-ディル-578b761ba` | Percent-encoding only (fixed in a9a8ace) |

When Apify returns a redirected URL, `_match_results()` in `bulk_enrichment.py` can't match the result back to the input URL. The profile is marked "failed (missing_from_results)" even though Apify successfully scraped it.

### The infinite loop

1. `linkedout enrich` queries profiles with `has_enriched_data = false`
2. Sends `vikas-khatana-web-developer` to Apify → pays $0.004
3. Apify returns data with `linkedinUrl: vikas-khatana`
4. `_match_results` can't match → marks profile as failed
5. Profile stays `has_enriched_data = false`
6. Next `linkedout enrich` run → repeats from step 2, paying Apify again

We're paying for data we already received but can't use. Raw results are saved to disk (R1 compliance), but the pipeline can't associate them with the right profile.

### The re-import trap

Naive fix: just update `linkedin_url` in the DB to the Apify canonical URL. But this breaks re-import:

1. User imports `connections.csv` → profile created with `linkedin_url = vikas-khatana-web-developer`
2. Enrichment updates DB to `linkedin_url = vikas-khatana`
3. User re-runs `linkedout setup` (re-imports same CSV)
4. Import pipeline normalizes CSV URL → `vikas-khatana-web-developer`
5. Looks up `existing_profiles_by_url` → **no match** (DB now has `vikas-khatana`)
6. Creates duplicate profile with old URL → triggers enrichment again → wastes money

The import dedup in `_run_merge()` (`import_pipeline/service.py:272-278`) builds its lookup from `CrawledProfileEntity.linkedin_url` only. If we update the URL without preserving the old one, re-import creates duplicates.

### Scope

Affects ~2-5% of profiles in a typical import. Percent-encoding mismatches (a larger set) were already fixed in commit a9a8ace.

## Solution

### 1. Fix loguru formatting (already in working tree)

17 logger calls across `bulk_enrichment.py` (14) and `post_enrichment.py` (3) use `%s`/`%d` (stdlib style) but the logger is loguru (`{}` style). Logs show literal `%d`, `%s` instead of values. Fix all in one commit.

### 2. Redirect-aware matching in `_match_results`

After the exact-match pass, pair remaining unmatched inputs with unmatched Apify results. Since Apify only returns data for URLs we sent, unmatched results **must** be redirected versions of unmatched inputs.

**Pairing strategy — rapidfuzz greedy matching:**

After the exact-match pass, collect unmatched inputs and unmatched Apify results. Extract the slug (everything after `/in/`) from both sides, then:

1. Compute `rapidfuzz.fuzz.ratio(input_slug, result_slug)` for all unmatched-input × unmatched-result pairs
2. Sort all pairs by similarity (highest first)
3. Greedily assign: pick the highest-similarity pair, remove both from candidates, repeat
4. Only pair if similarity ≥ 60% threshold
5. Remaining unpaired stay as failed

Uses `rapidfuzz` which is already a project dependency (used in import dedup). Handles all observed redirect patterns: suffix stripping (`vikas-khatana-web-developer` → `vikas-khatana`), emoji removal (`hiral-talsaniya-🥇-6448b5173` → `hiraltalsaniya`), and hyphen changes.

With batch size 100 and ~2-5% redirect rate, expect 2-5 redirects per batch — 1-to-1 alone would fail most of the time.

**Return type change:** `_match_results()` returns `(matched, missing, redirects)` where `redirects: dict[str, str]` maps `original_input_url → apify_canonical_url`. This lets the caller know which profiles need URL updates.

### 3. Add `previous_linkedin_url` to CrawledProfileEntity

New nullable column. When enrichment detects a redirect, store the original URL here before updating `linkedin_url`. This preserves the link to the CSV-imported URL.

- Column: `previous_linkedin_url: String(500), nullable=True`
- Index: `ix_cp_prev_linkedin_url` for dedup lookups

### 4. Update `linkedin_url` during post-processing

In `PostEnrichmentService._update_crawled_profile()`: if the Apify-returned `linkedinUrl` (normalized) differs from the profile's current `linkedin_url` (normalized):
1. `profile.previous_linkedin_url = profile.linkedin_url` (preserve old)
2. `profile.linkedin_url = normalize_linkedin_url(apify_url)` (update to canonical)

**Edge case — unique constraint conflict:** Pre-check SELECT for existing profile with the new URL before updating. If found, log a warning and skip the URL update. The profile still gets enriched — just doesn't get the URL updated. (Pre-check is cleaner than catching IntegrityError; tiny race window is harmless.)

### 5. Import dedup checks both URLs

In `import_pipeline/service.py` `_run_merge()`: when building `existing_profiles` dict, also index by `previous_linkedin_url`:

```python
for p in profile_rows:
    norm = normalize_linkedin_url(p.linkedin_url)
    if norm:
        existing_profiles[norm] = p
    prev = normalize_linkedin_url(p.previous_linkedin_url) if p.previous_linkedin_url else None
    if prev and prev not in existing_profiles:
        existing_profiles[prev] = p
```

Same for `_build_connection_lookups()`: load `previous_linkedin_url` so the dedup matcher can find profiles by old URLs.

### 6. Update enrichment spec

Add to `docs/specs/linkedout_enrichment_pipeline.collab.md`:

**New behavior under "Post-Enrichment Processing":**
- **LinkedIn slug redirect handling**: LinkedIn may resolve profile slugs to a different canonical form (e.g. stripping display name suffixes, removing emoji, normalizing hyphens). When Apify returns a `linkedinUrl` that differs from the input URL (after normalization), the system: (a) matches the result to the input via member-ID suffix fallback, (b) updates `linkedin_url` to the Apify canonical URL, and (c) stores the original URL in `previous_linkedin_url` for import dedup safety. The import pipeline checks both `linkedin_url` and `previous_linkedin_url` when deduplicating re-imports.

**New decision:**
- **`previous_linkedin_url` for redirect tracking** — Chose single `previous_linkedin_url` column over JSONB array of aliases or separate alias table. Rationale: LinkedIn redirects are rare (~2-5%) and typically happen once. A single column handles the common case without schema complexity. If a profile redirects multiple times (extremely rare), only the most recent previous URL is preserved.

**Known limitation (document in spec):**
- **Similar-slug collision in fuzzy matching** — If two profiles with similar slugs (e.g. `abhishek-mishra-developer` and `abhishek-mishra1-engineer`) both redirect in the same batch, the rapidfuzz greedy matcher could cross-pair them. This requires: similar slugs + same batch + both redirect — extremely rare in practice since LinkedIn CSV is date-sorted (not alphabetical) so similar names are naturally spread across batches. Accepted risk; revisit if observed in production. Mitigation options for the future: shuffle before batching, or reduce batch size.

**Update "Not Included" section:** Remove "Batch embedding calls" (now implemented in v0.4.0).

## Changes

| File | Change |
|------|--------|
| `enrichment_pipeline/bulk_enrichment.py` | Loguru `{}` formatting (done). Redirect-aware `_match_results` with `redirects` return value |
| `enrichment_pipeline/post_enrichment.py` | `_update_crawled_profile` updates URL + stores old in `previous_linkedin_url` |
| `crawled_profile/entities/crawled_profile_entity.py` | Add `previous_linkedin_url` column + index |
| `import_pipeline/service.py` | Dedup checks both `linkedin_url` and `previous_linkedin_url` |
| New Alembic migration | `ADD COLUMN previous_linkedin_url`, `CREATE INDEX ix_cp_prev_linkedin_url` |
| `docs/specs/linkedout_enrichment_pipeline.collab.md` | Document slug redirect behavior + decision |

## Test Plan

### Matching tests (`test_bulk_enrichment.py`)

- **T-redirect-1**: 1 unmatched input + 1 unmatched result → fuzzy paired, appears in `redirects` dict
- **T-redirect-2**: 3 unmatched inputs + 3 unmatched results with similar slugs → all 3 paired by rapidfuzz greedy
- **T-redirect-3**: All inputs match exactly → `redirects` is empty
- **T-redirect-4**: Unmatched results but 0 unmatched inputs (extra result from Apify bug) → ignored, no crash
- **T-redirect-5**: Unmatched input slug is completely dissimilar from unmatched result → stays failed (below 60% threshold)

### Post-processing tests (`test_post_enrichment.py`)

- **T-redirect-6**: Apify returns different canonical URL → `linkedin_url` updated, `previous_linkedin_url` stores old
- **T-redirect-7**: Apify returns same URL (no redirect) → `previous_linkedin_url` stays None
- **T-redirect-8**: Unique constraint conflict on new URL → URL update skipped, profile still enriched

### Import dedup tests (`test_import_service.py` or `test_merge.py`)

- **T-redirect-9**: Re-import CSV with old URL → finds profile via `previous_linkedin_url`, no duplicate created

## Review Decisions (2026-04-13)

1. **Fuzzy matching via rapidfuzz greedy** — not 1-to-1 or suffix-only. With batch size 100 and ~2-5% redirect rate, expect 2-5 redirects per batch. Greedy pairing with `rapidfuzz.fuzz.ratio` ≥ 60% threshold.
2. **Pre-check SELECT** for unique constraint handling — cleaner than catching IntegrityError, tiny race window is harmless.
3. **Fix all `%s`/`%d` calls** across both `bulk_enrichment.py` and `post_enrichment.py` in one commit (17 total, not 12).
4. **Single `previous_linkedin_url` column** — double redirects are extremely rare. Acceptable risk over JSONB array complexity.

## Verification

1. `uv run python -m pytest backend/tests/unit/enrichment_pipeline/ backend/tests/shared/utils/test_linkedin_url.py -v`
2. `uv run python -m pytest backend/tests/ -v --tb=short` — no regressions
3. Alembic migration applies: `uv run alembic upgrade head`
4. Spec updated
5. Commit + push
