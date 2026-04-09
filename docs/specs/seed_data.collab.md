---
feature: seed-data
module: seed-data
linked_files:
  - seed-data/seed-manifest.json
  - seed-data/seed-core.sqlite
  - seed-data/seed-full.sqlite
  - seed-data/README.md
  - backend/src/linkedout/commands/download_seed.py
  - backend/src/linkedout/commands/import_seed.py
  - scripts/verify-seed-checksums.py
version: 1
last_verified: "2026-04-09"
---

# Seed Data

**Created:** 2026-04-09 -- Written from scratch for LinkedOut OSS

## Intent

Provide pre-curated company reference data so new LinkedOut installations have useful company intelligence (names, aliases, funding rounds, role normalization) without requiring users to run Apify enrichment or manually populate the database. Seed data covers public, non-tenant-scoped company tables only -- no personal profile data.

## Behaviors

### Seed Data Concept

- **Company reference data only**: Seed data covers 6 tables of public company intelligence that is shared across all tenants. These tables provide the foundation for company matching during profile import, role title normalization, and startup tracking. Personal data (profiles, connections, contact sources) is explicitly excluded -- it ships via the demo pipeline instead.

- **Two tiers**:
  - **Core** (`seed-core.sqlite`, ~30 MB): Companies from the LinkedOut network where connections actually work. Contains ~47K companies, ~63K role aliases, ~108 funding rounds, ~148 startup tracking entries.
  - **Full** (`seed-full.sqlite`, ~84 MB): Core data plus ~171K additional US/India companies from PDL (People Data Labs) with 201+ employees. Contains ~218K companies, ~63K role aliases, ~320 funding rounds, ~322 startup tracking entries.

- **Data format**: SQLite files with one table per seed table, plus a `_metadata` table containing `version`, `created_at`, and `table_counts` (JSON string). SQLite is used as a portable, single-file transport format -- the actual data lives in PostgreSQL after import.

### Tables Covered

| Table | Description | Core Count | Full Count |
|-------|-------------|------------|------------|
| `company` | Company reference data (name, website, industry, size, etc.) | 47,258 | 218,199 |
| `company_alias` | Company name variations for fuzzy matching | 0 | 0 |
| `role_alias` | Job title normalization mappings | 62,717 | 62,717 |
| `funding_round` | Public funding data (round type, amount, investors) | 108 | 320 |
| `startup_tracking` | Startup metrics and tracking status | 148 | 322 |
| `growth_signal` | Growth indicators | 0 | 0 |

### Manifest Structure

- **File**: `seed-data/seed-manifest.json`, published alongside SQLite files as a GitHub Release asset.

- **Top-level fields**: `version` (semver string, currently `"0.1.0"`), `created_at` (ISO 8601 timestamp), `files` (array of file entries).

- **Per-file fields**: `name` (filename), `tier` (`"core"` or `"full"`), `size_bytes` (integer), `sha256` (hex digest for integrity verification), `table_counts` (object mapping table name to row count).

- **Validation**: Both `download-seed` and `import-seed` validate the manifest. `download-seed` checks that each file entry has `name`, `tier`, `sha256`, and `size_bytes`. `import-seed` validates that the SQLite file contains all 6 expected tables from `IMPORT_ORDER`.

### Download Flow

- **Command**: `linkedout download-seed [--full] [--output DIR] [--version TAG] [--force]`

- **Source**: GitHub Releases on `sridherj/linkedout-oss`. Default tier is core; pass `--full` for the full dataset. The base URL can be overridden with `LINKEDOUT_SEED_URL` for forks.

- **Version resolution**: If `--version` is not specified, queries the GitHub API (`/repos/.../releases/latest`) to find the latest release tag. Handles rate limiting (403/429) with a message to set `GITHUB_TOKEN`. Supports `GITHUB_TOKEN` for authenticated requests throughout.

- **Manifest fetch**: Downloads `seed-manifest.json` from the resolved release URL, parses JSON, validates structure (must have `files` array, each entry must have `name`, `tier`, `sha256`, `size_bytes`).

- **Tier selection**: `_select_tier_file()` finds the manifest entry matching the requested tier. Raises an error listing available tiers if the requested one is not found.

- **Download mechanics**: Stream-downloads with `tqdm` progress bar (8192-byte chunks), writing to a `.tmp` file first and renaming on success. Identical pattern to `download-demo`.

- **Caching**: Downloaded file is stored at `~/linkedout-data/seed/<filename>` (or `--output` override). If the file exists and SHA256 matches, download is skipped unless `--force`.

- **Checksum verification**: Post-download SHA256 check via `shared.utils.checksum.verify_checksum()`. On mismatch, the file is deleted.

- **Reporting**: Generates both an `OperationReport` (standard format) and a detailed JSON download report at `~/linkedout-data/reports/download-seed-<timestamp>.json` containing version, tier, filename, size, SHA256, duration, source URL, and destination path.

### Import Flow

- **Command**: `linkedout import-seed [--seed-file PATH] [--dry-run]`

- **File location**: Auto-detects seed files in `~/linkedout-data/seed/`, preferring `seed-core.sqlite` over `seed-full.sqlite`. Can be overridden with `--seed-file`.

- **Validation**: Reads `_metadata` table for version/created_at/table_counts, then checks that all 6 tables in `IMPORT_ORDER` exist in the SQLite file.

- **Import order**: Tables are imported in FK-safe order: `company`, `company_alias`, `role_alias`, `funding_round`, `startup_tracking`, `growth_signal`. This matches the order defined in `IMPORT_ORDER`.

- **RLS context**: All database writes use `SYSTEM_USER_ID` (`usr_sys_001`) from `dev_tools.db.fixed_data` as the `app_user_id` parameter for `db_session_manager.get_session()`. This is required because RLS policies gate all table access.

- **Type conversion**: SQLite stores PostgreSQL arrays as JSON strings and booleans as integers. `_convert_row()` handles the conversion:
  - `company.enrichment_sources`: JSON string to Python list.
  - `funding_round.lead_investors` and `funding_round.all_investors`: JSON string to Python list.
  - `startup_tracking.watching`: Integer 0/1 to Python bool.

- **Upsert logic**: Uses `INSERT ... ON CONFLICT (id) DO UPDATE SET ... WHERE <change detection> RETURNING (xmax = 0) AS inserted`:
  - `IS DISTINCT FROM` for null-safe column comparison -- identical rows are skipped entirely (no write, no version bump).
  - `xmax = 0` in RETURNING distinguishes inserts (new row) from updates (changed row).
  - If no rows returned, the ON CONFLICT matched but WHERE excluded the update (data identical = skipped).

- **Batch processing**: Rows are processed in batches of 1,000 (`BATCH_SIZE = 1000`). Progress is printed per batch as `Importing <table>... N/M`.

- **Dry run**: `--dry-run` reads all rows and checks existing IDs (via `SELECT id FROM <table>`) to report what would be inserted vs. skipped, without writing anything. Uses a READ session instead of WRITE.

- **Reporting**: Generates a detailed JSON import report at `~/linkedout-data/reports/seed-import-<timestamp>.json` with per-table breakdown (inserted/updated/skipped/total), overall totals, seed version, duration, and dry-run flag. Also generates a standard `OperationReport` and records a metric via `record_metric('seed_imported', ...)`.

- **Summary output**: Prints per-table results in columnar format (`<table>: N inserted, N updated, N skipped`), overall total, and next steps suggestion (`linkedout status`).

### Checksum Verification Script

- **Script**: `scripts/verify-seed-checksums.py` -- standalone script that reads `seed-data/seed-manifest.json` and verifies SHA256 checksums of all listed seed files present in `seed-data/`. Files not present are skipped with a "released separately" message. Returns exit code 1 on any mismatch.

### Seed Data Generation (Maintainer-Only)

- **Export tool**: `python -m dev_tools.seed_export --output seed-data/` produces both SQLite files and the manifest. Requires access to the production LinkedOut PostgreSQL database.

- **Release process**: Uses `gh release create "seed-v<VERSION>"` with all 3 files (core SQLite, full SQLite, manifest) as release assets. Tag format is `seed-v{semver}` to keep seed releases separate from code releases.

- **PII policy**: Seed data contains only company reference data -- no personal profile information. Company names, websites, industries, and funding data are all public.

## Decisions

- **SQLite as transport format**: Seed data ships as SQLite files rather than SQL dumps, CSV, or JSON. SQLite provides a portable single-file format that supports typed columns, is queryable for validation, and avoids encoding/escaping issues with text formats. The tradeoff is requiring a SQLite-to-PostgreSQL import step.

- **Two tiers over one**: Core (47K companies from the actual network) and Full (218K including PDL companies) provide a meaningful choice. Users who just want matching for their connections use core; users who want broader company intelligence use full. This keeps the default download small (~30 MB) while offering comprehensive data for those who want it.

- **Upsert with change detection over truncate-and-reload**: The `IS DISTINCT FROM` pattern means re-running `import-seed` with the same data is a no-op (all rows skipped). This is safer than truncate-and-reload which would temporarily leave tables empty and could break concurrent queries.

- **SYSTEM_USER_ID for RLS**: All seed imports run as `usr_sys_001` to satisfy RLS policies. This is the same system user used across all administrative operations.

- **No profile data in seed**: Profile data (crawled_profile, experience, education, profile_skill) is excluded from seed data because profiles are personal/tenant-scoped and ship via the demo pipeline instead. Seed data is strictly company reference tables that are shared across all tenants.

## Not Included

- **Incremental seed updates**: No mechanism to download only rows that changed since the last import. Each download is the complete tier file. The upsert logic handles this gracefully (unchanged rows are skipped).

- **Custom tier creation**: Users cannot create their own seed tiers or filter which tables to import. The 6-table set is fixed.

- **Automatic seed updates**: No background check for newer seed versions. Users must manually run `download-seed --force` to get updated data.

- **PDL import script**: While the README mentions PDL (People Data Labs) as the source for the ~171K additional companies in the full tier, the actual PDL import script is part of the maintainer toolchain and not exposed as a user-facing command.

- **Seed data export from user DB**: No command to export the user's own company data back to SQLite format for sharing or backup.
