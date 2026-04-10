# Sub-phase B: Backend Controller + All Backend Tests

**Effort:** 60-90 minutes
**Dependencies:** SP-A (schema, company_resolver, ProfileEnrichmentService must exist)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Add the `POST /crawled-profiles/{id}/enrich` controller endpoint and write all backend tests: unit test for the service, integration test for the endpoint, and unit test for `resolve_company`.

## What to Do

### 1. Add Controller Endpoint

**File:** `src/linkedout/crawled_profile/controllers/crawled_profile_controller.py`

Add a custom endpoint to the existing `crawled_profiles_router`:

1. Create a `_get_enrichment_service` dependency that:
   - Accepts `X-App-User-Id` header
   - Creates a WRITE session (check existing dependency patterns in `base_controller_utils.py` — look for `create_service_dependency_raw` or similar)
   - Instantiates `EmbeddingClient()`
   - Yields `ProfileEnrichmentService(session, embedding_client)`

2. Add the endpoint:
   ```python
   @crawled_profiles_router.post(
       '/{crawled_profile_id}/enrich',
       response_model=EnrichProfileResponseSchema,
       summary='Enrich a profile with experience, education, and skill data',
   )
   ```
   - Calls `service.enrich(crawled_profile_id, request)`
   - Catches `ValueError` → 404
   - Catches `Exception` → 500 with logged error

Add imports: `EnrichProfileRequestSchema`, `EnrichProfileResponseSchema`, `ProfileEnrichmentService`.

> **Important:** Verify the exact dependency injection pattern by reading the existing controller file and `base_controller_utils.py` before implementing. The plan's `create_service_dependency_raw` may need adjustment to match actual codebase patterns.

### 2. Unit Test — ProfileEnrichmentService

**File:** `tests/unit/linkedout/crawled_profile/services/test_profile_enrichment_service.py` — **new file**

Test cases:
- **Happy path:** provide experiences, educations, skills → verify correct entity creation
  - Verify `ExperienceEntity` has computed `start_date`, `end_date`, `end_date_text`
  - Verify `seniority_level`/`function_area` resolved from mocked `RoleAliasRepository`
  - Verify `company_id` resolved via `resolve_company`
  - Verify `EducationEntity` created with correct fields
  - Verify `ProfileSkillEntity` created and deduplicated
  - Verify `profile.has_enriched_data = True`
  - Verify `profile.search_vector` rebuilt with expected terms
  - Verify `profile.embedding` set when `EmbeddingClient` provided
- **Embedding failure:** mock `embed_text()` to raise → verify JSONL file appended, profile still saved
- **No embedding client:** `EmbeddingClient=None` → embedding skipped, no error
- **Empty arrays:** `experiences=[], educations=[], skills=[]` → 0 rows, `has_enriched_data = True` (Q9)
- **Duplicate skills:** same skill name twice → deduplicated
- **No role alias match:** position with no alias → `seniority_level`/`function_area` stay None
- **Bulk delete idempotency:** call enrich twice → rows replaced, not doubled

Mock strategy: mock `session`, `CrawledProfileRepository.get_by_id()`, `RoleAliasRepository.get_by_alias_title()`, `EmbeddingClient.embed_text()`.

### 3. Integration Test — Enrich Endpoint

**File:** `tests/integration/linkedout/crawled_profile/test_enrich_endpoint.py` — **new file**

Test against real PostgreSQL (follow existing integration test patterns — check `tests/integration/` for conftest setup).

Test cases:
- Create a `CrawledProfile` in DB → call `POST /crawled-profiles/{id}/enrich` with sample data → verify:
  - Response has correct counts
  - DB has correct experience/education/skill rows
  - `has_enriched_data = true` on profile
  - `search_vector` contains expected terms
  - Experience rows have `company_id` populated (if company exists or was created)
  - Experience rows have `seniority_level`/`function_area` (if role alias exists in test data)
- **Idempotency:** call enrich twice → row counts don't double
- **404:** non-existent `crawled_profile_id` → 404
- **Empty payload:** all arrays empty → `has_enriched_data = true`, 0 rows (Q9)

Headers: include `X-App-User-Id: usr_sys_001`.

### 4. Unit Test — `resolve_company`

**File:** `tests/unit/shared/utils/test_company_resolver.py` — **new file**

Test cases:
- **Match existing company** → returns existing company ID from cache
- **Create new company** → flushes session, returns new ID, updates `company_by_canonical` cache
- **None company_name** → returns None immediately
- **Cache hit on second call** for same company → doesn't create duplicate

Mock strategy: mock `Session`, `CompanyMatcher.match_or_create()`.

## Verification

```bash
# Run unit tests
pytest tests/unit/linkedout/crawled_profile/services/test_profile_enrichment_service.py -v
pytest tests/unit/shared/utils/test_company_resolver.py -v

# Run integration test
pytest tests/integration/linkedout/crawled_profile/test_enrich_endpoint.py -v

# Verify endpoint responds
curl -X POST http://localhost:8001/crawled-profiles/NONEXISTENT/enrich \
  -H "Content-Type: application/json" \
  -H "X-App-User-Id: usr_sys_001" \
  -d '{"experiences":[],"educations":[],"skills":[]}' 
# Should return 404
```

## Files Modified/Created

| File | Action |
|------|--------|
| `src/linkedout/crawled_profile/controllers/crawled_profile_controller.py` | Add enrich endpoint + dependency |
| `tests/unit/linkedout/crawled_profile/services/test_profile_enrichment_service.py` | **New** — service unit tests |
| `tests/integration/linkedout/crawled_profile/test_enrich_endpoint.py` | **New** — endpoint integration tests |
| `tests/unit/shared/utils/test_company_resolver.py` | **New** — resolver unit tests |
