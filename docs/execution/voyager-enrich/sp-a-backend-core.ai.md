# Sub-phase A: Backend Core (Schema + Company Resolver + Enrichment Service)

**Effort:** 45-60 minutes
**Dependencies:** None (can start immediately)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Create the foundation backend components: enrichment request/response schemas, shared `resolve_company` utility, and the standalone `ProfileEnrichmentService` with its `enrich()` method.

## What to Do

### 1. Add Enrichment Schemas

**File:** `src/linkedout/crawled_profile/schemas/crawled_profile_api_schema.py` — append new schemas

Add these 4 schemas to the existing file:

```python
class EnrichExperienceItem(BaseModel):
    """Single experience entry. Caller normalizes source-specific formats."""
    position: str | None = None
    company_name: str | None = None
    company_linkedin_url: str | None = None
    company_universal_name: str | None = None
    employment_type: str | None = None
    start_year: int | None = None
    start_month: int | None = None
    end_year: int | None = None
    end_month: int | None = None
    is_current: bool | None = None
    location: str | None = None
    description: str | None = None

class EnrichEducationItem(BaseModel):
    """Single education entry."""
    school_name: str | None = None
    school_linkedin_url: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    description: str | None = None

class EnrichProfileRequestSchema(BaseModel):
    """Canonical enrichment payload. Both extension and Apify transform to this."""
    experiences: list[EnrichExperienceItem] = []
    educations: list[EnrichEducationItem] = []
    skills: list[str] = []

class EnrichProfileResponseSchema(BaseModel):
    experiences_created: int
    educations_created: int
    skills_created: int
```

### 2. Create Shared `resolve_company` Utility

**File:** `src/shared/utils/company_resolver.py` — **new file**

Extract from `PostEnrichmentService._resolve_company()` (lines 304-338 in `post_enrichment.py`).

Stateless function that:
- Takes `session`, `company_matcher`, `company_by_canonical` cache, `company_name`, optional `linkedin_url`, optional `universal_name`
- Uses `CompanyMatcher.match_or_create()` for in-memory dedup
- Creates new `CompanyEntity` if no match, flushes, updates cache
- Returns `company_id` or `None`

See full implementation in the plan (Step 2, Q3 section). Import from `shared.utils.company_matcher` for `CompanyMatcher`, `normalize_company_linkedin_url`, `normalize_company_name`.

### 3. Create `ProfileEnrichmentService`

**File:** `src/linkedout/crawled_profile/services/profile_enrichment_service.py` — **new file**

Standalone service (does NOT extend `BaseService`). Key responsibilities:
- `__init__(session, embedding_client=None)` — creates repos, CompanyMatcher, preloads companies
- `enrich(profile_id, request) -> EnrichProfileResponseSchema` — the core method:
  1. Verify profile exists (raise ValueError if not)
  2. Bulk delete existing experience/education/skill rows (idempotent re-enrichment)
  3. Create experience rows with: computed `start_date`/`end_date`, `end_date_text`, resolved `company_id` via `resolve_company`, resolved `seniority_level`/`function_area` via `RoleAliasRepository.get_by_alias_title(position)` (Q5)
  4. Create education rows
  5. Create skill rows (deduplicated)
  6. Set `profile.has_enriched_data = True` (Q9: always after attempt)
  7. Rebuild `search_vector` from profile name/headline/about + experience companies/positions (Q1)
  8. Flush
  9. Generate embedding synchronously via `EmbeddingClient` (Q2)
- `_generate_embedding(profile, request)` — builds embedding text, calls `embed_text()`, on failure logs to JSONL
- `_log_failed_embedding(profile_id, error)` — appends to `data/failed_embeddings.jsonl`

See full implementation in plan Step 2. Follow the code exactly.

**Field mapping reference** (schema → ExperienceEntity):

| Schema field | Entity column | Transformation |
|---|---|---|
| position | position | direct |
| company_name | company_name | direct |
| company_linkedin_url | company_linkedin_url | direct |
| company_universal_name | — | used only for CompanyMatcher, not stored |
| start_year/start_month | start_date | `date(year, month or 1, 1)` if year |
| end_year/end_month | end_date | `date(year, month or 1, 1)` if year and not is_current |
| is_current | end_date_text | `"Present"` if is_current else None |
| position | seniority_level, function_area | Resolved via RoleAliasRepository |

## Verification

After completing this sub-phase:
1. All 3 new files exist and import correctly
2. `python -c "from linkedout.crawled_profile.schemas.crawled_profile_api_schema import EnrichProfileRequestSchema; print('OK')"` succeeds
3. `python -c "from shared.utils.company_resolver import resolve_company; print('OK')"` succeeds
4. `python -c "from linkedout.crawled_profile.services.profile_enrichment_service import ProfileEnrichmentService; print('OK')"` succeeds

## Files Modified/Created

| File | Action |
|------|--------|
| `src/linkedout/crawled_profile/schemas/crawled_profile_api_schema.py` | Append 4 schemas |
| `src/shared/utils/company_resolver.py` | **New** — shared company resolution |
| `src/linkedout/crawled_profile/services/profile_enrichment_service.py` | **New** — standalone enrichment service |
