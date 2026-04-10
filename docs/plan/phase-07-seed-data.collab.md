# Phase 7: Seed Data Pipeline — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Ready for implementation
**Phase goal:** Users get a useful company database without needing Apify enrichment. A fresh install can run `linkedout download-seed && linkedout import-seed` and have a populated company database.
**Dependencies:** Phase 6 (Code Cleanup) — CLI surface refactor (6E) must be complete so the `linkedout` namespace exists; Procrastinate removal (6C) complete; project_mgmt stripped (6B).
**Delivers:** Two CLI commands (`download-seed`, `import-seed`), a curation pipeline for maintainers, seed SQLite files published as GitHub Release assets, and a seed manifest for integrity verification.

---

## Phase 0 Decisions That Constrain This Phase

| Decision Doc | Constraint on Phase 7 |
|---|---|
| `docs/decision/cli-surface.md` | `linkedout download-seed` and `linkedout import-seed` are the user-facing commands. Flat namespace, no subgroups. Both follow the Operation Result Pattern (Progress -> Summary -> Gaps -> Next steps -> Report path). |
| `docs/decision/env-config-design.md` | Seed files download to `~/linkedout-data/seed/`. Config via `LINKEDOUT_DATA_DIR` override. No separate `~/.linkedout/` directory. |
| `docs/decision/logging-observability-strategy.md` | Both commands log to `~/linkedout-data/logs/cli.log` using loguru via `get_logger()`. Each produces a readiness report to `~/linkedout-data/reports/`. Human-readable log format (no JSON logs). |
| `docs/decision/queue-strategy.md` | No Procrastinate. Import runs synchronously. |
| `docs/decision/2026-04-07-data-directory-convention.md` | `~/linkedout-data/` is the default data directory. |
| `docs/decision/2026-04-07-embedding-model-selection.md` | Seed data does NOT include embeddings — embeddings are generated locally after import (Phase 5's `linkedout embed`). Seed profiles ship raw text only. |

---

## Seed Data Scope (from Plan Phase 0A review)

Seed data ships **10 tables** (everything not under tenant/BU/user scope):

| Table | Entity | Tenant-scoped? | Notes |
|-------|--------|----------------|-------|
| `company` | `CompanyEntity` | No | Company reference data |
| `company_alias` | `CompanyAliasEntity` | No | Company name variations |
| `role_alias` | `RoleAliasEntity` | No | Job title normalization |
| `funding_round` | `FundingRoundEntity` | No | Public funding data |
| `startup_tracking` | `StartupTrackingEntity` | No | Startup metrics |
| `growth_signal` | `GrowthSignalEntity` | No | Growth indicators |
| `crawled_profile` | `CrawledProfileEntity` | No | Profile snapshots from SJ's network |
| `experience` | `ExperienceEntity` | No | Work history |
| `education` | `EducationEntity` | No | Education history |
| `profile_skill` | `ProfileSkillEntity` | No | Skills/endorsements |

**Excluded from seed data** (tenant/BU/user-scoped):
- `connection` — user's personal connections
- `contact_source` — user's address book imports
- `enrichment_event` — user's enrichment history
- `import_job` — user's import history
- `search_session`, `search_turn`, `search_tag` — user's query history

**Two tiers:**
- **Core (~50MB):** ~5K companies (companies where SJ's real connections work) + full profile/role/funding data for those companies
- **Full (~500MB):** ~50-100K companies (top global companies ranked by employee count, funding, web traffic from PDL data) + same profile data

The only difference between tiers is company coverage breadth. Profile, role alias, funding, and experience data are identical in both.

---

## Detailed Task Breakdown

### 7A. Seed Data Curation Script (Maintainer Tool)

**Goal:** One-time script to extract seed data from the production LinkedOut PostgreSQL database into SQLite files. This is a maintainer-only tool, not user-facing.

**Acceptance criteria:**
- Script connects to the production LinkedOut DB (via `DATABASE_URL`) and exports the 10 seed tables to a SQLite file
- Core tier: filters companies to those where at least one `crawled_profile` has an `experience` record (i.e., companies where SJ's connections actually work)
- Full tier: exports all companies above a configurable threshold (employee count > 0 OR has funding data OR has web traffic data)
- Profile data is stripped of PII where appropriate: no email addresses, no phone numbers, no profile photos. LinkedIn URLs and public names are retained (they're public data)
- Each SQLite file includes a `_metadata` table with: version, created_at, table_count, row_counts per table, source_db_hash (for reproducibility)
- Script is idempotent — re-running produces identical output for the same source data

**File targets:**
- `backend/src/dev_tools/seed_export.py` — new file, the curation script
- Uses existing entity definitions from `backend/src/linkedout/*/entities/`
- Reads from PostgreSQL (via SQLAlchemy), writes to SQLite (via `sqlite3` stdlib)

**Integration points:**
- Reuses `db_session_manager` from `backend/src/shared/infra/db/db_session_manager.py` for source DB access
- Existing `seed_companies.py` has some patterns for company data handling — reference but don't extend (it's YC/PDL-specific)

**Complexity:** L

---

### 7B. Seed Manifest

**Goal:** Machine-readable manifest that describes available seed files, their sizes, checksums, and version.

**Acceptance criteria:**
- `seed-manifest.json` published alongside seed files in GitHub Releases
- Contains: `version` (semver matching the release), `created_at`, `files` array with per-file `name`, `size_bytes`, `sha256`, `tier` (core|full), `table_counts` (per-table row counts)
- `linkedout download-seed` fetches and validates against this manifest
- Manifest is generated automatically by the curation script (7A)

**File targets:**
- Manifest generation is part of `backend/src/dev_tools/seed_export.py` (writes `seed-manifest.json` alongside SQLite files)
- Manifest schema documented in `seed-data/README.md` (new file)

**Complexity:** S

---

### 7C. `linkedout download-seed` CLI Command

**Goal:** User-facing command to download seed data from GitHub Releases with progress bar, checksum verification, and tiered prompt.

**Acceptance criteria:**
- Downloads seed SQLite from the latest GitHub Release (or a specified `--version`)
- Default: downloads core tier (~50MB). `--full` flag downloads full tier (~500MB)
- Shows download progress bar (tqdm or rich.progress)
- Verifies SHA256 checksum against `seed-manifest.json` (downloaded first, ~1KB)
- If file already exists and checksum matches, skip download with message: `Seed data already downloaded (core v0.1.0, checksum OK). Use --force to re-download.`
- `--force` flag re-downloads even if file exists
- `--output DIR` overrides download location (default: `~/linkedout-data/seed/`)
- On network failure: clear error message with retry guidance
- Follows Operation Result Pattern: progress -> summary -> report path
- Produces report: `~/linkedout-data/reports/download-seed-YYYYMMDD-HHMMSS.json`

**File targets:**
- `backend/src/linkedout/cli/commands/download_seed.py` — new file
- Registered in `backend/src/linkedout/cli/cli.py` (the new flat CLI module from Phase 6E)

**CLI contract (from `docs/decision/cli-surface.md`):**
```
linkedout download-seed [OPTIONS]

Options:
  --full                Download full dataset (~500MB) instead of core (~50MB)
  --output DIR          Download location (default: ~/linkedout-data/seed/)
  --version VERSION     Specific release version (default: latest)
  --force               Re-download even if file exists and checksum matches
```

**Dependencies:**
- Phase 6E (CLI surface refactor) must be complete — the `linkedout` CLI entry point must exist
- Phase 3K/3L (readiness report framework / operation result pattern) — if not yet available, implement a minimal version inline and refactor later

**Complexity:** M

---

### 7D. `linkedout import-seed` CLI Command

**Goal:** User-facing command to import downloaded SQLite seed data into local PostgreSQL. Idempotent.

**Acceptance criteria:**
- Reads SQLite seed file from `~/linkedout-data/seed/` (auto-detect) or explicit `--seed-file PATH`
- Imports all 10 tables into PostgreSQL
- **Upsert strategy:** For each row, check if a matching record exists (by primary key or unique constraint). If yes, update. If no, insert. This makes the command idempotent.
- Shows per-table progress: `Importing company... 4,521/4,521`
- Summary output per table: inserted N, updated N, skipped N
- `--dry-run` flag: parse and report what would be imported without writing
- Handles foreign key ordering: companies before company_alias, crawled_profile before experience/education/profile_skill
- Follows Operation Result Pattern
- Produces report: `~/linkedout-data/reports/seed-import-YYYYMMDD-HHMMSS.json`
- On re-run with same seed file: all rows show as "skipped" (already exists, data matches)

**File targets:**
- `backend/src/linkedout/cli/commands/import_seed.py` — new file
- Registered in `backend/src/linkedout/cli/cli.py`

**CLI contract (from `docs/decision/cli-surface.md`):**
```
linkedout import-seed [OPTIONS]

Options:
  --seed-file PATH      Path to seed SQLite file (default: auto-detect in ~/linkedout-data/seed/)
  --dry-run             Report what would be imported, do not write
```

**Import order (respecting FK constraints):**
1. `company`
2. `company_alias` (FK → company)
3. `role_alias` (no FK)
4. `funding_round` (FK → company)
5. `startup_tracking` (FK → company)
6. `growth_signal` (FK → company)
7. `crawled_profile` (FK → company via current_company_id, nullable)
8. `experience` (FK → crawled_profile, FK → company)
9. `education` (FK → crawled_profile)
10. `profile_skill` (FK → crawled_profile)

**Integration points:**
- Uses `db_session_manager` for PostgreSQL writes
- Uses existing entity classes for ORM-based inserts (type safety, constraint validation)
- Or uses raw SQL `INSERT ... ON CONFLICT DO UPDATE` for performance with large datasets — decision depends on performance testing with ~50K rows
- **Batch size (review finding 2026-04-07):** Use `executemany` or bulk `INSERT ... VALUES` with 1000-row batches. Target < 5 minutes for the full seed (~100K companies, ~500MB). Row-by-row insertion will be too slow for the full tier. If batch inserts are still too slow, use `psycopg2.copy_expert()` with `COPY FROM STDIN`.

**Complexity:** L

---

### 7E. Seed Data Directory Structure

**Goal:** Establish the `seed-data/` directory in the repo with documentation and helper scripts.

**Acceptance criteria:**
- `seed-data/README.md` — documents the seed data pipeline: what's included, how tiers differ, how to regenerate (maintainer instructions), manifest schema
- `seed-data/.gitkeep` — directory exists in repo but seed SQLite files are .gitignored (they're too large for git; published as GitHub Release assets)
- `.gitignore` updated to exclude `seed-data/*.sqlite`, `seed-data/*.db`

**File targets:**
- `seed-data/README.md` — new file
- `seed-data/.gitkeep` — new file
- Update root `.gitignore`

**Complexity:** S

---

### 7F. GitHub Release Publishing (Manual + Documentation)

**Goal:** Document the process for publishing seed data as GitHub Release assets. Optionally, create a GitHub Actions workflow for automation.

**Acceptance criteria:**
- Document the manual release process in `seed-data/README.md`:
  1. Run curation script to generate SQLite files + manifest
  2. Create GitHub Release (tag matches `seed-manifest.json` version)
  3. Upload SQLite files + `seed-manifest.json` as release assets
- GitHub Release URL pattern documented so `download-seed` can construct the URL programmatically
- Consider a GitHub Actions workflow (`release-seed-data.yml`) that automates steps 2-3 when triggered manually — but this is optional for v1

**File targets:**
- Documentation in `seed-data/README.md` (update from 7E)
- Optional: `.github/workflows/release-seed-data.yml` — new file

**Complexity:** S (docs only) / M (with GH Actions workflow)

---

### 7G. Integration Testing

**Goal:** Verify the full download → import → verify flow works end-to-end.

**Acceptance criteria:**
- Unit tests for SQLite → PostgreSQL import logic (mock SQLite, real test DB)
- Unit tests for checksum verification
- Unit tests for idempotent upsert behavior (import same data twice → second run is all skips)
- Unit tests for FK ordering (import with wrong order → useful error, not DB constraint violation)
- Integration test: create a small test seed SQLite (~10 rows per table), run `import-seed`, verify data in PostgreSQL matches
- Integration test: `download-seed --dry-run` with a mocked GitHub Release URL
- Test the Operation Result Pattern output for both commands

**File targets:**
- `backend/tests/unit/cli/test_import_seed.py` — new file
- `backend/tests/unit/cli/test_download_seed.py` — new file
- `backend/tests/integration/cli/test_seed_pipeline.py` — new file
- Test fixtures: `backend/tests/fixtures/test-seed-core.sqlite` — small SQLite with ~10 rows per table

**Complexity:** M

---

## File-Level Implementation Summary

### New Files

| File | Task | Description |
|------|------|-------------|
| `backend/src/dev_tools/seed_export.py` | 7A | Maintainer curation script (PostgreSQL → SQLite) |
| `backend/src/linkedout/cli/commands/download_seed.py` | 7C | `linkedout download-seed` command |
| `backend/src/linkedout/cli/commands/import_seed.py` | 7D | `linkedout import-seed` command |
| `seed-data/README.md` | 7E | Seed data documentation |
| `seed-data/.gitkeep` | 7E | Directory placeholder |
| `backend/tests/unit/cli/test_import_seed.py` | 7G | Unit tests for import |
| `backend/tests/unit/cli/test_download_seed.py` | 7G | Unit tests for download |
| `backend/tests/integration/cli/test_seed_pipeline.py` | 7G | Integration tests |
| `backend/tests/fixtures/test-seed-core.sqlite` | 7G | Test fixture |
| `.github/workflows/release-seed-data.yml` | 7F | Optional: seed release automation |

### Modified Files

| File | Task | Changes |
|------|------|---------|
| `backend/src/linkedout/cli/cli.py` | 7C, 7D | Register `download-seed` and `import-seed` commands |
| `.gitignore` | 7E | Add `seed-data/*.sqlite`, `seed-data/*.db` |
| `backend/requirements.txt` | 7C | Add `tqdm` (if not already present) for progress bars |

### Files Referenced (Read-Only)

| File | Why |
|------|-----|
| `backend/src/linkedout/company/entities/company_entity.py` | Schema for company table |
| `backend/src/linkedout/company_alias/entities/company_alias_entity.py` | Schema for company_alias |
| `backend/src/linkedout/role_alias/entities/role_alias_entity.py` | Schema for role_alias |
| `backend/src/linkedout/funding/entities/funding_round_entity.py` | Schema for funding_round |
| `backend/src/linkedout/funding/entities/startup_tracking_entity.py` | Schema for startup_tracking |
| `backend/src/linkedout/funding/entities/growth_signal_entity.py` | Schema for growth_signal |
| `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py` | Schema for crawled_profile |
| `backend/src/linkedout/experience/entities/experience_entity.py` | Schema for experience |
| `backend/src/linkedout/education/entities/education_entity.py` | Schema for education |
| `backend/src/linkedout/profile_skill/entities/profile_skill_entity.py` | Schema for profile_skill |
| `backend/src/shared/infra/db/db_session_manager.py` | DB session management |

---

## Testing Strategy

### Layer 1: Unit Tests (run in CI, no external deps)
- SQLite parsing and row extraction
- Checksum computation and verification
- Manifest parsing and validation
- FK ordering logic
- Upsert conflict resolution logic (with in-memory SQLite as target)
- Operation Result output formatting
- Progress callback mechanics

### Layer 2: Integration Tests (run in CI, require test PostgreSQL)
- Full import pipeline: test SQLite → PostgreSQL with real schema
- Idempotency: import twice, verify counts
- FK constraint validation: correct ordering imports cleanly
- Partial import recovery: interrupt mid-import, re-run, verify no duplicates
- Dry-run mode: verify no writes occur
- Report generation: verify JSON report structure and content

### Layer 3: Manual/Nightly (not in regular CI)
- Full-size seed file import (50MB core)
- Download from real GitHub Release URL
- Performance benchmarking: time to import N rows

---

## Exit Criteria Verification Checklist

- [ ] `linkedout download-seed` downloads core seed (~50MB) with progress bar and checksum verification
- [ ] `linkedout download-seed --full` downloads full seed (~500MB)
- [ ] `linkedout import-seed` loads all 10 tables into PostgreSQL
- [ ] Running `import-seed` twice on the same data is safe (idempotent, second run shows all skips)
- [ ] Both commands follow Operation Result Pattern (progress -> summary -> gaps -> next steps -> report path)
- [ ] Both commands produce JSON reports in `~/linkedout-data/reports/`
- [ ] Both commands log to `~/linkedout-data/logs/cli.log`
- [ ] `--dry-run` works on `import-seed` (reports without writing)
- [ ] `--force` works on `download-seed` (re-downloads even if cached)
- [ ] Seed manifest (`seed-manifest.json`) is generated by curation script and validated by download command
- [ ] Seed SQLite files are published as GitHub Release assets
- [ ] `seed-data/README.md` documents the pipeline for maintainers
- [ ] Unit and integration tests pass in CI
- [ ] Fresh install can run `linkedout download-seed && linkedout import-seed` and have a populated company database
- [ ] `linkedout status` reflects imported seed data (company count, etc.)

---

## Complexity Summary

| Task | Size | Effort Notes |
|------|------|-------------|
| 7A. Seed curation script | L | Complex SQL queries for tier filtering, SQLite export, PII stripping, metadata table |
| 7B. Seed manifest | S | JSON generation, straightforward |
| 7C. `download-seed` command | M | HTTP download, progress bar, checksum, GitHub Release URL construction |
| 7D. `import-seed` command | L | SQLite → PostgreSQL ETL, upsert logic, FK ordering, 10 tables, idempotency |
| 7E. Seed directory structure | S | Files + .gitignore update |
| 7F. GitHub Release publishing | S | Documentation, optional GH Actions |
| 7G. Integration testing | M | Test fixtures, unit + integration tests |

---

## Open Questions

1. **GitHub Release URL pattern:** The `download-seed` command needs to know where to find seed files. Options:
   - (a) Hardcode `https://github.com/sridherj/linkedout-oss/releases/download/<version>/` — repo owner is `sridherj` (resolved in Phase 1)
   - (b) Store the repo URL in `config.yaml` — more flexible, set during setup
   - (c) Use GitHub API to find latest release — works but requires internet and potentially rate limiting
   - **Recommendation:** Option (a) with a `LINKEDOUT_SEED_URL` env var override for forks. The repo URL is known at build time for the official release.

2. **SQLite vs pg_dump for seed format:** The plan specifies SQLite. Alternatives:
   - SQLite: portable, inspectable, single file, no PostgreSQL version coupling. Requires ETL code.
   - pg_dump (custom format): native PostgreSQL, fastest import via `pg_restore`. But version-coupled and less inspectable.
   - CSV bundle: most portable but loses type information and is harder to keep atomic.
   - **Recommendation:** SQLite as specified. The ETL code (7D) is the main cost, but it gives us format independence and inspectability.

3. **Profile PII in seed data:** `crawled_profile` contains names and LinkedIn URLs (public data). Should we strip anything beyond email/phone?
   - Names and LinkedIn URLs are publicly visible on LinkedIn — no privacy concern for public profiles
   - Profile photos are URLs pointing to LinkedIn CDN — they break over time anyway, safe to include
   - **Recommendation:** Strip email, phone, and any internal notes. Keep names, LinkedIn URLs, headlines, summaries, and photo URLs.

4. **Seed data freshness for CI:** The test fixture SQLite (7G) is committed to the repo. Should CI also test with a real seed file?
   - Real seed files are 50-500MB — too large for CI artifact caching
   - The test fixture covers the same schema, just with fewer rows
   - **Recommendation:** CI uses the small test fixture. Nightly/release pipeline tests with real seed files.

5. **Company deduplication between seed and user data:** When a user imports their LinkedIn connections (Phase 9), some companies will already exist from seed data. How does the import pipeline handle this?
   - The `import-connections` command (Phase 6E) already handles company matching via `company_alias` lookups
   - Seed data provides the company reference data that makes this matching work
   - **No additional work needed in Phase 7** — this is already handled by the import pipeline's existing company matching logic

6. **Embedding column in seed data:** `crawled_profile` has an `embedding` column (pgvector). Should seed data include pre-computed embeddings?
   - Per the embedding model decision doc, the default model is `nomic-embed-text-v1.5` (768d). If we ship embeddings, they're locked to one model/dimension.
   - Users who choose OpenAI embeddings (1536d) would need to re-embed everything anyway.
   - Shipping embeddings would increase seed file size significantly (~768 floats * 4 bytes * N profiles).
   - **Recommendation:** Do NOT include embeddings in seed data. Users run `linkedout embed` after import to generate embeddings with their chosen provider. The `download-seed` summary should mention this as a next step.
