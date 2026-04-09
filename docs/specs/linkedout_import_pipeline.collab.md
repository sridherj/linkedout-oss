---
feature: linkedout-import-pipeline
module: backend/src/linkedout/import_pipeline
linked_files:
  - backend/src/linkedout/import_pipeline/service.py
  - backend/src/linkedout/import_pipeline/dedup.py
  - backend/src/linkedout/import_pipeline/merge.py
  - backend/src/linkedout/import_pipeline/controller.py
  - backend/src/linkedout/import_pipeline/schemas.py
  - backend/src/linkedout/import_pipeline/normalize.py
  - backend/src/linkedout/import_pipeline/converters/registry.py
  - backend/src/linkedout/import_pipeline/converters/base.py
  - backend/src/linkedout/import_pipeline/converters/linkedin_csv.py
  - backend/src/linkedout/import_pipeline/converters/google_job.py
  - backend/src/linkedout/import_pipeline/converters/google_phone.py
  - backend/src/linkedout/import_pipeline/converters/google_email.py
  - backend/src/shared/utils/linkedin_url.py
  - backend/src/linkedout/commands/import_connections.py
  - backend/src/linkedout/commands/import_contacts.py
  - backend/src/linkedout/commands/import_seed.py
  - backend/tests/integration/linkedout/import_pipeline/test_import_pipeline.py
version: 2
last_verified: "2026-04-09"
---

# LinkedOut Import Pipeline

**Created:** 2026-04-09 -- Adapted from internal spec for LinkedOut OSS

## Intent

Orchestrate CSV contact file uploads and seed data through parse, dedup, and merge pipelines that create or update connections and reference data in the user's network. Supports 4 contact source formats (LinkedIn CSV, Google Contacts with job titles, Google Contacts with phone numbers, email-only contacts) plus pg_dump seed data import for company/reference tables. Each contact import creates an ImportJob for status tracking and processes contacts through 3-stage dedup (URL, email, fuzzy name+company) before merging into the connection graph. Three CLI commands (`import-connections`, `import-contacts`, `import-seed`) provide direct import paths alongside the API-based pipeline.

## Behaviors

### CSV Parsing (API Pipeline)

- **Four source-specific converters**: Each source format has a dedicated converter class extending `BaseContactConverter` (in `converters/base.py`). LinkedIn CSV (`LinkedInCsvConverter`), Google Contacts job (`GoogleJobContactConverter`), Google Contacts phone (`PhoneContactConverter`), and email-only (`EmailOnlyContactConverter`) each implement `parse()` and `detect()`. All four are registered in `CONVERTER_REGISTRY` in `converters/registry.py`. Verify all four converters are registered.

- **Auto-detection of source format**: When no `source_type` is provided (or when `source_type` is `'google_contacts'`), the system iterates converters in detection order and uses the first converter whose `detect()` returns True. Detection order is defined in `_DETECTION_ORDER`: LinkedIn > Google Job > Phone > Email-Only. Verify detection order is LinkedIn first, email-only last.

- **Parsed contacts and failed rows**: Each converter returns a tuple of `(parsed_contacts, failed_rows)` where `failed_rows` is `list[tuple[int, dict, str]]` (row_number, raw_data, error_reason). Failed rows are tracked on the ImportJob's `failed_count`. Verify failed rows are counted correctly.

- **ParsedContact schema**: Parsed contacts use the `ParsedContact` dataclass (in `schemas.py`) with fields: first_name, last_name, full_name, email, phone, company, title, linkedin_url, connected_at, raw_record, source_type.

### Dedup Pipeline (API Pipeline)

- **Three-stage cascading dedup**: Contacts are matched against existing connections through URL match (confidence 1.0), email match (confidence 0.95), then fuzzy name+company match (threshold 0.85). Unmatched contacts are marked as `dedup_status='new'`. Each stage only processes contacts unmatched by prior stages. Implementation in `dedup.py` via `run_dedup()`. Verify each stage only processes contacts unmatched by prior stages.

- **Within-import URL dedup**: If two contacts in the same import file share a LinkedIn URL, the second is matched to the same connection as the first via `import_url_seen` dict. Verify duplicate URLs within a single import do not create duplicate connections.

- **Fuzzy matching requires both name and company**: Name matching uses `rapidfuzz.fuzz.token_sort_ratio` with a threshold of 85. Company matching uses a threshold of 80. Both must pass for a fuzzy match. If the entry has no company, the match is skipped (`continue`). Verify contacts with matching names but missing or non-matching companies are not fuzzy-matched.

- **Lookup entries built from joined data**: The service builds `ConnectionLookupEntry` objects by joining `ConnectionEntity` with `CrawledProfileEntity` to get linkedin_url, full_name, and current_company_name. Emails are split from comma-separated `connection.emails` field (not PostgreSQL ARRAY).

### Merge

- **Matched contacts merge into existing connections**: Survivorship rules in `merge.py`: earliest `connected_at` wins, emails and phones are unioned (comma-separated strings, sorted), sources list is appended (no duplicates). Source detail JSON is appended per contact source via `_append_source_detail()`. Verify merge does not overwrite existing data with nulls.

- **New contacts create stub profiles and connections**: A new `CrawledProfileEntity` is created with `data_source='csv_stub'` and `has_enriched_data=False` if no profile exists for the LinkedIn URL. For contacts without a URL, a `stub://` URL is generated using the contact_source ID. A `ConnectionEntity` is created linking the profile to the user. Verify every new connection has a non-null `crawled_profile_id`.

- **Existing profiles are reused by URL**: If a `CrawledProfileEntity` already exists for the contact's normalized LinkedIn URL (checked via `existing_profiles_by_url` dict), the new connection links to it rather than creating a duplicate. Verify profile dedup works across imports.

- **Stub merge for reconciliation**: `merge_stub_into_connection()` transfers phones, emails, sources, source_details from a stub connection to a target connection. Repoints all `contact_source` records from stub to target. Soft-deletes the stub connection and its crawled_profile (if URL starts with `stub://`). Verify no data is lost during merge.

### Normalization

- **Email normalization**: `normalize_email()` in `normalize.py` lowercases, strips whitespace, and validates presence of `@` and `.` after `@`. Returns empty string if invalid.

- **Phone normalization**: `normalize_phone()` in `normalize.py` uses the `phonenumbers` library with default country `'IN'` (India). Formats to E.164 via `phonenumbers.format_number()`. Returns `None` if unparseable or invalid.

- **LinkedIn URL normalization**: Handled by `shared/utils/linkedin_url.py` via `normalize_linkedin_url()`.

### Orchestration (API Pipeline)

- **Concurrent import guard**: Only one import per user per source_type can be active (`status IN ('pending', 'processing')`). Attempting a second returns `{'error': 'conflict'}`. Verify concurrent imports for the same user and source type are rejected.

- **Sync/async threshold**: Imports under 5000 contacts (configurable via `IMPORT_SYNC_THRESHOLD` env var) are processed synchronously. Larger imports return immediately with `async_mode=True` and processing status. Verify the threshold is respected.

- **ImportJob lifecycle tracking**: The import job transitions through statuses: pending -> parsing -> deduplicating -> complete (or failed). Counters (`total_records`, `parsed_count`, `matched_count`, `new_count`, `failed_count`) are updated at each stage. Verify all counters are populated on completion.

- **Post-import reconciliation**: For Google Contacts imports (`google_contacts_job`, `contacts_phone`, `google_contacts`) that create new stubs, the service triggers `reconcile_for_user()` from `dev_tools.reconcile_stubs`. Reconciliation failure does not fail the import (caught and logged as warning).

- **ContactSource bulk insert**: Before dedup, the service bulk-inserts `ContactSourceEntity` rows for all parsed contacts with `dedup_status='pending'`, preserving the raw import data for audit and the affinity scorer's external contact signal.

### Controller (API Endpoints)

- **Upload endpoint**: `POST /tenants/{tenant_id}/bus/{bu_id}/import` accepts multipart form data with `file` (CSV), optional `source_type`, and required `app_user_id`. Returns import job summary dict. Returns 409 on concurrent import conflict. Verify file upload works with multipart/form-data.

- **Job status endpoint**: `GET /tenants/{tenant_id}/bus/{bu_id}/import-jobs/{job_id}` returns import job status and all counters. Returns 404 for non-existent job IDs.

### CLI: import-connections

- **Command**: `linkedout import-connections [CSV_FILE]` -- imports LinkedIn connections from CSV export. Defined in `commands/import_connections.py`.

- **Auto-detect CSV**: If no file argument given, auto-detects `Connections*.csv` in `~/Downloads` (most recently modified).

- **LinkedIn CSV preamble**: Skips 3 preamble lines before the CSV header (standard LinkedIn export format).

- **URL-based profile matching**: Builds `{normalized_linkedin_url: crawled_profile_id}` index from existing profiles. Matched URLs link to existing profiles; unmatched URLs create stub profiles with `data_source='csv_stub'`.

- **Batch processing**: Processes rows in configurable batch sizes (default 1000, `--batch-size` option). Each batch runs in its own DB session with savepoint-per-row error isolation.

- **Dry-run support**: `--dry-run` parses the CSV and reports counts (total rows, with URL, without URL, with email) without writing to the database.

- **Operation report**: Generates an `OperationReport` JSON file and prints next-step suggestions (`compute-affinity`, `embed`).

### CLI: import-contacts

- **Command**: `linkedout import-contacts [CONTACTS_DIR]` -- imports Google contacts from 3 CSV files. Defined in `commands/import_contacts.py`.

- **Three source files required**: Expects `contacts_from_google_job.csv`, `contacts_with_phone.csv`, and `gmail_contacts_email_id_only.csv` in the specified directory (default `~/Downloads`).

- **Cross-source dedup**: Deduplicates contacts across all 3 sources by email before DB matching. Higher-priority source wins (LinkedIn=4 > Google Job=3 > Phone=2 > Email-Only=1). Phone data from lower-priority sources is merged into higher-priority duplicates.

- **Two-stage matching**: Matches contacts against existing connections by email (via email index) then by exact full-name match (via name index). Unmatched contacts create new stub connections with `data_source='gmail_stub'`.

- **Source type mapping**: Internal source names are mapped to external types for the affinity scorer: `google_job_contacts` -> `google_contacts_job`, `phone_contacts` -> `contacts_phone`, `email_only_contacts` -> `gmail_email_only`.

- **Contact source rows**: Creates `ContactSourceEntity` rows for every contact (matched or new) to feed the affinity scorer's external contact signal. Prior contact_source rows are deleted before re-import.

- **ImportJob tracking**: Creates a single ImportJob for the entire contacts import with `source_type='gmail_contacts'`.

- **Phone normalization**: Basic normalization with Indian number defaults (10-digit starting with 6-9 gets +91 prefix). Uses a simpler regex-based normalizer in this command (not the phonenumbers library used in the API pipeline).

### CLI: import-seed

- **Command**: `linkedout import-seed [--seed-file PATH]` -- imports seed company/reference data from a pg_dump file into PostgreSQL. Defined in `commands/import_seed.py`.

- **Six reference tables**: Imports `company`, `company_alias`, `role_alias`, `funding_round`, `startup_tracking`, `growth_signal` in FK-safe order. Profile data (crawled_profile, experience, education) is NOT part of seed data.

- **pg_dump source format**: Reads from a downloaded `.dump` file (pg_dump format). Auto-detects `seed-core.dump` or `seed-full.dump` in `~/linkedout-data/seed/`.

- **Staging schema pattern**: Uses `_seed_staging` as a staging schema. `pg_restore` loads the dump into the staging schema, then SQL upserts merge into the public schema. The staging schema is dropped after import (or on error). Column intersection ensures only columns present in both staging and public schemas are upserted, handling version skew gracefully.

- **Idempotent upsert**: Uses `INSERT ... ON CONFLICT (id) DO UPDATE` with `IS DISTINCT FROM` null-safe comparison. Distinguishes inserts from updates via PostgreSQL's `xmax = 0` trick. Rows with identical data are skipped. Verify re-running with same data produces 0 inserts and 0 updates.

- **pg_restore error handling**: Exit codes: 0 = success, 1 = warnings (expected with `--clean --if-exists` when staging tables don't exist yet). Only exit code >= 2 is a real failure.

- **Dry-run support**: `--dry-run` restores into the staging schema and reports what would be imported (new vs. existing row counts per table) without writing to public schema.

- **Detailed report**: Generates both a JSON report (in `~/linkedout-data/reports/`) and an `OperationReport` for consistency with other commands.

### Edge Cases

> Edge: The file position must be reset between detection and parsing when auto-detect is used in the API pipeline, since detection reads the file header.

> Edge: Phone normalization in `normalize.py` defaults to India (country code IN) via the phonenumbers library. Contacts without a recognizable country code are parsed as Indian numbers.

> Edge: Connection emails and phones are stored as comma-separated Text strings (not PostgreSQL ARRAY). Splitting and rejoining must handle empty strings and whitespace.

> Edge: `import-connections` creates connections with system user IDs (`usr_sys_001`, `tenant_sys_001`, `bu_sys_001`) hardcoded in the command -- these must match the system user created by the seed/migration.

> Edge: `import-contacts` deletes all prior `contact_source` rows for the 3 external source types before re-import, making it a destructive re-import rather than incremental.

> Edge: Seed import validates the manifest `format` field is `"pgdump"` before attempting restore. pg_restore exit code 1 (warnings) is tolerated; only exit code >= 2 is treated as failure.

## Decisions

### Cascading dedup over parallel matching -- 2026-03-27
**Chose:** Sequential 3-stage cascade (URL, email, fuzzy)
**Over:** Running all matchers in parallel and picking the best
**Because:** Sequential cascade avoids conflicting matches and makes confidence interpretation straightforward. Higher-confidence matchers run first.

### Conservative fuzzy thresholds -- 2026-03-27
**Chose:** Name threshold 85 + company threshold 80
**Over:** Lower thresholds or name-only matching
**Because:** False positives (merging two different people) are much worse than false negatives (creating a duplicate connection). Splink probabilistic dedup is deferred for ambiguous cases.

### Synchronous processing for small imports -- 2026-03-27
**Chose:** Sync processing under 5000 contacts
**Over:** Always async via task queue
**Because:** Most user imports are under 2000 contacts. Synchronous processing provides immediate feedback. The threshold is configurable.

### Three CLI commands for different import paths -- 2026-04-09
**Chose:** Separate `import-connections`, `import-contacts`, `import-seed` commands
**Over:** Single unified import command with subcommands
**Because:** Each import path has fundamentally different inputs (LinkedIn CSV vs. 3 Google CSVs vs. SQLite), matching logic, and output schemas. Separate commands keep each simple and independently testable.

### pg_dump as seed distribution format -- 2026-04-09
**Chose:** pg_dump file with staging schema pattern as seed transport
**Over:** SQLite, CSV bundle, or API-based seed download
**Because:** pg_dump eliminates ~640 lines of type conversion code (boolean casting, array serialization, column naming) and the entire impedance mismatch bug class. Staging schema + column intersection handles version skew. Upsert logic with `IS DISTINCT FROM` makes re-import safe.

## Not Included

- Async import processing (above threshold returns immediately; no background worker yet)
- iCloud vCard converter (deferred)
- Office/Exchange converter (deferred)
- Splink probabilistic dedup for ambiguous fuzzy-match cases
- GPT-4o-mini hard-case dedup
- Batch re-import or incremental sync for contacts (import-contacts is destructive re-import)
- Stub reconciliation as standalone CLI command (reconciliation runs as post-import hook only; `dev_tools/reconcile_stubs.py` exists but is not exposed as a CLI command in OSS)
- Profile/experience seed data (ships via demo pipeline, not import-seed)
