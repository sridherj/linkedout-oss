# Shared Context: Voyager Profile Enrichment Endpoint

**Plan:** `docs/plan/voyager-enrich-endpoint.md`
**Goal:** Create a single `POST /crawled-profiles/{id}/enrich` endpoint that both the Chrome Extension and Apify pipeline use to write structured experience/education/skill rows, rebuild search_vector, resolve role aliases, and generate embeddings.

---

## Core Problem

Two data sources (Chrome Extension via Voyager API, Apify pipeline) produce experience/education/skill data but use separate code paths. The extension currently sends `raw_profile` blobs without writing structured rows (`has_enriched_data = false`). The Apify pipeline has duplicated extraction logic. This plan unifies both into one canonical `enrich()` endpoint.

## Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| Q1 | `enrich()` owns `search_vector` | One owner prevents drift |
| Q2 | Sync embedding + JSONL failure file | 200ms acceptable; failures visible and retryable |
| Q3 | Extract `resolve_company` to shared util | Two consumers (enrich + PostEnrichmentService) |
| Q4 | Drop `raw_experience`/`raw_education` | `raw_profile` on crawled_profile is sufficient |
| Q5 | Populate `seniority_level`/`function_area` per experience via RoleAliasRepository | LLM reads these in affinity scoring |
| Q6 | Standalone `ProfileEnrichmentService` (not on CrawledProfileService) | 4 deps, different from CRUD — clean separation |
| Q7 | Await enrich before showing "Saved today" badge | Simpler than intermediate statuses, ~400ms total |
| Q8 | Big bang replace of Apify extraction methods | enrich() proven via extension tests first |
| Q9 | Always set `has_enriched_data = true` after attempt | Empty data is truth; prevents futile re-enrichment |
| Q10 | Enrich if `has_enriched_data = false` regardless of freshness | Natural backfill for pre-feature profiles |
| Q11 | Always show "Saved today" even if enrich fails; log to activity log | Profile IS saved; user can't fix embedding failures |

## DAG (Build Order)

```
A (backend core: schema + resolver + service) ──┬── B (controller + backend tests) ──┬── E (extension wiring + verification)
                                                 ├── C (Apify migration + tests)      │
                                                 │                                     │
D (extension types + mapper + client) ───────────────────────────────────────────────── ┘
```

- **A** has no dependencies — start immediately
- **B** depends on A (controller needs service, tests need endpoint)
- **C** depends on A (Apify migration calls enrich())
- **D** is fully independent — frontend types/mapper/client, can run in parallel with A/B/C
- **E** depends on B + D (wiring needs backend endpoint working + frontend client ready)

B and C can run in parallel after A completes.
D can run in parallel with everything.

## Endpoint Contract

```
POST /crawled-profiles/{crawled_profile_id}/enrich
Headers: X-App-User-Id
Body: EnrichProfileRequestSchema
Response 200: { "experiences_created": N, "educations_created": N, "skills_created": N }
```

## Repo Locations

| Component | Path |
|-----------|------|
| Backend root | `.` |
| Frontend root | `<linkedout-fe>` |
| Extension code | `<linkedout-fe>/extension/` |
| CrawledProfile schemas | `src/linkedout/crawled_profile/schemas/crawled_profile_api_schema.py` |
| CrawledProfile controller | `src/linkedout/crawled_profile/controllers/crawled_profile_controller.py` |
| CrawledProfile services | `src/linkedout/crawled_profile/services/` |
| PostEnrichmentService | `src/linkedout/enrichment_pipeline/post_enrichment.py` |
| Shared utils | `src/shared/utils/` (company_matcher.py, date_parsing.py, linkedin_url.py) |
| CompanyEntity | `src/linkedout/company/entities/company_entity.py` |
| ExperienceEntity | `src/linkedout/experience/entities/experience_entity.py` |
| EducationEntity | `src/linkedout/education/entities/education_entity.py` |
| ProfileSkillEntity | `src/linkedout/profile_skill/entities/profile_skill_entity.py` |
| RoleAliasRepository | `src/linkedout/role_alias/repositories/role_alias_repository.py` |
| EmbeddingClient | `src/linkedout/utilities/llm_manager/embedding_client.py` |
| Base controller utils | `src/common/controllers/base_controller_utils.py` |
| DB session manager | `src/shared/infra/db/db_session_manager.py` |
| Extension backend types | `<linkedout-fe>/extension/lib/backend/types.ts` |
| Extension mapper | `<linkedout-fe>/extension/lib/profile/mapper.ts` |
| Extension client | `<linkedout-fe>/extension/lib/backend/client.ts` |
| Extension background | `<linkedout-fe>/extension/entrypoints/background.ts` |

## Key Specs (read before modifying)

- `docs/specs/chrome_extension.collab.md`
- `docs/specs/linkedout_data_model.collab.md`

## Testing Strategy

| Layer | What's Real | What's Mocked |
|-------|-------------|---------------|
| Unit (service) | Nothing | Session, Repository, EmbeddingClient |
| Unit (Apify transformer) | Nothing | Nothing (pure function) |
| Unit (resolve_company) | Nothing | Session, CompanyMatcher |
| Integration (endpoint) | PostgreSQL + full stack | Nothing (or EmbeddingClient) |
| Extension (mapper) | Nothing | Nothing (pure function) |
| Extension (client) | Nothing | fetch/request |

## Verification Command

After all sub-phases complete, run against a real profile:
```bash
curl -X POST http://localhost:8001/crawled-profiles/cp_NW0DkPyIpcn_69BK4jRZz/enrich \
  -H "Content-Type: application/json" \
  -H "X-App-User-Id: usr_sys_001" \
  -d '{"experiences": [{"position": "Human Resources Consultant", "company_name": "ValueMomentum", "is_current": true}], "educations": [{"school_name": "Andhra University", "degree": "MBA", "field_of_study": "HR"}], "skills": ["Talent Acquisition", "HR Operations"]}'
```
