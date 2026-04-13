# SP4: Import Dedup + Spec Update

**Depends on:** SP2 (entity has `previous_linkedin_url`), SP3 (URL update logic working)
**Produces:** Import dedup checks both URLs, spec updated, test T9
**Estimated scope:** ~20 lines production code + ~30 lines test + spec text

## Overview

Two tasks:
1. Fix import dedup to check `previous_linkedin_url` so re-imports don't create duplicates after a redirect URL update
2. Update the enrichment spec to document the new behavior

## Changes

### 1. Import dedup: `_run_merge()` checks both URLs

**File:** `backend/src/linkedout/import_pipeline/service.py`
**Function:** `_run_merge()` starting at line 261

Current code (lines 272-278):
```python
existing_profiles: dict[str, CrawledProfileEntity] = {}
profile_rows = self._session.execute(select(CrawledProfileEntity)).scalars().all()
for p in profile_rows:
    norm = normalize_linkedin_url(p.linkedin_url) if p.linkedin_url else None
    if norm:
        existing_profiles[norm] = p
```

Add `previous_linkedin_url` indexing after the existing loop body:

```python
existing_profiles: dict[str, CrawledProfileEntity] = {}
profile_rows = self._session.execute(select(CrawledProfileEntity)).scalars().all()
for p in profile_rows:
    norm = normalize_linkedin_url(p.linkedin_url) if p.linkedin_url else None
    if norm:
        existing_profiles[norm] = p
    # Also index by previous URL for redirect dedup safety
    prev = normalize_linkedin_url(p.previous_linkedin_url) if p.previous_linkedin_url else None
    if prev and prev not in existing_profiles:
        existing_profiles[prev] = p
```

### 2. Import dedup: `_build_connection_lookups()` includes `previous_linkedin_url`

**File:** `backend/src/linkedout/import_pipeline/service.py`
**Function:** `_build_connection_lookups()` starting at line 211

Add `CrawledProfileEntity.previous_linkedin_url` to the SELECT (line 215-222):

```python
rows = self._session.execute(
    select(
        ConnectionEntity.id,
        ConnectionEntity.emails,
        CrawledProfileEntity.linkedin_url,
        CrawledProfileEntity.previous_linkedin_url,  # NEW
        CrawledProfileEntity.full_name,
        CrawledProfileEntity.current_company_name,
    ).join(
        CrawledProfileEntity,
        ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id,
    ).where(
        ConnectionEntity.app_user_id == app_user_id,
    )
).all()
```

Update the unpacking loop (line 230-246) to also include `previous_linkedin_url` in the lookup entry. The `ConnectionLookupEntry` is used for dedup matching. Add the previous URL as an additional lookup entry:

```python
for row in rows:
    conn_id, emails_csv, li_url, prev_li_url, full_name, company = row
    norm_url = normalize_linkedin_url(li_url) if li_url else None
    norm_prev_url = normalize_linkedin_url(prev_li_url) if prev_li_url else None
    # ... rest of loop unchanged ...

    entries.append(ConnectionLookupEntry(
        connection_id=conn_id,
        linkedin_url=norm_url,
        emails=norm_emails or None,
        full_name=full_name,
        company=company,
    ))
    # Add duplicate entry with previous URL for redirect dedup
    if norm_prev_url and norm_prev_url != norm_url:
        entries.append(ConnectionLookupEntry(
            connection_id=conn_id,
            linkedin_url=norm_prev_url,
            emails=norm_emails or None,
            full_name=full_name,
            company=company,
        ))
```

### 3. Update enrichment spec

**File:** `docs/specs/linkedout_enrichment_pipeline.collab.md`

Add the following content (see plan Step 6 for exact text):

**Under "Post-Enrichment Processing" section**, add:

> **LinkedIn slug redirect handling**: LinkedIn may resolve profile slugs to a different canonical form (e.g. stripping display name suffixes, removing emoji, normalizing hyphens). When Apify returns a `linkedinUrl` that differs from the input URL (after normalization), the system: (a) matches the result to the input via rapidfuzz greedy slug matching, (b) updates `linkedin_url` to the Apify canonical URL, and (c) stores the original URL in `previous_linkedin_url` for import dedup safety. The import pipeline checks both `linkedin_url` and `previous_linkedin_url` when deduplicating re-imports.

**Add a new decision:**

> **`previous_linkedin_url` for redirect tracking** — Chose single `previous_linkedin_url` column over JSONB array of aliases or separate alias table. Rationale: LinkedIn redirects are rare (~2-5%) and typically happen once. A single column handles the common case without schema complexity. If a profile redirects multiple times (extremely rare), only the most recent previous URL is preserved.

**Add known limitation:**

> **Similar-slug collision in fuzzy matching** — If two profiles with similar slugs (e.g. `abhishek-mishra-developer` and `abhishek-mishra1-engineer`) both redirect in the same batch, the rapidfuzz greedy matcher could cross-pair them. This requires: similar slugs + same batch + both redirect — extremely rare in practice since LinkedIn CSV is date-sorted (not alphabetical) so similar names are naturally spread across batches. Accepted risk; revisit if observed in production.

**Update "Not Included" section:** Remove "Batch embedding calls" if present (now implemented in v0.4.0).

### 4. Test T9

**File:** `backend/tests/unit/import_pipeline/test_import_service.py` (or create if needed — check for existing test file first with `ls backend/tests/unit/import_pipeline/`)

**T-redirect-9:** Re-import CSV with old URL finds profile via `previous_linkedin_url`, no duplicate created.

Setup:
1. Create a `CrawledProfileEntity` with `linkedin_url='https://www.linkedin.com/in/vikas-khatana'` and `previous_linkedin_url='https://www.linkedin.com/in/vikas-khatana-web-developer'`
2. Call `_run_merge()` with a contact whose linkedin_url is `vikas-khatana-web-developer`
3. Assert: contact matched to existing profile (not created as new)

This may need to be adapted based on how existing import tests are structured. Check existing test patterns first.

## Verification

- [ ] `_run_merge()` indexes by both `linkedin_url` and `previous_linkedin_url`
- [ ] `_build_connection_lookups()` includes `previous_linkedin_url` in SELECT and entries
- [ ] Spec updated with redirect handling, decision, and known limitation
- [ ] Test T9 passes
- [ ] `uv run python -m pytest backend/tests/ -v --tb=short` — no regressions
- [ ] Spec version bumped if applicable

## Files Changed

| File | Change |
|------|--------|
| `backend/src/linkedout/import_pipeline/service.py` | `_run_merge()` + `_build_connection_lookups()` check `previous_linkedin_url` |
| `docs/specs/linkedout_enrichment_pipeline.collab.md` | Document redirect behavior, decision, known limitation |
| `backend/tests/unit/import_pipeline/test_*.py` | Test T9 |
