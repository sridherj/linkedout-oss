# Sub-phase C: Apify Pipeline Migration

**Effort:** 45-60 minutes
**Dependencies:** SP-A (ProfileEnrichmentService and resolve_company must exist)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Migrate `PostEnrichmentService` to delegate structured row creation, search_vector, and embedding to `ProfileEnrichmentService.enrich()`. Add `_to_enrich_schema()` transformer. Delete 6 now-unused methods. Migrate `_resolve_company` call to shared utility.

## What to Do

### 1. Add `_to_enrich_schema()` Method

**File:** `src/linkedout/enrichment_pipeline/post_enrichment.py`

Add a new method `_to_enrich_schema(self, apify_data: dict) -> EnrichProfileRequestSchema` that transforms Apify JSON into the canonical format.

Key Apify-specific handling:
- **Month strings:** `start.get('month')` can be int or string ("January") — use `parse_month_name()` from `shared.utils.date_parsing`
- **`is_current`:** check if `end.get('text', '').strip().lower() == 'present'`
- **Skills:** merge `apify_data['skills'][].name` (dict format) + `apify_data['topSkills'][]` (string format) into flat list
- **Year validation:** only accept `int` values for year fields

See full implementation in plan Step 4 (`_to_enrich_schema` section).

Import: `from shared.utils.date_parsing import parse_month_name`

### 2. Replace Extraction Flow with `enrich()` Call

In the main processing method (around lines 96-107), replace:
```python
# BEFORE:
self._extract_experiences(profile.id, apify_data)
self._extract_education(profile.id, apify_data)
self._extract_skills(profile.id, apify_data)
self._generate_embedding(profile, apify_data)
self._populate_search_vector(profile, apify_data)
```

With:
```python
# AFTER:
enrich_request = self._to_enrich_schema(apify_data)
from linkedout.crawled_profile.services.profile_enrichment_service import ProfileEnrichmentService
enrichment_service = ProfileEnrichmentService(self._session, self._embedding_client)
enrichment_service.enrich(profile.id, enrich_request)
```

Keep `self._update_crawled_profile(profile, apify_data)` — it maps Apify-specific profile fields and stays.

### 3. Migrate `_resolve_company` in `_update_crawled_profile`

Replace `self._resolve_company(...)` call (around line 152-157) with the shared utility:

```python
from shared.utils.company_resolver import resolve_company

company_id = resolve_company(
    self._session, self._company_matcher, self._company_by_canonical,
    cp.get('companyName'), cp.get('companyLinkedinUrl'),
)
```

`PostEnrichmentService` still keeps `self._company_matcher` and `self._company_by_canonical` (from `_preload_companies`) for this one call.

### 4. Delete Unused Methods (Q8: Big Bang)

Delete these 6 methods that are now handled by `enrich()`:
- `_extract_experiences()` (~lines 184-240)
- `_extract_education()` (~lines 242-266)
- `_extract_skills()` (~lines 268-302)
- `_resolve_company()` (~lines 304-338) — migrated to shared util
- `_generate_embedding()` (~lines 340-366) — enrich() handles
- `_populate_search_vector()` (~lines 368-388) — enrich() handles

**Keep:**
- `_update_crawled_profile()` — Apify-specific profile field mapping
- `_update_enrichment_event()` — enrichment event status tracking
- `_preload_companies()` — still needed for `_update_crawled_profile`'s company resolution

### 5. Apify Transformer Unit Test

**File:** `tests/unit/linkedout/enrichment_pipeline/test_to_enrich_schema.py` — **new file**

Test `_to_enrich_schema()` as a pure transformation:
- Sample Apify JSON with experiences, education, skills → verify correct `EnrichProfileRequestSchema`
- Month string parsing: "January" → 1, "Feb" → 2
- `is_current` from "Present" end date text
- `topSkills` merged with `skills`
- Skills as objects (`.name`) and strings both handled
- Empty/null arrays don't crash
- Non-integer year values filtered out

### 6. Apify Migration Integration Test

**File:** `tests/integration/linkedout/enrichment_pipeline/test_post_enrichment_with_enrich.py` — **new file**

Test the full flow: `PostEnrichmentService` → `_to_enrich_schema()` → `ProfileEnrichmentService.enrich()`:
- Use sample Apify JSON → verify DB has correct experience/education/skill rows
- Verify `_resolve_company` shared util called correctly from `_update_crawled_profile`
- Verify row counts match expectations

## Verification

```bash
# Unit test for transformer
pytest tests/unit/linkedout/enrichment_pipeline/test_to_enrich_schema.py -v

# Integration test for migrated flow
pytest tests/integration/linkedout/enrichment_pipeline/test_post_enrichment_with_enrich.py -v

# Existing enrichment pipeline tests still pass
pytest tests/integration/linkedout/enrichment_pipeline/ -v
```

## Files Modified/Created

| File | Action |
|------|--------|
| `src/linkedout/enrichment_pipeline/post_enrichment.py` | Add `_to_enrich_schema()`, delegate to `enrich()`, delete 6 methods, migrate `_resolve_company` |
| `tests/unit/linkedout/enrichment_pipeline/test_to_enrich_schema.py` | **New** — transformer unit tests |
| `tests/integration/linkedout/enrichment_pipeline/test_post_enrichment_with_enrich.py` | **New** — migration integration tests |
