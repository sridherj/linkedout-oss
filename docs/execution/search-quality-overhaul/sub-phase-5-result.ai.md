# Sub-Phase 5 Result: Explainer Enrichment

**Status:** Completed
**Date:** 2026-03-31

## Changes Made

### 2c. Enriched explainer with work history from DB

**File:** `src/linkedout/intelligence/explainer/why_this_person.py`

1. Added imports for `Session`, `ExperienceEntity`, `ProfileSkillEntity`
2. Added `_fetch_enrichment_data()` method to `WhyThisPersonExplainer`:
   - Two explicit batch queries: experiences (ordered by start_date desc, limited to 5 per profile) and skills (limited to 10 per profile)
   - On any DB failure, returns `{}` so caller skips explanations entirely (Code-2 decision)
   - Groups results by `crawled_profile_id`
3. Updated `_format_result()` to accept optional `enrichment` dict:
   - Appends `MatchEvidence_*` fields from `match_context`
   - Appends `WorkHistory=[...]` and `Skills=[...]` from enrichment data
4. Updated `explain()` signature to accept optional `session: Session`:
   - When session provided, fetches enrichment data for all result profile IDs
   - If fetch fails (returns `{}`), skips explanations entirely with warning log

### 2d. Rewrote explainer prompt

Replaced `_PROMPT_TEMPLATE` with evidence-grounded prompt:
- Added "ONLY reference facts present in the data below. Do NOT invent or assume facts."
- Added guidance to focus on career transitions, matching companies, relevant skills, seniority changes
- Added instruction to mention specific companies for transition queries
- Added instruction to use work history when provided

### 2e. Wired session into explainer call

**File:** `src/linkedout/intelligence/controllers/search_controller.py`

Updated `_run_explainer()` in `_stream_search()`:
- Opens a `DbSessionType.READ` session via `db_session_manager.get_session()`
- Passes session to `explainer.explain()` as keyword argument
- Uses separate session from search agent (Arch-4 decision: intentional)

### Perf-1: Index Verification

Confirmed from entity definitions:
- `ix_exp_profile` index exists on `experience.crawled_profile_id`
- `ix_psk_profile` index exists on `profile_skill.crawled_profile_id`

No migration needed.

## Verification

- All 918 existing tests pass (`pytest tests/ -x -q` — 71s)
- Entity column names verified: `position` (not `title`), `company_name` (direct column, no join needed)
