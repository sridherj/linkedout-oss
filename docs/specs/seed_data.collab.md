---
feature: seed-data
module: seed-data
linked_files:
  - seed-data/seed-manifest.json
  - seed-data/seed.dump
  - seed-data/README.md
  - backend/src/linkedout/commands/download_seed.py
  - backend/src/linkedout/commands/import_seed.py
  - scripts/verify-seed-checksums.py
version: 3
last_verified: "2026-04-13"
---

# Seed Data

**Created:** 2026-04-09 -- Written from scratch for LinkedOut OSS

## Intent

Provide pre-curated company reference data so new LinkedOut installations have useful company intelligence (names, aliases, funding rounds, role normalization) without requiring users to run Apify enrichment or manually populate the database. Seed data covers public, non-tenant-scoped company tables only -- no personal profile data.

## Behaviors

### Seed Data Concept

- **Company reference data only**: Seed data covers 6 tables of public company intelligence that is shared across all tenants. These tables provide the foundation for company matching during profile import, role title normalization, and startup tracking. Personal data (profiles, connections, contact sources) is explicitly excluded -- it ships via the demo pipeline instead.

- **Single seed file** (`seed.dump`): Contains all qualifying companies -- those with employee data, funding rounds, size tier, or profile experience. This is a unified dataset that replaces the previous two-tier (core/full) system.

- **Data format**: pg_dump file using a `_seed_staging` schema. Data is exported from PostgreSQL into a staging schema, then dumped with `pg_dump`. On import, `pg_restore` loads into the staging schema, then SQL upserts merge into the public schema. This eliminates type conversion issues (boolean casting, array serialization) that existed with the previous SQLite-based format.

### Tables Covered

| Table | Description |
|-------|-------------|
| `company` | Company reference data (name, website, industry, size, etc.) |
| `company_alias` | Company name variations for fuzzy matching |
| `role_alias` | Job title normalization mappings |
| `funding_round` | Public funding data (round type, amount, investors) |
| `startup_tracking` | Startup metrics and tracking status |
| `growth_signal` | Growth indicators |

### Manifest Structure

- **File**: `seed-data/seed-manifest.json`, published alongside the dump file as a GitHub Release asset.

- **Top-level fields**: `version` (semver string, currently `"0.3.0"`), `created_at` (ISO 8601 timestamp), `format` (`"pgdump"`), `files` (array with a single file entry).

- **Per-file fields**: `name` (filename), `size_bytes` (integer), `sha256` (hex digest for integrity verification), `table_counts` (object mapping table name to row count).

- **Validation**: Both `download-seed` and `import-seed` validate the manifest. `download-seed` checks that each file entry has `name`, `sha256`, and `size_bytes`. `import-seed` validates the manifest `format` field is `"pgdump"`.

### Download Flow

- **Command**: `linkedout download-seed [--output DIR] [--version TAG] [--force]`

- **Source**: GitHub Releases on `sridherj/linkedout-oss`. Downloads `seed.dump` from the manifest. The base URL can be overridden with `LINKEDOUT_SEED_URL` for forks.

- **Version resolution**: If `--version` is not specified, queries the GitHub API (`/repos/.../releases/latest`) to find the latest release tag. Handles rate limiting (403/429) with a message to set `GITHUB_TOKEN`. Supports `GITHUB_TOKEN` for authenticated requests throughout.

- **Manifest fetch**: Downloads `seed-manifest.json` from the resolved release URL, parses JSON, validates structure (must have `files` array, each entry must have `name`, `sha256`, `size_bytes`).

- **Download mechanics**: Stream-downloads with `tqdm` progress bar (8192-byte chunks), writing to a `.tmp` file first and renaming on success. Identical pattern to `download-demo`.

- **Caching**: Downloaded file is stored at `~/linkedout-data/seed/<filename>` (or `--output` override). If the file exists and SHA256 matches, download is skipped unless `--force`.

- **Checksum verification**: Post-download SHA256 check via `shared.utils.checksum.verify_checksum()`. On mismatch, the file is deleted.

- **Reporting**: Generates both an `OperationReport` (standard format) and a detailed JSON download report at `~/linkedout-data/reports/download-seed-<timestamp>.json` containing version, filename, size, SHA256, duration, source URL, and destination path.

### Import Flow

- **Command**: `linkedout import-seed [--seed-file PATH] [--dry-run]`

- **File location**: Auto-detects `seed.dump` in `~/linkedout-data/seed/`. Can be overridden with `--seed-file`.

- **Staging schema pattern**: Import uses `_seed_staging` as a staging schema. `pg_restore` loads the dump file into the staging schema, then SQL upserts merge data from staging into public. The staging schema is dropped after import (or on error).

- **Column intersection**: The upsert uses the intersection of staging and public columns — only columns present in BOTH schemas are included. This handles version skew gracefully (newer seed files with extra columns, or older seed files missing columns).

- **Import order**: Tables are imported in FK-safe order: `company`, `company_alias`, `role_alias`, `funding_round`, `startup_tracking`, `growth_signal`. This matches the order defined in `IMPORT_ORDER`.

- **RLS context**: All database writes use `SYSTEM_USER_ID` (`usr_sys_001`) from `dev_tools.db.fixed_data` as the `app_user_id` parameter for `db_session_manager.get_session()`. This is required because RLS policies gate all table access.

- **Upsert logic**: Uses `INSERT ... ON CONFLICT (id) DO UPDATE SET ... WHERE <change detection> RETURNING (xmax = 0) AS inserted`:
  - `IS DISTINCT FROM` for null-safe column comparison -- identical rows are skipped entirely (no write, no version bump).
  - `xmax = 0` in RETURNING distinguishes inserts (new row) from updates (changed row).
  - If no rows returned, the ON CONFLICT matched but WHERE excluded the update (data identical = skipped).

- **pg_restore error handling**: Exit codes: 0 = success, 1 = warnings (expected with `--clean --if-exists` when tables don't exist yet). Only exit code >= 2 is a real failure.

- **Dry run**: `--dry-run` reads all rows and checks existing IDs (via `SELECT id FROM <table>`) to report what would be inserted vs. skipped, without writing anything. Uses a READ session instead of WRITE.

- **Reporting**: Generates a detailed JSON import report at `~/linkedout-data/reports/seed-import-<timestamp>.json` with per-table breakdown (inserted/updated/skipped/total), overall totals, seed version, duration, and dry-run flag. Also generates a standard `OperationReport` and records a metric via `record_metric('seed_imported', ...)`.

- **Summary output**: Prints per-table results in columnar format (`<table>: N inserted, N updated, N skipped`), overall total, and next steps suggestion (`linkedout status`).

### Checksum Verification Script

- **Script**: `scripts/verify-seed-checksums.py` -- standalone script that reads `seed-data/seed-manifest.json` and verifies SHA256 checksums of all listed seed files present in `seed-data/`. Files not present are skipped with a "released separately" message. Returns exit code 1 on any mismatch.

### Seed Data Generation (Maintainer-Only)

- **Export tool**: `python -m dev_tools.seed_export --output seed-data/` produces the dump file and manifest. Export uses the `_seed_staging` schema pattern: filtered data is written to the staging schema, then `pg_dump` produces the `.dump` file. Requires access to the production LinkedOut PostgreSQL database.

- **Release process**: Uses `gh release create "seed-v<VERSION>"` with 2 files (dump and manifest) as release assets. Tag format is `seed-v{semver}` to keep seed releases separate from code releases.

- **PII policy**: Seed data contains only company reference data -- no personal profile information. Company names, websites, industries, and funding data are all public.

## Decisions

- **pg_dump as transport format**: Seed data ships as pg_dump files using a staging schema pattern. This eliminates the entire type conversion layer (boolean casting, array serialization, column naming) that was required with the previous SQLite-based format. pg_restore loads data natively into PostgreSQL with correct types, and the staging schema + column intersection pattern handles version skew gracefully.

- **Single seed file over tiers**: After migrating all data to the OSS database, the two-tier system (core/full) no longer adds value — the private DB is a strict superset. A single `seed.dump` simplifies the download/import flow, removes tier selection UX, and reduces code surface area.

- **Upsert with change detection over truncate-and-reload**: The `IS DISTINCT FROM` pattern means re-running `import-seed` with the same data is a no-op (all rows skipped). This is safer than truncate-and-reload which would temporarily leave tables empty and could break concurrent queries.

- **SYSTEM_USER_ID for RLS**: All seed imports run as `usr_sys_001` to satisfy RLS policies. This is the same system user used across all administrative operations.

- **No profile data in seed**: Profile data (crawled_profile, experience, education, profile_skill) is excluded from seed data because profiles are personal/tenant-scoped and ship via the demo pipeline instead. Seed data is strictly company reference tables that are shared across all tenants.

## Not Included

- **Incremental seed updates**: No mechanism to download only rows that changed since the last import. Each download is the complete tier file. The upsert logic handles this gracefully (unchanged rows are skipped).

- **Custom seed filtering**: Users cannot filter which tables to import. The 6-table set is fixed.

- **Automatic seed updates**: No background check for newer seed versions. Users must manually run `download-seed --force` to get updated data.

- **PDL import script**: While the README mentions PDL (People Data Labs) as the source for the ~171K additional companies in the full tier, the actual PDL import script is part of the maintainer toolchain and not exposed as a user-facing command.

- **Seed data export from user DB**: No command to export the user's own company data back to dump format for sharing or backup.
