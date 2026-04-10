# Plan: Pre-Commit OSS Audit Cleanup

## Context
First commit to linkedout-oss. Audit identified 5 categories of problematic files. Decisions made via interview. This plan covers all unstage operations, file edits, and .gitignore updates needed before the commit lands.

---

## Decisions Summary

| # | Issue | Decision |
|---|-------|----------|
| 1 | Real LinkedIn PII in fixtures (478 profiles, 8k+ related records) | Replace with fake data |
| 2 | Real LinkedIn URLs in apify_sample_response.json | Scrub real identifiers → fakes |
| 3 | Personal machine paths in .claude/settings.json | gitignore + unstage |
| 4 | Session telemetry files (plan_and_progress/sessions/) | Unstage + gitignore pattern |
| 5 | Internal backend/docs/ (~130 files) | Unstage entirely |

---

## Step-by-Step Execution

### Step 1 — Unstage backend/docs/ entirely
```bash
git restore --staged backend/docs/
```
Add to `backend/.gitignore` (or root `.gitignore`):
```
backend/docs/
```
> These are internal private project planning artifacts. If OSS-specific docs are added later, they'll be committed intentionally.

---

### Step 2 — Unstage session telemetry files
```bash
git restore --staged plan_and_progress/sessions/
git restore --staged backend/plan_and_progress/sessions/
git restore --staged extension/plan_and_progress/sessions/
git restore --staged backend/src/plan_and_progress/sessions/
git restore --staged .claude/skills/plan_and_progress/sessions/
```
Add to root `.gitignore`:
```
# Claude session telemetry (auto-generated, never commit)
plan_and_progress/sessions/
.claude/skills/plan_and_progress/sessions/
```

---

### Step 3 — Unstage + gitignore .claude/settings.json
```bash
git restore --staged .claude/settings.json
git restore --staged backend/src/.claude/settings.json
```
Add to root `.gitignore`:
```
# Personal Claude Code hook config (machine-specific paths)
.claude/settings.json
```
Add to `backend/src/.gitignore` (or backend/.gitignore):
```
.claude/settings.json
```
> Local files remain untouched so your hooks keep working.

---

### Step 4 — Replace fixtures with fake data
**File:** `backend/src/dev_tools/db/fixtures/` (4 JSON files)

Write a one-off Python script `scripts/generate-fake-fixtures.py` that:
1. Generates ~20 fake `crawled_profiles` using obviously fake identifiers
   - IDs: `cp_fake_001` through `cp_fake_020`
   - linkedin_url: `https://www.linkedin.com/in/fake-user-001` etc.
   - first_name/last_name: `Fake`, `User001` etc.
   - headline/about: generic placeholder strings
   - Realistic-looking but clearly synthetic: city/country from a small fixed list
2. Generates ~3 `companies` with fake names (co_fake_001 etc.)
3. Generates ~40 `experiences` (2 per profile avg) referencing fake profile IDs
4. Generates ~20 `educations` (1 per profile avg)
5. Generates ~60 `profile_skills` (3 per profile avg)
6. Writes all 5 JSON files in place

Schema to preserve exactly (from audit):
- `crawled_profiles`: id, linkedin_url, public_identifier, first_name, last_name, full_name, headline, about, location_city, location_state, location_country, location_country_code, connections_count, follower_count, current_company_name, current_position, company_id, seniority_level, function_area, has_enriched_data, data_source, profile_image_url, open_to_work, premium
- `experiences`: id, crawled_profile_id, position, company_name, company_id, employment_type, start_year, start_month, end_year, end_month, is_current, seniority_level, function_area, location
- `educations`: id, crawled_profile_id, school_name, degree, field_of_study, start_year, end_year
- `profile_skills`: id, crawled_profile_id, skill_name, endorsement_count
- `companies`: id, canonical_name, normalized_name, linkedin_url, universal_name, website, domain, industry, founded_year, hq_city, hq_country, employee_count_range, estimated_employee_count, size_tier, network_connection_count, enrichment_sources

After generation, run the script and verify the JSON files look clean, then commit.

**No test changes needed.** The only integration test that touches seed data (`test_seed_pipeline.py`) uses a separate SQLite fixture (`backend/tests/fixtures/test-seed-core.sqlite`) with its own independently generated synthetic data. No test asserts on specific names, URLs, or IDs from these JSON files.

---

### Step 5 — Scrub apify_sample_response.json
**File:** `backend/docs/reference/apify_sample_response.json`

BUT — this file is in `backend/docs/` which we're gitignoring in Step 1. So this file is already handled. Skip.

---

## .gitignore Changes Summary

### Root `.gitignore` — add:
```
# Personal Claude Code hook config (machine-specific paths)
.claude/settings.json

# Claude session telemetry (auto-generated, never commit)
plan_and_progress/sessions/
.claude/skills/plan_and_progress/sessions/
```

### `backend/.gitignore` (or new `backend/src/.gitignore`) — add:
```
# Personal Claude Code hook config
.claude/settings.json

# Internal planning docs (private project artifacts)
backend/docs/
```

> Note: `backend/docs/` gitignore goes in the root `.gitignore` since the path is relative to root.

---

## Files Modified
- Root `.gitignore` — add 3 ignore patterns
- `backend/.gitignore` — add `.claude/settings.json` pattern
- `backend/src/dev_tools/db/fixtures/crawled_profiles.json` — replaced with fake data
- `backend/src/dev_tools/db/fixtures/experiences.json` — replaced with fake data
- `backend/src/dev_tools/db/fixtures/educations.json` — replaced with fake data
- `backend/src/dev_tools/db/fixtures/profile_skills.json` — replaced with fake data
- `backend/src/dev_tools/db/fixtures/companies.json` — replaced with fake data

## Files Unstaged (not in commit)
- `backend/docs/` (entire directory, ~130 files)
- `plan_and_progress/sessions/` (4 files)
- `backend/plan_and_progress/sessions/` (~3 files)
- `extension/plan_and_progress/sessions/` (~2 files)
- `backend/src/plan_and_progress/sessions/` (~3 files)
- `.claude/skills/plan_and_progress/sessions/` (~2 files)
- `.claude/settings.json`
- `backend/src/.claude/settings.json`

---

## Verification
1. `git diff --cached --name-only | grep "backend/docs"` → should return nothing
2. `git diff --cached --name-only | grep "plan_and_progress/sessions"` → should return nothing
3. `git diff --cached --name-only | grep "settings.json"` → should return nothing
4. `cat backend/src/dev_tools/db/fixtures/crawled_profiles.json | python3 -c "import json,sys; d=json.load(sys.stdin); print([p['linkedin_url'] for p in d[:3]])"` → should show `/fake-user-` URLs
5. Run `uv run python -m dev_tools.db.load_fixtures --dry-run` to confirm fake fixtures load without errors
