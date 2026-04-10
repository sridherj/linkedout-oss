# Sub-Phase 5: Explainer Enrichment (Phase 2c + 2d + 2e)

**Working directory:** `./`
**Depends on:** Sub-phase 3 (match_context on SearchResultItem)
**Modifies:**
- `src/linkedout/intelligence/explainer/why_this_person.py`
- `src/linkedout/intelligence/controllers/search_controller.py`

## Context

The `WhyThisPersonExplainer` currently only sees surface data: name, position, company, headline, affinity, dunbar tier. It has no access to work history, skills, or the SQL match evidence. This forces the LLM to fabricate explanations.

### Current explainer code (`why_this_person.py`):
- `_format_result()` (lines 22-39): Formats only surface fields
- `explain()` (line 68): Takes `query` + `results`, no DB access
- `_PROMPT_TEMPLATE` (line 14): Generic "write a 1-sentence explanation"

### Current controller wiring (`search_controller.py`):
- `_run_explainer()` (line 247): Creates `WhyThisPersonExplainer()` with no DB session
- Runs in `asyncio.to_thread` (line 251)

## Review Decisions

- **Arch-2:** Two explicit batch queries (experiences + skills), not one combined query
- **Code-2:** If either batch query fails (DB timeout, etc.), skip explanations entirely for affected profiles. No half-baked guesses.
- **Perf-1:** Verify indexes on `experience.crawled_profile_id` and `profile_skill.crawled_profile_id` during implementation
- **Tests-1:** Unit test data-fetching/formatting, mock LLM

## Tasks

### 2c. Enrich explainer with work history from DB

**File:** `src/linkedout/intelligence/explainer/why_this_person.py`

**Step 1:** Add imports for SQLAlchemy session and entity classes:
```python
from sqlalchemy.orm import Session
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
```

**Step 2:** Add a data-fetching method to `WhyThisPersonExplainer`:

```python
def _fetch_enrichment_data(
    self,
    session: Session,
    crawled_profile_ids: list[str],
) -> dict[str, dict]:
    """Fetch experience + skills for a batch of profiles.

    Returns: {crawled_profile_id: {"experiences": [...], "skills": [...]}}
    """
    enrichment: dict[str, dict] = {pid: {"experiences": [], "skills": []} for pid in crawled_profile_ids}

    # Query 1: Experiences
    try:
        exp_rows = (
            session.query(
                ExperienceEntity.crawled_profile_id,
                ExperienceEntity.title,
                ExperienceEntity.company_name,
                ExperienceEntity.start_date,
                ExperienceEntity.end_date,
                ExperienceEntity.is_current,
            )
            .filter(ExperienceEntity.crawled_profile_id.in_(crawled_profile_ids))
            .order_by(ExperienceEntity.start_date.desc())
            .all()
        )
        for row in exp_rows:
            enrichment[str(row.crawled_profile_id)]["experiences"].append({
                "title": row.title,
                "company": row.company_name,
                "start": str(row.start_date) if row.start_date else None,
                "end": str(row.end_date) if row.end_date else None,
                "current": row.is_current,
            })
    except Exception:
        logger.exception("Failed to fetch experiences for explainer")
        return {}  # Skip entirely per Code-2 decision

    # Query 2: Skills
    try:
        skill_rows = (
            session.query(
                ProfileSkillEntity.crawled_profile_id,
                ProfileSkillEntity.skill_name,
            )
            .filter(ProfileSkillEntity.crawled_profile_id.in_(crawled_profile_ids))
            .all()
        )
        for row in skill_rows:
            enrichment[str(row.crawled_profile_id)]["skills"].append(row.skill_name)
    except Exception:
        logger.exception("Failed to fetch skills for explainer")
        return {}  # Skip entirely per Code-2 decision

    return enrichment
```

**Step 3:** Update `_format_result()` to accept optional enrichment data:

```python
def _format_result(item: SearchResultItem, enrichment: dict | None = None) -> str:
    parts = [f"ID={item.connection_id}", f"Name={item.full_name}"]
    # ... existing surface fields ...

    # Add match_context if present
    if item.match_context:
        for key, val in item.match_context.items():
            parts.append(f"MatchEvidence_{key}={val}")

    # Add enrichment data if present
    if enrichment:
        experiences = enrichment.get("experiences", [])
        if experiences:
            exp_strs = []
            for exp in experiences[:5]:  # Limit to 5 most recent
                exp_str = f"{exp.get('title', '?')} at {exp.get('company', '?')}"
                if exp.get('start'):
                    exp_str += f" ({exp['start']}"
                    exp_str += f"-{exp['end']}" if exp.get('end') else "-present"
                    exp_str += ")"
                exp_strs.append(exp_str)
            parts.append(f"WorkHistory=[{'; '.join(exp_strs)}]")

        skills = enrichment.get("skills", [])
        if skills:
            parts.append(f"Skills=[{', '.join(skills[:10])}]")  # Limit to 10

    return " | ".join(parts)
```

**Step 4:** Update `explain()` signature to accept optional session:

```python
def explain(
    self,
    query: str,
    results: list[SearchResultItem],
    session: Session | None = None,
) -> dict[str, str]:
    """Return {connection_id: '1-sentence explanation'} for each result."""
    if not results:
        return {}

    # Fetch enrichment data if session is available
    enrichment_map: dict[str, dict] = {}
    if session:
        profile_ids = [r.crawled_profile_id for r in results if r.crawled_profile_id]
        if profile_ids:
            enrichment_map = self._fetch_enrichment_data(session, profile_ids)
            if not enrichment_map:
                # DB fetch failed — skip explanations entirely (Code-2)
                logger.warning("Skipping explanations: enrichment data fetch failed")
                return {}

    formatted = "\n".join(
        _format_result(r, enrichment_map.get(r.crawled_profile_id))
        for r in results
    )
    # ... rest of existing logic ...
```

**Important:** Check the actual column names on `ExperienceEntity` — `company_name` might be a property or the column might be named differently. The experience table links to company via `company_id`, so you may need to join to `CompanyEntity` to get the company name, OR use a column like `company_name` if it exists as a denormalized field. Read the entity file to confirm.

### 2d. Rewrite explainer prompt

**File:** `src/linkedout/intelligence/explainer/why_this_person.py`

Replace `_PROMPT_TEMPLATE` (line 14):

```python
_PROMPT_TEMPLATE = """For each person below, write a 1-sentence explanation of why they match the query "{query}".
ONLY reference facts present in the data below. Do NOT invent or assume facts.
Focus on specific evidence: career transitions, matching companies, relevant skills, seniority changes.
If the query asks about transitions (e.g., "IT to product"), mention the specific companies involved.
If work history is provided, use it to ground your explanation.
Format: one line per person, "ID: explanation"

Results:
{formatted_results}"""
```

### 2e. Wire session into explainer call

**File:** `src/linkedout/intelligence/controllers/search_controller.py`

The current `_run_explainer()` (line 247) creates the explainer without a DB session:
```python
def _run_explainer() -> dict[str, str]:
    explainer = WhyThisPersonExplainer()
    return explainer.explain(request.query, results)
```

Change to open a DB session and pass it:

```python
def _run_explainer() -> dict[str, str]:
    explainer = WhyThisPersonExplainer()
    # Open a new session for explainer DB queries
    from linkedout.database import get_session  # or however sessions are created
    with get_session() as session:
        return explainer.explain(request.query, results, session=session)
```

**Important:** Check how the controller currently gets its DB session. It likely already has a session factory or uses dependency injection. Use the same pattern. Look at how `SearchAgent` gets its session (it has `self._session` per `search_agent.py`). The controller may already have access to a session — if so, pass it directly instead of creating a new one.

**Review Decision Arch-4:** Having a separate DB session for the explainer (vs. reusing the search agent's session) is accepted and documented as intentional.

### Perf-1: Verify indexes

Before finishing, verify that these indexes exist:
```sql
-- Run against the DB
SELECT indexname FROM pg_indexes WHERE tablename = 'experience' AND indexdef LIKE '%crawled_profile_id%';
SELECT indexname FROM pg_indexes WHERE tablename = 'profile_skill' AND indexdef LIKE '%crawled_profile_id%';
```

If indexes are missing, add them via Alembic migration.

## Verification

1. **Unit test (Tests-1):** Test `_fetch_enrichment_data` with a mock session. Test `_format_result` with enrichment data. Mock the LLM call.
2. **Integration test:** Call `explain()` with a real session and verify enrichment data appears in the formatted prompt.
3. Run existing tests: `cd . && pytest tests/ -x -q --timeout=30`
4. Manual smoke test: Query "moved from IT to product" — explanation should mention specific companies.
