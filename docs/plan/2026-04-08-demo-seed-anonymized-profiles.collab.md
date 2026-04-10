# Plan: Demo Seed Data — Anonymized Profiles from Real Network

## Context
The OSS repo needs a "taste test" experience — when a user first installs LinkedOut
and runs `import-seed`, they should immediately be able to query 2K realistic profiles
before importing their own LinkedIn connections. These demo profiles are sampled from
SJ's real 22K enriched connections, anonymized (fake names/URLs), and auto-removed
when the user imports their real data.

## Design Decisions (from interview)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Demo data marker | `data_source='demo-seed'` + `cp_demo_` ID prefix (belt + suspenders) |
| 2 | Cleanup trigger | Auto-cleanup on first `import-connections` |
| 3 | Companies | Reference real seed companies (not fake ones) |
| 4 | Data source | Real production DB (22K enriched profiles), anonymized |
| 5 | Demo user | System IDs (tenant_sys_001, bu_sys_001, usr_sys_001) |
| 6 | Architecture | Separate scripts, combined seed SQLite file |

## ID Conventions

| Table | Demo ID pattern | Example |
|-------|----------------|---------|
| crawled_profile | `cp_demo_NNNN` | `cp_demo_0001` |
| experience | `exp_demo_NNNNNN` | `exp_demo_000001` |
| education | `edu_demo_NNNN` | `edu_demo_0001` |
| profile_skill | `psk_demo_NNNNNN` | `psk_demo_000001` |
| connection | `conn_demo_NNNN` | `conn_demo_0001` |

All crawled_profile records: `data_source = 'demo-seed'`

## Files to Create/Modify

### New: `scripts/generate-demo-seed.py`
The core script. Connects to real production DB, builds anonymized demo data.

**Sampling strategy (2K from 22K, stratified):**
1. Query distinct (seniority_level, function_area, location_country) buckets
2. Proportional sampling from each bucket to preserve the real distribution
3. Ensure minimum 1 representative from each bucket (so rare categories appear)
4. For each sampled profile, also pull its experiences, education, profile_skill records

**Anonymization (what changes):**
- `first_name` / `last_name` / `full_name` → Faker names (locale-matched: Indian names for India, etc.)
- `linkedin_url` / `public_identifier` → `https://www.linkedin.com/in/demo-user-NNNN`
- `headline` → reconstructed from real `current_position` + `current_company_name`
- `about` → templated: "Experienced {position} with expertise in {top_skills}..."
- `profile_image_url` → null
- `connections_count` / `follower_count` → jittered ±20%
- `id` → `cp_demo_NNNN`
- `data_source` → `demo-seed`

**What stays real (not PII, valuable for demo quality):**
- `current_company_name`, `company_id` (references real seed companies)
- `location_city`, `location_state`, `location_country`, `location_country_code`
- `seniority_level`, `function_area`
- `open_to_work`, `premium` (booleans, no PII)
- All experience records (real positions, real companies, real dates — just new IDs)
- All education records (real schools, degrees, fields — just new IDs)
- All skill records (real skill names — just new IDs)
- Experience `position`, `company_name`, `company_id`, `employment_type`, dates, `location`
- Education `school_name`, `degree`, `field_of_study`, years

**Connection records (one per demo profile):**
- `id` → `conn_demo_NNNN`
- `tenant_id` → `tenant_sys_001`
- `bu_id` → `bu_sys_001`
- `app_user_id` → `usr_sys_001`
- `crawled_profile_id` → `cp_demo_NNNN`
- `connected_at` → randomized within last 2 years

**Output:** Appends 5 tables (crawled_profile, experience, education, profile_skill, connection) to the existing seed-core.sqlite.

**Expected volumes:**
- ~2,000 crawled_profile records
- ~12,000 experience records (~6 per profile)
- ~4,400 education records (~2.2 per profile)
- ~10,000 profile_skill records (capped at 5 per profile for seed size)
- ~2,000 connection records (1 per profile)

### Modify: `backend/src/linkedout/commands/import_seed.py`
- **Restore profile tables to IMPORT_ORDER** but as optional — the seed file may or may not include them
- Keep the 6 company tables as required
- Add `connection` to IMPORT_ORDER (after profile_skill)
- Update `_validate_seed_file()`: only require company tables; profile tables are optional
- Restore `BOOL_COLUMNS` entries for `crawled_profile` and `experience`

### Modify: `backend/src/dev_tools/seed_export.py`
- Keep as-is (exports only 6 company tables) — demo profiles are added by a separate script, not by seed_export

### Modify: `backend/src/linkedout/commands/import_connections.py`
- Add demo data detection at the start of the import flow
- If `crawled_profile` records with `data_source='demo-seed'` exist:
  - Print warning with counts
  - Delete in FK-safe order: connection (WHERE crawled_profile_id LIKE 'cp_demo_%'), profile_skill, education, experience, crawled_profile
  - Report what was removed
- Then proceed with normal import

### Modify: `backend/src/dev_tools/db/fixtures/` (the 20 fake profiles)
- These were just replaced with 20 simple fakes. That's fine for `load_fixtures`.
- The demo seed is a separate, richer dataset generated from real data.
- No changes needed here.

### Modify: `scripts/generate-fake-fixtures.py`
- Rename or update to clarify this is for dev fixture data only, not the demo seed.
- No functional changes.

## Execution Order

1. **Update import_seed.py** — restore profile tables as optional in IMPORT_ORDER, add connection table
2. **Build generate-demo-seed.py** — the core anonymization/sampling script
3. **Update import_connections command** — add auto-cleanup of demo data
4. **Run generate-demo-seed.py** locally against production DB — produces the demo data appended to seed-core.sqlite (this file is gitignored, published as release asset)
5. **Stage the new/modified files** into the commit

## Verification

1. `python scripts/generate-demo-seed.py --db-url $DB --seed-file /tmp/test-seed.sqlite` → creates file with 5 demo tables
2. Inspect: `sqlite3 /tmp/test-seed.sqlite "SELECT COUNT(*), data_source FROM crawled_profile GROUP BY data_source"` → shows 2000, demo-seed
3. Inspect: `sqlite3 /tmp/test-seed.sqlite "SELECT id FROM crawled_profile LIMIT 3"` → cp_demo_0001, cp_demo_0002, ...
4. Inspect: no real names: `sqlite3 /tmp/test-seed.sqlite "SELECT first_name, last_name, linkedin_url FROM crawled_profile LIMIT 5"` → Faker names, demo URLs
5. Inspect: real companies preserved: `sqlite3 /tmp/test-seed.sqlite "SELECT DISTINCT current_company_name FROM crawled_profile LIMIT 10"` → real company names
6. `import_seed_command` with demo seed → successfully imports both company + demo data
7. `import_connections` → detects demo data, removes it, imports real connections
