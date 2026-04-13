# SP3: Redirect Matching + URL Update

**Depends on:** SP2 (entity has `previous_linkedin_url` column)
**Produces:** Redirect-aware matching in `_match_results`, URL update in post-enrichment, integration in `_process_batch_results`, tests T1-T8
**Estimated scope:** ~120 lines production code + ~200 lines tests

## Overview

This is the core bug fix. Two changes:

1. **`_match_results()`** — After exact matching, use rapidfuzz to pair remaining unmatched inputs with unmatched results (redirect detection)
2. **`_update_crawled_profile()`** — When Apify returns a different canonical URL, update `linkedin_url` and preserve old URL in `previous_linkedin_url`

Plus the glue in `_process_batch_results()` to thread redirect info through to post-enrichment.

## Changes

### 1. Redirect-aware `_match_results()` in `bulk_enrichment.py`

**File:** `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py`
**Function:** `_match_results()` starting at line 205

#### Current signature and return type:
```python
def _match_results(
    batch_urls: list[str],
    apify_results: list[dict],
) -> tuple[dict[str, dict], list[str]]:
    # Returns (matched, missing)
```

#### New signature and return type:
```python
def _match_results(
    batch_urls: list[str],
    apify_results: list[dict],
) -> tuple[dict[str, dict], list[str], dict[str, str]]:
    # Returns (matched, missing, redirects)
    # redirects: {original_input_url: apify_canonical_url}
```

#### Implementation

Keep the existing exact-match pass unchanged. After it, add a fuzzy-match pass:

```python
from rapidfuzz import fuzz

# ... existing exact-match code produces matched, missing ...

# Fuzzy-match pass: pair unmatched inputs with unmatched results
redirects: dict[str, str] = {}

# Collect unmatched result URLs (not claimed by exact match)
matched_result_keys = set()
for url in batch_urls:
    key = normalize_linkedin_url(url)
    if key and key in result_lookup:
        matched_result_keys.add(key)

unmatched_results: dict[str, dict] = {
    k: v for k, v in result_lookup.items() if k not in matched_result_keys
}

if missing and unmatched_results:
    # Extract slug (everything after /in/) for fuzzy comparison
    def _slug(normalized_url: str) -> str:
        return normalized_url.rsplit('/in/', 1)[-1] if '/in/' in normalized_url else normalized_url

    # Build all pairs with similarity scores
    pairs: list[tuple[float, str, str]] = []  # (score, input_url, result_key)
    for input_url in missing:
        input_key = normalize_linkedin_url(input_url)
        if not input_key:
            continue
        input_slug = _slug(input_key)
        for result_key in unmatched_results:
            result_slug = _slug(result_key)
            score = fuzz.ratio(input_slug, result_slug)
            pairs.append((score, input_url, result_key))

    # Greedy assignment: highest similarity first
    pairs.sort(key=lambda x: x[0], reverse=True)
    used_inputs: set[str] = set()
    used_results: set[str] = set()

    for score, input_url, result_key in pairs:
        if score < 60:
            break  # All remaining are below threshold
        if input_url in used_inputs or result_key in used_results:
            continue
        # Pair them
        matched[input_url] = unmatched_results[result_key]
        apify_url = unmatched_results[result_key].get('linkedinUrl', '')
        canonical = normalize_linkedin_url(apify_url)
        if canonical:
            redirects[input_url] = canonical
        used_inputs.add(input_url)
        used_results.add(result_key)

    # Update missing list: remove successfully paired inputs
    missing = [url for url in missing if url not in used_inputs]

return matched, missing, redirects
```

**Import:** Add `from rapidfuzz import fuzz` at the top of the file (near existing imports).

### 2. Update `_process_batch_results()` to pass redirects

**File:** `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py`
**Function:** `_process_batch_results()` starting at line 618

Change the `_match_results` call at line 634 from:
```python
matched, _missing = _match_results(batch_urls, apify_results)
```
to:
```python
matched, _missing, redirects = _match_results(batch_urls, apify_results)
```

Pass `redirects` through to `service.process_batch()`. Add `redirects` as a kwarg:
```python
batch_enriched, batch_failed = service.process_batch(
    to_process,
    enrichment_event_ids={},
    skip_embeddings=skip_embeddings,
    source='bulk_enrichment',
    redirects=redirects,  # NEW
)
```

### 3. Update `process_batch()` and `_update_crawled_profile()` in `post_enrichment.py`

**File:** `backend/src/linkedout/enrichment_pipeline/post_enrichment.py`

#### 3a. `process_batch()` (line 274)

Add `redirects: dict[str, str] | None = None` parameter. Pass it through to `process_enrichment_result()`:

```python
def process_batch(
    self,
    results: list[tuple[str, str, dict]],
    enrichment_event_ids: dict[str, str],
    skip_embeddings: bool = False,
    source: str = 'bulk_enrichment',
    redirects: dict[str, str] | None = None,  # NEW
) -> tuple[int, int]:
```

In the loop (line 300), pass the redirect info:
```python
for profile_id, linkedin_url, apify_data in results:
    try:
        with self._session.begin_nested():
            event_id = enrichment_event_ids.get(linkedin_url)
            canonical_url = redirects.get(linkedin_url) if redirects else None
            self.process_enrichment_result(
                apify_data, event_id, linkedin_url,
                source=source, skip_archive=True,
                canonical_url=canonical_url,  # NEW
            )
```

#### 3b. `process_enrichment_result()` 

Add `canonical_url: str | None = None` parameter. After calling `_update_crawled_profile()`, if `canonical_url` is provided and differs from current URL, do the URL swap:

Find where `_update_crawled_profile(profile, data)` is called. After that call, add:

```python
if canonical_url and normalize_linkedin_url(profile.linkedin_url) != canonical_url:
    # Check for unique constraint conflict
    existing = self._session.execute(
        select(CrawledProfileEntity.id).where(
            CrawledProfileEntity.linkedin_url == canonical_url
        )
    ).scalar_one_or_none()
    if existing:
        logger.warning(
            'Skipping URL update for {}: canonical URL {} already exists (profile {})',
            profile.linkedin_url, canonical_url, existing,
        )
    else:
        profile.previous_linkedin_url = profile.linkedin_url
        profile.linkedin_url = canonical_url
        logger.info(
            'Updated linkedin_url: {} -> {} (old preserved in previous_linkedin_url)',
            profile.previous_linkedin_url, canonical_url,
        )
```

**Import needed:** `normalize_linkedin_url` from `shared.utils.linkedin_url` (check if already imported).

### 4. Tests

**File:** `backend/tests/unit/enrichment_pipeline/test_bulk_enrichment.py` — add tests for `_match_results` redirect behavior
**File:** `backend/tests/unit/enrichment_pipeline/test_post_enrichment.py` — add tests for URL update behavior

#### T1: Single redirect pairing
```
Input: batch_urls=['https://www.linkedin.com/in/vikas-khatana-web-developer']
Apify results: [{'linkedinUrl': 'https://www.linkedin.com/in/vikas-khatana', ...}]
Expected: matched has the URL, redirects = {'https://...vikas-khatana-web-developer': 'https://...vikas-khatana'}
```

#### T2: Multiple redirects with rapidfuzz greedy
```
3 unmatched inputs + 3 unmatched results with similar slugs. All 3 paired correctly.
```

#### T3: All exact matches — no redirects
```
All inputs match exactly. redirects is empty dict.
```

#### T4: Extra Apify result (no unmatched input)
```
Apify returns result for URL not in batch. No crash, ignored.
```

#### T5: Below threshold — stays failed
```
Unmatched input slug is completely dissimilar from unmatched result. Stays in missing.
```

#### T6: URL update on redirect
```
Mock a CrawledProfileEntity. Call with canonical_url different from current. 
Assert: previous_linkedin_url set to old value, linkedin_url set to canonical.
```

#### T7: No redirect — previous_linkedin_url stays None
```
Call without canonical_url. Assert: previous_linkedin_url unchanged (None).
```

#### T8: Unique constraint conflict — URL update skipped
```
Mock a second profile existing with the canonical URL. 
Assert: URL update skipped, profile still enriched, warning logged.
```

## Verification

- [ ] `_match_results` returns 3-tuple `(matched, missing, redirects)`
- [ ] All callers updated for 3-tuple return
- [ ] `_process_batch_results` passes `redirects` to `process_batch()`
- [ ] `process_batch()` accepts and forwards `redirects`
- [ ] `process_enrichment_result()` accepts `canonical_url` and updates URL when appropriate
- [ ] Pre-check SELECT prevents unique constraint violation
- [ ] Tests T1-T8 pass
- [ ] `uv run python -m pytest backend/tests/unit/enrichment_pipeline/ -v` — all pass
- [ ] `uv run python -m pytest backend/tests/ -v --tb=short` — no regressions

## Files Changed

| File | Change |
|------|--------|
| `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py` | Redirect fuzzy matching in `_match_results`, threading in `_process_batch_results` |
| `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` | `canonical_url` param in `process_enrichment_result` + `process_batch`, URL swap logic |
| `backend/tests/unit/enrichment_pipeline/test_bulk_enrichment.py` | Tests T1-T5 |
| `backend/tests/unit/enrichment_pipeline/test_post_enrichment.py` | Tests T6-T8 |
