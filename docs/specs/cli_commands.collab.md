---
feature: cli-commands
module: backend/src/linkedout
linked_files:
  - backend/src/linkedout/cli.py
  - backend/src/linkedout/cli_helpers.py
  - backend/src/linkedout/commands/import_connections.py
  - backend/src/linkedout/commands/import_contacts.py
  - backend/src/linkedout/commands/import_seed.py
  - backend/src/linkedout/commands/download_seed.py
  - backend/src/linkedout/commands/enrich.py
  - backend/src/linkedout/commands/compute_affinity.py
  - backend/src/linkedout/commands/embed.py
  - backend/src/linkedout/commands/embed_query.py
  - backend/src/linkedout/commands/status.py
  - backend/src/linkedout/commands/diagnostics.py
  - backend/src/linkedout/commands/version.py
  - backend/src/linkedout/commands/config.py
  - backend/src/linkedout/commands/query_log.py
  - backend/src/linkedout/commands/report_issue.py
  - backend/src/linkedout/commands/start_backend.py
  - backend/src/linkedout/commands/stop_backend.py
  - backend/src/linkedout/commands/download_demo.py
  - backend/src/linkedout/commands/restore_demo.py
  - backend/src/linkedout/commands/reset_demo.py
  - backend/src/linkedout/commands/use_real_db.py
  - backend/src/linkedout/commands/demo_help.py
  - backend/src/linkedout/commands/reset_db.py
  - backend/src/linkedout/commands/setup.py
  - backend/src/linkedout/commands/upgrade.py
  - backend/src/linkedout/commands/migrate.py
version: 5
last_verified: "2026-04-12"
---

# CLI Commands

**Created:** 2026-04-09 -- Written from scratch for LinkedOut OSS
**Updated:** 2026-04-12 -- v5: enrich command for Apify-based profile enrichment with key rotation, progress reporting, and cost estimation

## Intent

Provide a user-facing CLI surface for all LinkedOut operations: setup, data import, intelligence processing, server management, demo mode, and diagnostics. Commands are organized as a flat namespace under the `linkedout` entry point, with category-grouped help text for discoverability.

## Behaviors

### CLI Structure

- **Entry point**: `linkedout` command, registered via `pyproject.toml` as `linkedout = "linkedout.cli:cli"`.

- **Flat namespace with category help**: All commands live at the top level (e.g., `linkedout status`, not `linkedout system status`). The `--help` output groups commands by category using a custom `CategoryHelpGroup` that replaces Click's default help formatter with an ASCII art banner and category-organized command listing. The one exception is `config`, which is a Click subgroup with `path` and `show` subcommands.

- **Lazy registration**: The root group (`_LazyLinkedOutCLI`) defers all command imports until `list_commands()` or `get_command()` is called. This avoids importing SQLAlchemy, embedding providers, and other heavy dependencies at CLI startup. Verify that `linkedout --help` does not trigger database connections.

- **cli_logged decorator**: Most commands use `@cli_logged("command_name")` which generates a correlation ID (`cli_<command_name>_<uuid>`), sets it as the thread-local correlation ID, and logs start/completion/failure with timing. Verify correlation IDs appear in structured log output.

- **dry_run_option**: A shared `click.option('--dry-run', is_flag=True)` is defined in `cli_helpers.py` for reuse. Some commands import it directly; others define their own `--dry-run` inline.

- **Post-command hooks**: A `result_callback` on the root group (`_post_command_hooks`) runs after every command. It handles two concerns: (1) appends a demo mode nudge ("Demo mode . linkedout setup to use your own data") when demo mode is active, and (2) appends an update notification banner when an update is available and not snoozed (using `check_for_update(timeout=3)` with a 3-second timeout to avoid stalling the CLI). Verify both the demo nudge and the update banner appear after commands when their conditions are met.

- **Exit codes**: Commands propagate non-zero exit codes via `raise SystemExit(1)` or `sys.exit(1)` on failure. Verify failed commands exit non-zero.

- **Operation reports**: Write commands (import-connections, import-contacts, import-seed, download-seed, compute-affinity, embed, enrich) generate JSON operation reports via `OperationReport` and save them to `~/linkedout-data/reports/`. Each report includes operation name, duration, counts (total/succeeded/skipped/failed), and suggested next steps.

### Setup

- **setup**: Runs the interactive LinkedOut setup flow. Delegates to `linkedout.setup.orchestrator.run_setup()`. Supports `--data-dir <path>` to override the default data directory (`~/linkedout-data`). Verify the setup flow creates config files, validates database connectivity, and completes without error on a fresh install.

### Data Import

- **import-connections**: Import LinkedIn connections from a CSV export file. Takes an optional positional `CSV_FILE` argument; if omitted, auto-detects the most recent `Connections*.csv` in `~/Downloads`. Skips 3 preamble lines in LinkedIn's CSV format. For each row: normalizes the LinkedIn URL, attempts to match against existing `crawled_profile` rows by URL, creates stub profiles (`data_source='csv_stub'`) for unmatched connections, and inserts `connection` rows with `sources=['linkedin_csv']`. Uses SYSTEM_USER_ID for RLS bypass.
  - Options: `--format {linkedin,google,auto}` (default: `auto`), `--dry-run` (parse and report counts only), `--batch-size N` (rows per commit batch, default: 1000).
  - Output: Per-batch progress, then final counts (imported/matched/unenriched/no-url/errors) and elapsed time.
  - Suggested next steps: `linkedout enrich`, `linkedout compute-affinity`.
  - Verify: matched connections link to existing profiles; unmatched connections create stubs; `--dry-run` makes no DB writes.

- **import-contacts**: Import Google contacts from CSV files. Takes an optional positional `CONTACTS_DIR` argument (default: `~/Downloads`). Expects three specific CSV files: `contacts_from_google_job.csv` (Google Contacts 31-col), `contacts_with_phone.csv` (Outlook-style 67-col), `gmail_contacts_email_id_only.csv` (Google Contacts 27-col). All three must exist or the command errors. Parses all three sources, deduplicates by email across sources (higher-priority source wins: linkedin_csv > google_job > phone > email_only), then matches against existing connections by email first, then by full_name. Matched contacts merge email/phone onto existing connections. Unmatched contacts create stub profiles (`data_source='gmail_stub'`) and new connections. Writes `contact_source` rows for the affinity scorer. Creates an `import_job` record to track the operation. Destructive re-import: deletes prior `contact_source` rows for these source types before inserting.
  - Options: `--format {google,icloud,auto}` (default: `auto`), `--dry-run` (parse and report counts only).
  - Output: Per-source parse counts, dedup stats, match/merge results, errors, and elapsed time.
  - Suggested next steps: `linkedout compute-affinity`.
  - Verify: email matching merges onto existing connections; name matching works; unmatched contacts create new stubs; prior contact_source rows are cleaned up.

- **import-seed**: Import seed company data from a pg_dump file into PostgreSQL. Uses `pg_restore` to load into a `_seed_staging` schema, then SQL upserts merge data into the public schema using column intersection for version-skew safety. Imports 6 tables in FK-safe order: `company`, `company_alias`, `role_alias`, `funding_round`, `startup_tracking`, `growth_signal`. Uses `INSERT ... ON CONFLICT (id) DO UPDATE ... WHERE ... IS DISTINCT FROM ...` for null-safe upsert with change detection. `RETURNING (xmax = 0)` distinguishes inserts from updates.
  - Options: `--seed-file <path>` (default: auto-detect `seed.dump` in `~/linkedout-data/seed/`), `--dry-run` (report what would be imported without writing).
  - Output: Per-table counts (inserted/updated/skipped), total summary, and a detailed JSON import report saved to `~/linkedout-data/reports/`.
  - Verify: idempotent (running twice produces no updates on identical data); validates manifest format before import; staging schema is cleaned up after import.

### Seed Data

- **download-seed**: Download seed company data (pg_dump file) from GitHub Releases. Queries GitHub API for the latest release (or uses `--version`), fetches `seed-manifest.json` for file metadata, downloads `seed.dump` with a tqdm progress bar, and verifies SHA256 checksum. Respects `GITHUB_TOKEN` for rate-limited API calls and `LINKEDOUT_SEED_URL` for fork/mirror overrides. Skips download if the file already exists and checksum matches (unless `--force`). Writes to a temp file first, renames on success.
  - Options: `--output <dir>` (download location, default: `~/linkedout-data/seed/`), `--version <tag>` (specific release version, default: latest), `--force` (re-download even if cached).
  - Output: Download progress bar, checksum verification, file location, and a detailed JSON download report.
  - Suggested next steps: `linkedout import-seed`.
  - Verify: skip-if-cached works; checksum mismatch triggers re-download; `--force` always re-downloads.

### Intelligence

- **compute-affinity**: Calculate affinity scores and Dunbar tiers for all connections. Iterates over all active `app_user` rows, creates an `AffinityScorer` per user, and calls `compute_for_user()` which writes `affinity_score` and `dunbar_tier` on each connection row. Safe to re-run (scores are overwritten in place).
  - Options: `--dry-run` (report user count only), `--force` (recompute all; default: only unscored connections).
  - Output: Per-user update counts, total connections updated, and operation report.
  - Suggested next steps: `linkedout status`.
  - Verify: scores are written to connection rows; `--dry-run` makes no DB writes.

- **enrich**: Enrich unenriched LinkedIn profiles via Apify with concurrent batched execution. Queries `crawled_profile` rows where `has_enriched_data = false` and `linkedin_url IS NOT NULL`, dispatches batches to the Apify LinkedIn scraper, processes results into relational data via `PostEnrichmentService`, and generates embeddings inline (unless `--skip-embeddings`). Uses crash-recovery state files to resume interrupted runs. Uses `SYSTEM_USER_ID` for RLS bypass. Supports Ctrl+C for graceful interruption with partial summary.
  - Options: `--limit N` (max profiles to enrich; default: all unenriched), `--dry-run` (count unenriched profiles, estimate cost, exit without calling Apify), `--skip-embeddings` (defer embedding to a separate `linkedout embed` run).
  - Output: Per-batch progress showing `Batch N: done/total (pct%) | $cost | ~remaining`. Final summary with total enriched, failed, batches completed, cost, and duration.
  - Error handling: Missing Apify key shows setup instructions (`APIFY_API_KEY`, `APIFY_API_KEYS`, `secrets.yaml`) and exits with code 1. Credit exhaustion (HTTP 402) raises `ApifyCreditExhaustedError`; the `KeyHealthTracker` marks the key as exhausted and rotates to the next healthy key. When all keys are exhausted, enrichment stops with a partial summary. Individual profile failures are logged and counted but do not halt the batch. Batch embedding failures are non-fatal — enrichment continues and embeddings can be backfilled with `linkedout embed`.
  - Suggested next steps: `linkedout compute-affinity` (or `linkedout embed` first if `--skip-embeddings` was used).
  - Verify: `--dry-run` makes no DB writes and shows correct count/cost; `--limit` restricts the number of profiles enriched; interrupted runs resume from last completed batch; operation report is saved to `~/linkedout-data/reports/`.

- **embed**: Generate vector embeddings for profile search. Queries enriched `crawled_profile` rows lacking embeddings in the target column, builds text representations from profile fields (name, headline, about, company, position, experiences), generates embeddings via the configured provider (OpenAI or local nomic), and writes vectors to the correct pgvector column (`embedding_openai` or `embedding_nomic`). Also populates `search_vector` (tsvector) for full-text search. Resumable via progress file checkpointing; safe to Ctrl+C and resume.
  - Options: `--provider {openai,local}` (default: from config), `--dry-run` (report profile counts and cost estimate), `--resume/--no-resume` (resume from last checkpoint, default: true), `--force` (clear existing embeddings and re-embed all), `--batch` (use OpenAI Batch API, 50% cheaper but slower; OpenAI provider only).
  - Output: Progress bar (real-time mode) or batch status updates, then final counts (embedded/skipped/failed), provider info, and duration.
  - Suggested next steps: `linkedout compute-affinity`.
  - Verify: embeddings are written to the correct column; `--force` clears and re-embeds; progress file enables resume after interruption; `--batch` with non-OpenAI provider raises `UsageError`.

- **embed-query**: Generate a single embedding vector for a query string. Takes a positional `TEXT` argument, generates the embedding via the configured provider, and outputs the vector to stdout. Designed for use by Claude Code when constructing similarity search SQL.
  - Options: `--provider {openai,local}` (default: from config), `--format {json,raw}` (default: json).
  - Output (json): JSON array of floats (e.g., `[0.123, -0.456, ...]`).
  - Output (raw): Space-separated floats.
  - No `search_query:` prefix is applied — query embeddings must match document embeddings, which are generated without prefixes.
  - Verify: outputs valid JSON array of correct dimension (768 for local, 1536 for OpenAI); `--provider` choice constraint works; `--format raw` outputs space-separated values.

### Query Logging

- **log-query**: Log a completed network query to the daily JSONL history file. Called by AI skills after each `/linkedout` query execution. Takes a positional `TEXT` argument (the query string).
  - Options: `--type <type>` (query type: `company_lookup`, `person_search`, `semantic_search`, `network_stats`, `general`; default: `general`), `--results <count>` (number of results returned; default: 0).
  - Output: Appends a JSON line to `~/linkedout-data/queries/YYYY-MM-DD.jsonl` with fields: `timestamp` (ISO 8601), `query_text`, `query_type`, `result_count`. Prints a confirmation message to stderr.
  - Verify: creates the `queries/` directory if it doesn't exist; appends (not overwrites) to existing daily files; invalid `--type` values are rejected by Click choice validation.

### System

- **status**: Quick one-line system health check. Checks database connectivity (via `check_db_connection()`), queries profile/company counts, calculates embedding coverage percentage, checks backend server status via PID file and `/health` endpoint, and reports demo mode state.
  - Options: `--json` (output as JSON instead of pipe-delimited one-liner).
  - Output (text): `LinkedOut v{version} [DEMO] | DB: {name} (demo) | {profiles} profiles | {companies} companies | embeddings: {pct}% | backend: {status}`.
  - Output (JSON): structured object with `version`, `demo_mode`, `database_name`, `db_connected`, `profiles`, `companies`, `embedding_coverage_pct`, and `backend` sub-object.
  - Verify: demo mode indicator appears when active; backend status detects running/stopped server.

- **diagnostics**: Comprehensive system health report for troubleshooting. Collects system info (OS, Python, PostgreSQL versions, disk space, data dir size), configuration (embedding provider/model, API key status), database stats (profile/company/connection counts, embedding coverage, schema version), and runs health checks (DB connection, embedding model, disk space, API keys). Computes a `health_status` object containing a `badge` (HEALTHY | NEEDS_ATTENTION | ACTION_REQUIRED) and severity counts (`critical`, `warning`, `info`). Badge derivation: HEALTHY if 0 critical and 0 warning issues; NEEDS_ATTENTION if 0 critical but ≥1 warning; ACTION_REQUIRED if ≥1 critical. Derives an `issues` list from DB stats and health check results via `compute_issues()` (lives in `health_checks.py` as a shared utility), with categories: bootstrap (missing system records), setup (missing owner profile), embeddings (profiles without embeddings), enrichment (unenriched profiles), affinity (connections without scores), and any failed health check. Each issue has `severity` (CRITICAL|WARNING|INFO), `category`, `message`, and `action` (CLI command to fix). Saves a JSON report to `~/linkedout-data/reports/`.
  - Options: `--repair` (auto-fix common issues by invoking the `linkedout` CLI entry point directly, e.g., `linkedout embed`; does NOT use `sys.executable -m linkedout.cli`), `--json` (output as JSON), `--output <path>` (write report to specific file).
  - Output: Multi-section human-readable summary (System, Config, Database, Health Checks, Recommendations) or raw JSON. The `database` section of JSON output includes extended stats: `profiles_enriched`, `profiles_unenriched`, `enrichment_events_total`, `connections_with_affinity`, `connections_without_affinity`, `owner_profile_exists`, `system_tenant_exists`, `system_bu_exists`, `system_user_exists`, `seed_companies_loaded`, `funding_rounds_total` (in addition to original counts).
  - Verify: API key status shows configured/not-configured without revealing secrets; `--repair` invokes the `linkedout` CLI entry point directly; `--json` output includes `health_status` object (`{badge, critical, warning, info}`) and `issues` array with severity-sorted actionable items.

- **version**: Show version information. Displays ASCII art logo, version number, Python version, PostgreSQL version, install path, config path, and data directory.
  - Options: `--json` (output as JSON object from `get_version_info()`), `--check` (run a fresh update check, ignoring cache and snooze; prints "Up to date (v{current})" or "Update available: v{current} -> v{latest}. Run: linkedout upgrade" with exit code 0 for up-to-date or 1 for update available; combine with `--json` for machine-readable output: `{"update_available": bool, "current": str, "latest": str, "release_url": str}`).
  - Verify: version matches `__version__` in `linkedout.version`; `--check` bypasses snooze via `check_for_update(force=True, skip_snooze=True)`; `--check` returns exit code 1 when outdated.

- **config**: Click subgroup for configuration management. Currently has two subcommands:
  - **config path**: Show the config file location (`~/.linkedout/config.yaml`).
  - **config show**: Show current configuration with secrets redacted. Displays key-value pairs: `embedding_provider`, `embedding_model`, `database_url` (always shows `***`, never the real URL), `data_dir`, `demo_mode`, `backend_port`, `api_keys.openai` (shows "configured" or "not configured"), `api_keys.apify` (shows "configured" or "not configured").
    - Options: `--json` (output as JSON object with the same fields).
    - Verify: `database_url` is always `***`; API key values are never exposed, only "configured"/"not configured" status.

- **report-issue**: Generate a diagnostic bundle for bug reports. Not yet implemented (exits with "coming in Phase 3").
  - Options: `--dry-run` (show the redacted report without filing an issue).

### Server

- **start-backend**: Start the LinkedOut API server (uvicorn). Required for the Chrome extension to communicate with the backend. Idempotent: kills any existing process on the target port before starting. Writes a PID file to `~/linkedout-data/state/backend.pid`. In foreground mode (default), runs uvicorn directly with auto-reload disabled. In background mode, spawns a detached subprocess, waits up to 10 seconds for `/health` to return 200, and reports success/failure with actionable error messages.
  - Options: `--port <int>` (default: from config/env, typically 8001), `--host <str>` (default: from config/env, typically 127.0.0.1), `--background` (run as daemon).
  - Output: Server URL and PID (background) or live server output (foreground).
  - Verify: idempotent port cleanup works; PID file is written; background mode health check succeeds; foreground mode cleans up PID on Ctrl+C.

- **stop-backend**: Stop the LinkedOut API server. Reads the PID from `~/linkedout-data/state/backend.pid`, sends SIGTERM, waits up to 10 seconds for graceful shutdown, then sends SIGKILL if the process is still alive. Cleans up stale PID files (process no longer running).
  - No options.
  - Output: "Stopping backend (PID {pid})..." then "Backend stopped." or "Backend is not running."
  - Verify: graceful shutdown via SIGTERM; SIGKILL fallback after timeout; stale PID file handled.

### Demo

- **download-demo**: Download the demo database dump (pg_dump format) from GitHub Releases. Similar pattern to `download-seed`: fetches `demo-manifest.json`, downloads with progress bar, verifies SHA256 checksum. Caches to `~/linkedout-data/cache/`. Respects `LINKEDOUT_DEMO_URL` for fork overrides.
  - Options: `--version <tag>` (specific release tag, default: `demo-v1`), `--force` (re-download even if cached).
  - Output: Download progress, checksum verification, file location.
  - Suggested next steps: `linkedout restore-demo`.
  - Verify: skip-if-cached works; checksum verification catches corruption.

- **restore-demo**: Restore the demo database from the cached dump file. Requires `pg_restore` to be installed. Creates the `linkedout_demo` database (drops first if it exists), restores the dump, updates config to demo mode, and regenerates `agent-context.env`. Idempotent: safe to re-run. After restore, displays the demo user profile and sample search queries.
  - No options.
  - Output: Progress messages, database stats (profiles/companies/connections), demo user profile description, sample queries, and suggested next steps.
  - Suggested next steps: `linkedout status`, `linkedout start-backend`, `linkedout demo-help`.
  - Verify: demo database is created and populated; config switches to demo mode; `agent-context.env` is regenerated.

- **reset-demo**: Reset the demo database to its original state by dropping and re-restoring from the cached dump. Does not re-download. Requires active demo mode.
  - Options: `--yes / -y` (skip confirmation prompt).
  - Output: Progress messages, database stats after reset.
  - Verify: requires demo mode to be active; confirmation prompt appears without `--yes`; data is fully reset.

- **use-real-db**: Switch from demo mode back to the real database. Disables demo mode in config and regenerates `agent-context.env`. If the user is not in demo mode, reports "Already using real database." and exits cleanly.
  - Options: `--drop-demo` (also drop the `linkedout_demo` database).
  - Output: Confirmation of switch, regeneration status.
  - Verify: config switches back to real database URL; `--drop-demo` drops the demo database; no-op when not in demo mode.

- **demo-help**: Display the demo user profile description and sample search queries. Useful for reference after setup.
  - No options.
  - Output: Demo user profile info and curated sample queries.

### Database

- **reset-db**: Reset the database. Default mode truncates all data (fastest). Full mode drops all tables and recreates via Alembic migrations. Uses `SET session_replication_role = 'replica'` to disable FK checks during truncation, iterates tables from `TableName.get_all_table_names()` in reverse order.
  - Options: `--full` (drop all tables and recreate instead of truncate), `--yes / -y` (skip confirmation prompt).
  - Output: Progress messages and "Done." on success.
  - Verify: default mode preserves schema but clears data; `--full` mode drops and recreates; confirmation prompt appears without `--yes`.

### Upgrade

- **upgrade**: Upgrade LinkedOut to the latest version. Only works for git clone installations. Delegates to `linkedout.upgrade.upgrader.Upgrader` which handles: pre-flight checks, `git pull`, dependency updates, database migrations, version scripts, and post-upgrade health checks. Reports step-by-step progress, prints what's-new notes, and saves an upgrade report.
  - Options: `--verbose` (show detailed command output), `--snooze` (snooze the current update notification instead of upgrading; shows confirmation with duration using escalating backoff: 24h → 48h → 1 week; if already up to date, prints "Already running the latest version."; if update check fails, prints "Could not check for updates.").
  - Output: Step-by-step progress messages, version transition summary (e.g., "v0.1.0 -> v0.2.0"), duration, and report path.
  - Verify: detects non-git-clone installations and refuses to upgrade; already-up-to-date is a no-op; failures include rollback instructions; `--snooze` invokes `snooze_update()` and displays the escalating duration.

### Hidden Commands

- **migrate**: Run database migrations (wraps `alembic upgrade head`). Hidden from main help text (`hidden=True`). Intended for internal/advanced use.
  - Options: `--dry-run` (preview pending migrations via `alembic history --indicate-current -v` without applying).
  - Output: Migration status/output.
  - Verify: hidden from `linkedout --help`; `--dry-run` does not apply migrations.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-04-09 | CLI framework | Click | argparse or Typer | Click is well-established, supports groups, and has good help generation |
| 2026-04-09 | Command namespace | Flat with category help | Nested Click groups | Flat commands are faster to type (e.g., `linkedout status` vs `linkedout system status`) and discoverable via category-grouped help text |
| 2026-04-09 | Import strategy | Lazy registration | Eager import | Avoids importing SQLAlchemy, embedding providers, etc. at CLI startup; keeps `linkedout --help` fast |
| 2026-04-09 | Demo isolation | Separate database (linkedout_demo) | In-DB markers | Infrastructure-level isolation avoids CASCADE deletes, mixed data bugs, and cleanup complexity |
| 2026-04-09 | Seed data format | pg_dump with staging schema upsert | SQLite or CSV | pg_dump eliminates type conversion (boolean/array), staging schema + column intersection handles version skew, upsert is idempotent with IS DISTINCT FROM null-safety |
| 2026-04-09 | Embedding resumability | Progress file checkpoint | Database-tracked batches | File-based progress is simpler, survives DB resets, and supports Ctrl+C recovery |

## Not Included

- Shell completion setup (no `--install-completion`)
- Interactive prompts for missing parameters (except confirmation prompts on destructive operations)
- Verbose/debug logging flags (logging level controlled via environment, not CLI flags)
- Plugin/extension system for third-party commands
- `config set` subcommand (config modification is Phase 2)
- `report-issue` implementation (Phase 3)
