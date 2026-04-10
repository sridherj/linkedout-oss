# Unified Profile Enrichment: Single `enrich()` Endpoint

## Problem

Two data sources produce experience/education/skill data for profiles:

1. **Chrome Extension** — Voyager API (decoration-93) → `VoyagerProfile` with positions, educations, skills. But the mapper (`lib/profile/mapper.ts`) only sends basic profile fields + `raw_profile` blob. **Never writes structured rows.** Result: `has_enriched_data = false`, 0 experience/education/skill rows.

2. **Apify Pipeline** — `PostEnrichmentService` in `post_enrichment.py` writes rows directly via ORM (`_extract_experiences()`, `_extract_education()`, `_extract_skills()`). Duplicated logic that should live in one place.

## Design Principles

1. **One canonical input format.** The `enrich()` endpoint accepts a single normalized schema. Callers (extension, Apify pipeline) transform their source-specific data before calling. The endpoint does not handle Apify month-name parsing, Voyager date-string splitting, or any source-specific quirks.

2. **enrich() owns the full "make profile searchable" lifecycle:** structured rows, search_vector, role alias resolution, and synchronous embedding generation.

## Design Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| Q1 | search_vector ownership | enrich() owns it; remove `_populate_search_vector()` from Apify | One owner prevents drift. enrich() writes the experience data that feeds search_vector. |
| Q2 | Embedding generation | **Sync inline + JSONL failure file** (`data/failed_embeddings.jsonl`). `ProfileEnrichmentService` takes optional `EmbeddingClient`, calls `embed_text()` synchronously. On failure: log, append to JSONL, continue. | 200ms acceptable. Failures must be visible and retryable, not silent. No Procrastinate needed. |
| Q3 | `_resolve_company` location | Extract to `shared/utils/company_resolver.py` as stateless function | Two internal consumers (enrich + PostEnrichmentService._update_crawled_profile), same logic. |
| Q4 | `raw_experience`/`raw_education` | Drop — enrich() doesn't populate these columns | Profile-level `raw_profile` stores the full original response. Per-row blobs are redundant. |
| Q5 | Role alias on experience rows | Populate `seniority_level` and `function_area` per experience via `RoleAliasRepository` | LLM actively reads `experience.seniority_level` in affinity scoring. Currently always null — populating improves scoring immediately. |
| Q6 | Service placement | **Standalone `ProfileEnrichmentService`** (not on CrawledProfileService) | enrich() has 4 deps (EmbeddingClient, RoleAliasRepo, CompanyMatcher, company preload) — different from CRUD. Clean separation, easier to test. |
| Q7 | Extension UX | **Await enrich before showing badge** — hold "Saving..." through save + enrich, then "Saved today" | Simpler than intermediate statuses. ~400ms total, imperceptible. Zero new message types. |
| Q8 | Apify migration | **Big bang replace** — delete 5 methods, replace with `_to_enrich_schema()` + `enrich()` in one step | enrich() proven via extension tests first. `_to_enrich_schema()` independently tested. |
| Q9 | Empty payload | **Always set `has_enriched_data = true`** after enrichment attempt, even with empty arrays | Attempt = enriched. Empty Voyager data is truth for that profile. Marking false causes futile re-enrichment. |
| Q10 | Fresh but unenriched | **Enrich if `has_enriched_data = false`**, regardless of freshness | Natural backfill for pre-feature profiles on next visit. 3 lines in skip path. |
| Q11 | Enrich failure badge | **Always "Saved today"**, log failure to activity log | Profile IS saved. User can't fix failed embeddings. JSONL file gives ops visibility. |

## Endpoint Contract

```
POST /crawled-profiles/{crawled_profile_id}/enrich
Headers: X-App-User-Id
Body: EnrichProfileRequestSchema (see below)
Response 200: { "experiences_created": 2, "educations_created": 2, "skills_created": 7 }
```

---

## Step 1: Backend Schema

**File:** `src/linkedout/crawled_profile/schemas/crawled_profile_api_schema.py` — append new schemas

```python
from pydantic import BaseModel

class EnrichExperienceItem(BaseModel):
    """Single experience entry. Caller normalizes source-specific formats."""
    position: str | None = None
    company_name: str | None = None
    company_linkedin_url: str | None = None       # e.g. "https://www.linkedin.com/company/google"
    company_universal_name: str | None = None      # for CompanyMatcher dedup (not stored)
    employment_type: str | None = None
    start_year: int | None = None
    start_month: int | None = None                 # 1-12 integer, caller parses strings
    end_year: int | None = None
    end_month: int | None = None
    is_current: bool | None = None                 # caller sets: Apify checks "present", extension checks !endDate
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
    skills: list[str] = []                         # flat deduplicated list, caller merges topSkills etc.


class EnrichProfileResponseSchema(BaseModel):
    experiences_created: int
    educations_created: int
    skills_created: int
```

**Field mapping — schema → ExperienceEntity columns:**

| Schema field | ExperienceEntity column | Notes |
|---|---|---|
| position | position | direct |
| company_name | company_name | direct |
| company_linkedin_url | company_linkedin_url | direct |
| company_universal_name | — | used only for CompanyMatcher → `company_id`, not stored |
| employment_type | employment_type | direct |
| start_year / start_month | start_year, start_month | direct |
| end_year / end_month | end_year, end_month | direct |
| is_current | is_current | direct |
| location | location | direct |
| description | description | direct |
| — | start_date | **computed**: `date(start_year, start_month or 1, 1)` if start_year |
| — | end_date | **computed**: `date(end_year, end_month or 1, 1)` if end_year and not is_current |
| — | end_date_text | **set to** `"Present"` if `is_current` else None |
| — | seniority_level | **resolved** via `RoleAliasRepository.get_by_alias_title(position)` (Q5) |
| — | function_area | **resolved** via `RoleAliasRepository.get_by_alias_title(position)` (Q5) |
| — | raw_experience | **not stored** (Q4 — `raw_profile` on crawled_profile is sufficient) |

---

## Step 2: Backend Service — `ProfileEnrichmentService`

**File:** `src/linkedout/crawled_profile/services/profile_enrichment_service.py` — **new file** (Q6: standalone service)

Standalone service with explicit deps. Does NOT extend `BaseService` — custom business logic.

```python
import json
import logging
from datetime import date as date_type
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.crawled_profile.repositories.crawled_profile_repository import CrawledProfileRepository
from linkedout.crawled_profile.schemas.crawled_profile_api_schema import (
    EnrichProfileRequestSchema, EnrichProfileResponseSchema,
)
from linkedout.education.entities.education_entity import EducationEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from linkedout.role_alias.repositories.role_alias_repository import RoleAliasRepository
from shared.utils.company_resolver import resolve_company
from shared.utils.company_matcher import CompanyMatcher
from utilities.llm_manager.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)

FAILED_EMBEDDINGS_PATH = Path('data/failed_embeddings.jsonl')


class ProfileEnrichmentService:
    """Owns the full "make profile searchable" lifecycle.

    Responsibilities:
    - Structured rows (delete-then-create): experience, education, skill
    - Company resolution via CompanyMatcher
    - Role alias resolution (seniority_level, function_area) per experience
    - search_vector rebuild
    - Synchronous embedding generation (Q2)
    - JSONL failure logging for failed embeddings (Q2)
    """

    def __init__(self, session: Session, embedding_client: Optional[EmbeddingClient] = None):
        self._session = session
        self._repository = CrawledProfileRepository(session)
        self._embedding_client = embedding_client
        self._role_alias_repo = RoleAliasRepository(session)
        self._company_matcher = CompanyMatcher()
        self._company_by_canonical: dict[str, CompanyEntity] = {}
        self._preload_companies()

    def _preload_companies(self) -> None:
        """Load existing companies into matcher for dedup."""
        companies = self._session.execute(select(CompanyEntity)).scalars().all()
        for co in companies:
            self._company_matcher.match_or_create(
                company_name=co.canonical_name,
                linkedin_url=co.linkedin_url,
                universal_name=co.universal_name,
            )
            self._company_by_canonical[co.canonical_name] = co

    def enrich(self, profile_id: str, request: EnrichProfileRequestSchema) -> EnrichProfileResponseSchema:
        """Write experience/education/skill rows for a profile.

        Owns the full "make profile searchable" lifecycle:
        - Structured rows (delete-then-create)
        - Company resolution
        - Role alias resolution (seniority_level, function_area) per experience
        - search_vector rebuild
        - Synchronous embedding generation
        """
        session = self._session

        # 1. Verify profile exists
        profile = self._repository.get_by_id(profile_id)
        if not profile:
            raise ValueError(f'CrawledProfile not found: {profile_id}')

        # 2. Bulk delete existing rows (idempotent re-enrichment)
        session.execute(ExperienceEntity.__table__.delete().where(
            ExperienceEntity.crawled_profile_id == profile_id))
        session.execute(EducationEntity.__table__.delete().where(
            EducationEntity.crawled_profile_id == profile_id))
        session.execute(ProfileSkillEntity.__table__.delete().where(
            ProfileSkillEntity.crawled_profile_id == profile_id))

        # 3. Create experiences
        for exp in request.experiences:
            company_id = resolve_company(
                session, self._company_matcher, self._company_by_canonical,
                exp.company_name, exp.company_linkedin_url, exp.company_universal_name,
            )

            # Compute date fields from year/month
            start_date = date_type(exp.start_year, exp.start_month or 1, 1) if exp.start_year else None
            end_date = None
            if exp.end_year and not exp.is_current:
                end_date = date_type(exp.end_year, exp.end_month or 1, 1)

            # Q5: Role alias lookup for seniority + function area
            seniority_level = None
            function_area = None
            if exp.position:
                alias = self._role_alias_repo.get_by_alias_title(exp.position)
                if alias:
                    seniority_level = alias.seniority_level
                    function_area = alias.function_area

            session.add(ExperienceEntity(
                crawled_profile_id=profile_id,
                position=exp.position,
                company_name=exp.company_name,
                company_id=company_id,
                company_linkedin_url=exp.company_linkedin_url,
                employment_type=exp.employment_type,
                start_date=start_date,
                start_year=exp.start_year,
                start_month=exp.start_month,
                end_date=end_date,
                end_year=exp.end_year,
                end_month=exp.end_month,
                end_date_text='Present' if exp.is_current else None,
                is_current=exp.is_current if exp.is_current else None,
                seniority_level=seniority_level,
                function_area=function_area,
                location=exp.location,
                description=exp.description,
            ))

        # 4. Create educations
        for edu in request.educations:
            session.add(EducationEntity(
                crawled_profile_id=profile_id,
                school_name=edu.school_name,
                school_linkedin_url=edu.school_linkedin_url,
                degree=edu.degree,
                field_of_study=edu.field_of_study,
                start_year=edu.start_year,
                end_year=edu.end_year,
                description=edu.description,
            ))

        # 5. Create skills (deduplicated)
        seen: set[str] = set()
        for skill_name in request.skills:
            if not skill_name or skill_name in seen:
                continue
            seen.add(skill_name)
            session.add(ProfileSkillEntity(
                crawled_profile_id=profile_id,
                skill_name=skill_name,
                endorsement_count=0,
            ))

        # 6. Set has_enriched_data flag (Q9: always true after attempt)
        profile.has_enriched_data = True

        # 7. Q1: Rebuild search_vector (enrich() owns this)
        parts = []
        if profile.full_name: parts.append(profile.full_name)
        if profile.headline: parts.append(profile.headline)
        if profile.about: parts.append(profile.about)
        for exp in request.experiences:
            if exp.company_name: parts.append(exp.company_name)
            if exp.position: parts.append(exp.position)
        profile.search_vector = ' '.join(parts) if parts else None

        session.flush()

        # 8. Q2: Synchronous embedding generation + JSONL failure logging
        self._generate_embedding(profile, request)

        return EnrichProfileResponseSchema(
            experiences_created=len(request.experiences),
            educations_created=len(request.educations),
            skills_created=len(seen),
        )

    def _generate_embedding(self, profile: CrawledProfileEntity, request: EnrichProfileRequestSchema) -> None:
        """Generate embedding synchronously. On failure, append to JSONL for retry."""
        if not self._embedding_client:
            logger.debug('No embedding client — skipping embedding generation')
            return

        exp_dicts = [
            {'company_name': e.company_name or '', 'title': e.position or ''}
            for e in request.experiences
        ]
        profile_dict = {
            'full_name': profile.full_name,
            'headline': profile.headline,
            'about': profile.about,
            'experiences': exp_dicts,
        }
        text = EmbeddingClient.build_embedding_text(profile_dict)
        if not text.strip():
            return

        try:
            vector = self._embedding_client.embed_text(text)
            profile.embedding = vector
        except Exception as e:
            logger.error(f'Embedding generation failed for {profile.id}: {e}')
            self._log_failed_embedding(profile.id, str(e))

    def _log_failed_embedding(self, profile_id: str, error: str) -> None:
        """Append failed embedding to JSONL file for later retry."""
        from datetime import datetime, timezone
        entry = {
            'profile_id': profile_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': error,
        }
        try:
            FAILED_EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(FAILED_EMBEDDINGS_PATH, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f'Failed to log embedding failure: {e}')
```

### Q3: Shared `resolve_company` utility

**File:** `src/shared/utils/company_resolver.py` — new file, extracted from `PostEnrichmentService._resolve_company` (lines 304-338)

```python
"""Stateless company resolution — match or create via CompanyMatcher."""
from typing import Optional

from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from shared.utils.company_matcher import CompanyMatcher, normalize_company_linkedin_url, normalize_company_name


def resolve_company(
    session: Session,
    company_matcher: CompanyMatcher,
    company_by_canonical: dict[str, CompanyEntity],
    company_name: Optional[str],
    linkedin_url: Optional[str] = None,
    universal_name: Optional[str] = None,
) -> Optional[str]:
    """Resolve or create a company, returning its ID.

    Uses CompanyMatcher for in-memory dedup. Creates new CompanyEntity if no match.
    Caller manages the CompanyMatcher and company_by_canonical cache.
    """
    if not company_name:
        return None
    canonical = company_matcher.match_or_create(
        company_name=company_name, linkedin_url=linkedin_url, universal_name=universal_name)
    if not canonical:
        return None
    if canonical in company_by_canonical:
        return company_by_canonical[canonical].id
    # Create new company
    norm_url = normalize_company_linkedin_url(linkedin_url) if linkedin_url else None
    co = CompanyEntity(
        canonical_name=canonical,
        normalized_name=normalize_company_name(canonical),
        linkedin_url=norm_url,
        universal_name=universal_name,
    )
    session.add(co)
    session.flush()
    company_by_canonical[canonical] = co
    return co.id
```

Both `enrich()` and `PostEnrichmentService._update_crawled_profile()` (line 152) import and call this.

---

## Step 3: Backend Controller Endpoint

**File:** `src/linkedout/crawled_profile/controllers/crawled_profile_controller.py`

Custom endpoint added to existing `crawled_profiles_router`. New dependency for `ProfileEnrichmentService` (Q6: standalone service, not CrawledProfileService).

```python
from linkedout.crawled_profile.services.profile_enrichment_service import ProfileEnrichmentService
from utilities.llm_manager.embedding_client import EmbeddingClient


def _get_enrichment_service(
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[ProfileEnrichmentService, None, None]:
    """Dependency that creates ProfileEnrichmentService with EmbeddingClient."""
    from shared.infra.db.db_session_manager import DbSessionType
    from common.controllers.base_controller_utils import create_service_dependency_raw
    for session in create_service_dependency_raw(DbSessionType.WRITE, app_user_id=app_user_id):
        embedding_client = EmbeddingClient()
        yield ProfileEnrichmentService(session, embedding_client)


@crawled_profiles_router.post(
    '/{crawled_profile_id}/enrich',
    response_model=EnrichProfileResponseSchema,
    summary='Enrich a profile with experience, education, and skill data',
)
def enrich_profile(
    crawled_profile_id: str,
    request: EnrichProfileRequestSchema,
    service: ProfileEnrichmentService = Depends(_get_enrichment_service),
) -> EnrichProfileResponseSchema:
    try:
        return service.enrich(crawled_profile_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error enriching profile {crawled_profile_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to enrich profile: {str(e)}')
```

Add imports: `EnrichProfileRequestSchema`, `EnrichProfileResponseSchema` from the api_schema file.

> Note: The exact `create_service_dependency_raw` helper may need to be verified against the existing dependency pattern in `base_controller_utils.py`. The key point is: the dependency yields a WRITE session and passes `EmbeddingClient` to the service constructor.

---

## Step 4: Migrate Apify Pipeline

**File:** `src/linkedout/enrichment_pipeline/post_enrichment.py`

### Before (current flow, lines 96-107):
```python
self._update_crawled_profile(profile, apify_data)       # Apify-specific profile mapping
self._extract_experiences(profile.id, apify_data)        # DUPLICATED
self._extract_education(profile.id, apify_data)          # DUPLICATED
self._extract_skills(profile.id, apify_data)             # DUPLICATED
self._generate_embedding(profile, apify_data)            # inline embedding
self._populate_search_vector(profile, apify_data)        # search vector
```

### After (refactored — Q6: standalone service, Q8: big bang):
```python
self._update_crawled_profile(profile, apify_data)        # stays — Apify-specific profile field mapping
enrich_request = self._to_enrich_schema(apify_data)      # NEW — transform Apify JSON → canonical format
from linkedout.crawled_profile.services.profile_enrichment_service import ProfileEnrichmentService
enrichment_service = ProfileEnrichmentService(self._session, self._embedding_client)
enrichment_service.enrich(profile.id, enrich_request)    # SHARED — handles rows, search_vector, role alias, embedding
# No more _extract_*, _generate_embedding, or _populate_search_vector — enrich() owns all (Q1, Q2)
```

### `_to_enrich_schema()` — Apify JSON → canonical format

Handles all Apify-specific quirks (month strings, "present" text, skill objects vs strings, topSkills merging):

```python
from shared.utils.date_parsing import parse_month_name

def _to_enrich_schema(self, apify_data: dict) -> EnrichProfileRequestSchema:
    """Transform Apify's JSON into the canonical EnrichProfileRequestSchema."""
    experiences = []
    for exp in (apify_data.get('experience', []) or []):
        start = exp.get('startDate', {}) or {}
        end = exp.get('endDate', {}) or {}
        end_text = (end.get('text', '') or '').strip().lower()

        # Apify months can be int or string ("January")
        start_month = start.get('month')
        if isinstance(start_month, str):
            start_month = parse_month_name(start_month)
        end_month = end.get('month')
        if isinstance(end_month, str):
            end_month = parse_month_name(end_month)

        experiences.append(EnrichExperienceItem(
            position=exp.get('position'),
            company_name=exp.get('companyName'),
            company_linkedin_url=exp.get('companyLinkedinUrl'),
            company_universal_name=exp.get('companyUniversalName'),
            employment_type=exp.get('employmentType'),
            start_year=start.get('year') if isinstance(start.get('year'), int) else None,
            start_month=start_month if isinstance(start_month, int) else None,
            end_year=end.get('year') if isinstance(end.get('year'), int) else None,
            end_month=end_month if isinstance(end_month, int) else None,
            is_current=(end_text == 'present') or None,
            location=exp.get('location'),
            description=exp.get('description'),
        ))

    educations = []
    for edu in (apify_data.get('education', []) or []):
        start = edu.get('startDate', {}) or {}
        end = edu.get('endDate', {}) or {}
        educations.append(EnrichEducationItem(
            school_name=edu.get('schoolName'),
            school_linkedin_url=edu.get('schoolLinkedinUrl'),
            degree=edu.get('degree'),
            field_of_study=edu.get('fieldOfStudy'),
            start_year=start.get('year') if isinstance(start.get('year'), int) else None,
            end_year=end.get('year') if isinstance(end.get('year'), int) else None,
            description=edu.get('description'),
        ))

    # Merge skills[].name + topSkills[] into flat list
    skill_names = []
    for s in (apify_data.get('skills', []) or []):
        name = s.get('name') if isinstance(s, dict) else str(s)
        if name: skill_names.append(name)
    for s in (apify_data.get('topSkills', []) or []):
        if s: skill_names.append(s)

    return EnrichProfileRequestSchema(
        experiences=experiences, educations=educations, skills=skill_names)
```

### Delete these methods (now unused — Q8: big bang):
- `_extract_experiences()` (lines 184-240)
- `_extract_education()` (lines 242-266)
- `_extract_skills()` (lines 268-302)
- `_resolve_company()` (lines 304-338) — Q3: migrated to shared util
- `_generate_embedding()` (lines 340-366) — Q2: enrich() generates embedding synchronously
- `_populate_search_vector()` (lines 368-388) — Q1: enrich() owns search_vector

### Keep these methods:
- `_update_crawled_profile()` — Apify JSON field mapping to profile columns (stays Apify-specific)
- `_update_enrichment_event()` — enrichment event status tracking

### `_resolve_company` migration in `_update_crawled_profile`:
Lines 152-157 call `self._resolve_company()` for the profile-level `company_id`. After migration, change to import the shared utility:

```python
from shared.utils.company_resolver import resolve_company

# In _update_crawled_profile, replace self._resolve_company(...) with:
company_id = resolve_company(
    self._session, self._company_matcher, self._company_by_canonical,
    cp.get('companyName'), cp.get('companyLinkedinUrl'),
)
```

PostEnrichmentService still needs `self._company_matcher` and `self._company_by_canonical` (initialized in `_preload_companies`) for this one call. That's fine — same pattern, just calling the shared function.

---

## Step 5: Extension — Mapper + API Call

### 5a. Types

**File:** `<linkedout-fe>/extension/lib/backend/types.ts` — append:

```ts
/** Matches EnrichProfileRequestSchema from backend. */
export interface EnrichExperienceItem {
  position?: string | null;
  company_name?: string | null;
  company_linkedin_url?: string | null;
  company_universal_name?: string | null;
  employment_type?: string | null;
  start_year?: number | null;
  start_month?: number | null;
  end_year?: number | null;
  end_month?: number | null;
  is_current?: boolean | null;
  location?: string | null;
  description?: string | null;
}

export interface EnrichEducationItem {
  school_name?: string | null;
  school_linkedin_url?: string | null;
  degree?: string | null;
  field_of_study?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  description?: string | null;
}

export interface EnrichProfilePayload {
  experiences: EnrichExperienceItem[];
  educations: EnrichEducationItem[];
  skills: string[];
}
```

### 5b. Mapper

**File:** `<linkedout-fe>/extension/lib/profile/mapper.ts` — add:

Extension normalizes Voyager data into canonical format. Key transformations:
- `VoyagerPosition.startDate` is `"2022-09"` or `"2022"` → split into year/month ints
- `VoyagerPosition.companyUrn` → resolve to company URL + universalName via `VoyagerCompany[]`
- `!endDate` → `is_current: true`

```ts
import type { VoyagerProfile, VoyagerCompany } from '../voyager/types';
import type { EnrichProfilePayload } from '../backend/types';

export function toEnrichPayload(profile: VoyagerProfile): EnrichProfilePayload {
  return {
    experiences: profile.positions.map(p => {
      const company = resolveCompany(p.companyUrn, profile.companies);
      return {
        position: p.title,
        company_name: p.companyName,
        company_linkedin_url: company?.url ?? null,
        company_universal_name: company?.universalName ?? null,
        start_year: parseYear(p.startDate),
        start_month: parseMonth(p.startDate),
        end_year: parseYear(p.endDate),
        end_month: parseMonth(p.endDate),
        is_current: !p.endDate ? true : null,
        location: p.locationName,
        description: p.description,
      };
    }),
    educations: profile.educations.map(e => ({
      school_name: e.schoolName,
      degree: e.degreeName,
      field_of_study: e.fieldOfStudy,
      start_year: parseYear(e.startDate),
      end_year: parseYear(e.endDate),
      description: e.description,
    })),
    skills: profile.skills,   // already flat string[] from Voyager parser
  };
}

/** Match companyUrn to VoyagerCompany for URL + universalName resolution. */
function resolveCompany(companyUrn: string | null, companies: VoyagerCompany[]): VoyagerCompany | null {
  if (!companyUrn) return null;
  return companies.find(c => c.entityUrn === companyUrn) ?? null;
}

/** "2022-09" → 2022, "2022" → 2022, null → null */
function parseYear(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const year = parseInt(dateStr.split('-')[0], 10);
  return isNaN(year) ? null : year;
}

/** "2022-09" → 9, "2022" → null, null → null */
function parseMonth(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const parts = dateStr.split('-');
  if (parts.length < 2) return null;
  const month = parseInt(parts[1], 10);
  return isNaN(month) ? null : month;
}
```

### 5c. API Client

**File:** `<linkedout-fe>/extension/lib/backend/client.ts` — add:

```ts
import type { EnrichProfilePayload } from './types';

/**
 * Enrich a profile with experience, education, and skill data.
 */
export async function enrichProfile(
  crawledProfileId: string,
  payload: EnrichProfilePayload,
): Promise<void> {
  await request<unknown>(
    `${API_BASE_URL}/crawled-profiles/${crawledProfileId}/enrich`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}
```

### 5d. Wire into Save Flow

**File:** `<linkedout-fe>/extension/entrypoints/background.ts`

**Key design decisions applied here:**
- Q7: Await enrich before showing "Saved today" badge (hold "Saving..." through save + enrich)
- Q11: Always show "Saved today" even if enrichment fails (log failure silently)
- Q10: Enrich fresh-but-unenriched profiles (backfill on visit)
- `has_enriched_data` is NOT set in extension payload — `enrich()` sets it on the backend

There are 3 "done" paths where enrichment fires **before** the done status. Enrich is awaited, failures are caught and logged:

**Path 1 — New profile create** (around line 234):
```ts
const newId = await createProfile(payload);
// Await enrichment before showing badge (Q7)
try {
  await enrichProfile(newId, toEnrichPayload(profile));
} catch (err) {
  console.warn('[enrichProfile] Failed:', err);
  await appendLogAndNotify({
    timestamp: new Date().toISOString(),
    action: 'error',
    profileName, linkedinUrl,
    reason: `Enrichment failed: ${err}`,
  });
}
sendProfileStatus('done', { badgeStatus: 'saved_today', ... });
```

**Path 2 — 409 race → update** (around line 257):
```ts
await updateProfile(retryFreshness.id, payload);
try {
  await enrichProfile(retryFreshness.id, toEnrichPayload(profile));
} catch (err) {
  console.warn('[enrichProfile] Failed:', err);
  // log entry
}
sendProfileStatus('done', { badgeStatus: 'saved_today', ... });
```

**Path 3 — Stale → update** (around line 302):
```ts
await updateProfile(freshness.id, payload);
try {
  await enrichProfile(freshness.id, toEnrichPayload(profile));
} catch (err) {
  console.warn('[enrichProfile] Failed:', err);
  // log entry
}
sendProfileStatus('done', { badgeStatus: 'saved_today', ... });
```

**Path 4 — Fresh but unenriched (Q10: backfill)** (line 281-299):
```ts
// Profile is fresh (< 30 days), but check if it has enriched data
if (!freshness.profile.has_enriched_data) {
  try {
    await enrichProfile(freshness.id, toEnrichPayload(profile));
  } catch (err) {
    console.warn('[enrichProfile] Backfill failed:', err);
  }
}
sendProfileStatus('skipped', { badgeStatus: 'up_to_date', ... });
```

**`has_enriched_data` NOT set in extension payload** (Q11):
The `toCrawledProfilePayload()` in `mapper.ts` does NOT set `has_enriched_data`. It stays `false` (the default) on create/update. The backend `enrich()` method sets it to `true` on success. This ensures correct state even when enrichment fails.

Imports needed in `background.ts`:
```ts
import { enrichProfile } from '../lib/backend/client';
import { toEnrichPayload } from '../lib/profile/mapper';
```

---

## Step 6: Tests

### 6a. Backend Unit Test — `ProfileEnrichmentService.enrich()`

**File:** `tests/unit/linkedout/crawled_profile/services/test_profile_enrichment_service.py`

- Mock `self._session` and `self._repository`
- Verify bulk delete calls for all 3 entity tables
- Verify ExperienceEntity created with correct fields including:
  - Computed `start_date`, `end_date`, `end_date_text`
  - Resolved `seniority_level`, `function_area` from role alias (Q5)
  - Resolved `company_id` from CompanyMatcher (Q3)
- Verify EducationEntity created with correct fields
- Verify ProfileSkillEntity created, deduplicated
- Verify `profile.has_enriched_data = True` (Q9: always true after attempt)
- Verify `profile.search_vector` rebuilt — assert expected terms (company names, positions) present (Q1)
- **Verify `profile.embedding` is set when `EmbeddingClient` provided** (Q2)
- **Verify embedding failure → JSONL file appended, profile still saved** (Q2)
- **Verify embedding skipped when `EmbeddingClient` is None**
- Edge: empty arrays → 0 rows created, `has_enriched_data = True`, no errors (Q9)
- Edge: duplicate skills → deduplicated
- Edge: position with no role alias match → seniority_level/function_area stay None

### 6b. Backend Integration Test — `POST /crawled-profiles/{id}/enrich`

**File:** `tests/integration/linkedout/crawled_profile/test_enrich_endpoint.py`

- Create profile → call enrich with sample data → verify DB rows
- Verify `has_enriched_data = true` on profile
- Verify experience rows have correct `company_id` (resolved via CompanyMatcher)
- Verify experience rows have `seniority_level`/`function_area` populated (Q5)
- **Verify `search_vector` contains expected terms** (profile name, company names, positions)
- **Verify `embedding` is populated** (integration test uses real EmbeddingClient or mock)
- Test idempotency: call enrich twice → row counts don't double (delete-then-create)
- Test 404: non-existent profile_id → 404
- **Test empty payload: all arrays empty → `has_enriched_data = true`, 0 rows** (Q9)

### 6c. Apify Transformer Test

**File:** `tests/unit/linkedout/enrichment_pipeline/test_to_enrich_schema.py`

- Test `_to_enrich_schema()` with sample Apify JSON
- Verify month string parsing ("January" → 1, "Feb" → 2)
- Verify `is_current` from "Present" end date text
- Verify topSkills merged with skills
- Verify skills as objects (`.name`) and strings both handled
- Verify empty/null arrays don't crash

### 6d. Apify Migration Integration Test

**File:** `tests/integration/linkedout/enrichment_pipeline/test_post_enrichment_with_enrich.py`

- **Verify PostEnrichmentService → ProfileEnrichmentService.enrich() flow produces correct rows**
- Use sample Apify JSON → `_to_enrich_schema()` → `enrich()` → verify DB matches expected experience/education/skill rows
- **Verify `_resolve_company` shared util called correctly from `_update_crawled_profile`**

### 6e. `resolve_company` Shared Utility Test

**File:** `tests/unit/shared/utils/test_company_resolver.py`

- **Test match existing company → returns company ID**
- **Test create new company → flushes, returns new ID, updates cache**
- **Test None company_name → returns None**
- **Test cache hit on second call for same company**

### 6f. Extension Mapper Test

**File:** `<linkedout-fe>/extension/lib/profile/__tests__/mapper.test.ts`

- Test `toEnrichPayload()` with `VOYAGER_FULL_PROFILE` fixture
- Verify position → experience field mapping (title → position, companyName → company_name)
- Verify company URL resolution from companyUrn via companies array
- Verify company universalName resolution
- Verify `is_current: true` when no endDate
- Verify date parsing: "2022-09" → year=2022, month=9
- Verify date parsing: "2022" → year=2022, month=null
- Edge: empty positions/educations/skills → empty arrays

### 6g. Extension Client Test

**File:** `<linkedout-fe>/extension/lib/backend/__tests__/client.test.ts`

- Test `enrichProfile()` sends POST to correct URL
- Verify request body shape matches `EnrichProfilePayload`
- Verify `X-App-User-Id` header included

### 6h. Extension Fresh-but-Unenriched Path

- **Verify enrich is called when `freshness.profile.has_enriched_data === false` even if profile is fresh** (Q10)

---

## Step 7: Verify with Manjusha's Profile

```bash
curl -X POST http://localhost:8001/crawled-profiles/cp_NW0DkPyIpcn_69BK4jRZz/enrich \
  -H "Content-Type: application/json" \
  -H "X-App-User-Id: usr_sys_001" \
  -d '{
    "experiences": [
      { "position": "Human Resources Consultant", "company_name": "ValueMomentum",
        "is_current": true },
      { "position": "Technical Recruiter (Product Hiring)", "company_name": "KANARY STAFFING",
        "start_year": 2022, "start_month": 4, "end_year": 2024, "end_month": 1 }
    ],
    "educations": [
      { "school_name": "Andhra University", "degree": "MBA", "field_of_study": "HR" },
      { "school_name": "NTR University", "degree": "Bachelor", "field_of_study": "Pharmacy" }
    ],
    "skills": ["Talent Acquisition", "HR Operations", "Recruitment", "Sourcing",
               "Employee Relations", "LinkedIn Recruiter", "Technical Recruiting"]
  }'
```

Then verify:
```sql
SELECT COUNT(*) FROM experience WHERE crawled_profile_id = 'cp_NW0DkPyIpcn_69BK4jRZz';  -- expect 2
SELECT COUNT(*) FROM education WHERE crawled_profile_id = 'cp_NW0DkPyIpcn_69BK4jRZz';   -- expect 2
SELECT COUNT(*) FROM profile_skill WHERE crawled_profile_id = 'cp_NW0DkPyIpcn_69BK4jRZz'; -- expect 7
SELECT has_enriched_data FROM crawled_profile WHERE id = 'cp_NW0DkPyIpcn_69BK4jRZz';      -- expect true
SELECT embedding IS NOT NULL FROM crawled_profile WHERE id = 'cp_NW0DkPyIpcn_69BK4jRZz';  -- expect true
SELECT search_vector FROM crawled_profile WHERE id = 'cp_NW0DkPyIpcn_69BK4jRZz';          -- expect non-null
```

---

## Files to Modify (Summary)

| # | File | Change |
|---|------|--------|
| 1 | `src/linkedout/crawled_profile/schemas/crawled_profile_api_schema.py` | Add enrich request/response schemas |
| 2 | `src/shared/utils/company_resolver.py` | **New file** — extract `resolve_company()` from PostEnrichmentService (Q3) |
| 3 | `src/linkedout/crawled_profile/services/profile_enrichment_service.py` | **New file** — standalone `ProfileEnrichmentService` with `enrich()` (Q6) |
| 4 | `src/linkedout/crawled_profile/controllers/crawled_profile_controller.py` | Add `POST /{id}/enrich` endpoint + `_get_enrichment_service` dependency |
| 5 | `src/linkedout/enrichment_pipeline/post_enrichment.py` | Add `_to_enrich_schema()`, delegate to `ProfileEnrichmentService.enrich()`, delete 6 methods (Q8), migrate `_resolve_company` to shared util |
| 6 | `<linkedout-fe>/extension/lib/backend/types.ts` | Add enrich payload types |
| 7 | `<linkedout-fe>/extension/lib/profile/mapper.ts` | Add `toEnrichPayload()` + date helpers |
| 8 | `<linkedout-fe>/extension/lib/backend/client.ts` | Add `enrichProfile()` function |
| 9 | `<linkedout-fe>/extension/entrypoints/background.ts` | Await `enrichProfile()` in 3 done paths + fresh-but-unenriched backfill (Q7, Q10, Q11) |
| 10 | `docs/specs/chrome_extension.collab.md` | Update Decision #4 to reflect new `/enrich` endpoint |
| 11-18 | Test files (see Step 6a-h) | Unit + integration tests for all layers |

## Implementation Order

1. Schema (Step 1) — no dependencies
2. Shared company resolver (new file) — no dependencies
3. `ProfileEnrichmentService` (Step 2, new file) — depends on 1 + 2
4. Controller endpoint (Step 3) — depends on 3
5. Backend tests (Step 6a, 6b) — verify backend works
6. Apify migration (Step 4) — big bang replace (Q8)
7. Apify tests (Step 6c, 6d) — verify existing pipeline still works
8. `resolve_company` test (Step 6e)
9. Extension types + mapper + client (Step 5a-c) + tests (Step 6f, 6g)
10. Extension wiring (Step 5d) — await enrich, backfill path
11. Extension fresh-but-unenriched test (Step 6h)
12. Update chrome extension spec Decision #4
13. Manjusha verification (Step 7)

## Agent Usage

| Step | Agent | Why |
|------|-------|-----|
| 1 | Manual | Simple schema addition to existing file |
| 2 | Manual | Utility extraction |
| 3 | Manual | Custom business logic, standalone service |
| 4 | Manual | 10-line addition to existing router — not worth agent overhead |
| 5 | Manual | Apify-specific refactoring |
| 6 | Manual | Extension TypeScript, outside agent scope |
| 6b | **integration-test-creator-agent** | Integration test follows established patterns |
| 6d | **integration-test-creator-agent** | Apify migration integration test |
| 6f-h | Manual | Extension TypeScript tests |
