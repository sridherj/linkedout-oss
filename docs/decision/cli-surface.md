# CLI Surface Design — Decision Document

**Spike:** 0A  
**Date:** 2026-04-07  
**Status:** Approved by SJ (2026-04-07)  
**Author:** Claude (taskos-detailed-plan agent), refined interactively with SJ

---

## Context

LinkedOut's existing CLI lives under the `rcv2` namespace with 5 command groups (`db`, `test`, `prompt`, `agent`, `dev`) and ~25 commands. This was built for a private multi-tenant deployment with Langfuse, Apify, and TaskOS integrations. The OSS version needs a clean `linkedout` namespace designed for single-user, self-hosted use where the primary interface is a Claude Code / Codex / Copilot skill.

**Design principle:** Skills handle the "thinking" (interactive UX, natural language), CLI handles the "doing" (deterministic operations that skills invoke under the hood). CLI commands are building blocks, not the user-facing experience.

**Reference:** gstack CLI patterns — flat command list, category-based help, plain text output, short lowercase hyphen-separated names.

---

## The `linkedout` Namespace

Single entry point: `linkedout`

```
linkedout <command> [options]
```

Installed via `pip install -e .` in `pyproject.toml`:
```toml
[project.scripts]
linkedout = "linkedout.cli:cli"
```

No subgroups (no `linkedout db reset`). Flat command list like gstack. Commands are short, verb-first, self-documenting.

---

## Command Inventory: Existing → OSS

### Commands That Carry Forward

| Old Command | New Command | Changes |
|-------------|-------------|---------|
| `rcv2 db load-linkedin-csv` | `linkedout import-connections` | Rename. Auto-detect CSV format (LinkedIn, Google, generic). `--format linkedin\|google\|auto` flag, default `auto`. |
| `rcv2 db load-gmail-contacts` | `linkedout import-contacts` | Rename. Loads Google/iCloud contacts. `--format google\|icloud\|auto`. |
| `rcv2 db compute-affinity` | `linkedout compute-affinity` | Remove `--user-id` (single-user). Keep `--dry-run`. |
| `rcv2 db generate-embeddings` | `linkedout embed` | Rename. Covers both first-time generation and embedding. Supports OpenAI Batch API and local nomic provider. `--provider openai\|local\|auto`. Resumable. Progress bar. `--force` to embed all. |
| `rcv2 db reset` | `linkedout reset-db` | Simplify modes. Default: truncate data. `--full` for drop+recreate. `--yes` to skip confirmation. |
| `rcv2 dev start` | `linkedout start-backend` | Start backend API for Chrome extension. `--port 8001`. Only needed when extension is active. Clearer name for skill context. |

### Commands That Are Retired

| Old Command | Reason |
|-------------|--------|
| `rcv2 db seed` | Replaced by `import-seed` (loads from downloaded SQLite, not hardcoded fixtures) |
| `rcv2 db verify-seed` | Internal dev tool. Merged into `linkedout diagnostics`. |
| `rcv2 db validate-orm` | Internal dev tool. Stays in dev scripts, not user-facing CLI. |
| `rcv2 db enrich-companies` | Requires external PDL CSV file. Not user-facing — seed data ships pre-enriched. |
| `rcv2 db load-fixtures` | Dev-only. Not relevant for end users. |
| `rcv2 db load-apify` | Requires Apify dataset files. Extension handles crawling directly via API. |
| `rcv2 db seed-companies` | Replaced by `download-seed` + `import-seed` flow. |
| `rcv2 db fix-none-names` | One-off data fix. Not needed in clean OSS installs. |
| `rcv2 db backfill-seniority` | One-off backfill. Rolled into `import-connections` and import pipelines. |
| `rcv2 db classify-roles` | One-off backfill. Rolled into import pipelines. |
| `rcv2 db reconcile-stubs` | Rolled into `import-contacts` pipeline. |
| `rcv2 db download-profile-pics` | Dependent on Apify data. Extension handles this directly. |
| `rcv2 db backfill-experience-dates` | One-off backfill. Rolled into import pipelines. |
| `rcv2 test *` | Dev-only. Stays as `pytest` commands in CONTRIBUTING.md, not in user CLI. |
| `rcv2 prompt *` | Langfuse-specific. Disabled by default in OSS. |
| `rcv2 agent *` | TaskOS-specific. Stripped in OSS. |
| `be`, `fe`, `fe-setup` | Dev shortcuts. Not user-facing. |
| `pm` | Langfuse prompt manager. Not in OSS. |
| `run-all-agents` | TaskOS-specific. Stripped. |

### New Commands

| Command | Purpose | Invoked By |
|---------|---------|------------|
| `linkedout download-seed` | Download seed data (core ~50MB or full ~500MB) from GitHub Releases. Core = ~5K companies; Full = ~50-100K companies. Both tiers include full profile, role alias, funding, and experience data. Checksum verification, progress bar. `--full` for the 500MB set. | `/linkedout-setup` skill |
| `linkedout import-seed` | Import downloaded SQLite seed data into local PostgreSQL. Covers 10 tables: company, company_alias, role_alias, funding_round, startup_tracking, growth_signal, crawled_profile, experience, education, profile_skill. Idempotent. | `/linkedout-setup` skill |
| `linkedout diagnostics` | Comprehensive system health report: OS, Python, PostgreSQL version, disk space, config summary (secrets redacted), DB stats (table counts, embedding coverage), recent errors. Outputs JSON to `~/linkedout-data/reports/`. Shareable for bug reports. `--repair` flag to auto-fix common issues. | `/linkedout-setup-report` skill, user debugging |
| `linkedout status` | Quick one-line health check + stats. Shows: DB connected (Y/N), profiles loaded, companies available, embedding coverage %, affinity computed (Y/N), extension connected (Y/N). | `/linkedout` skill preamble |
| `linkedout version` | Print version, install path, Python version, DB connection status. Displays ASCII logo from `docs/brand/logo-ascii.txt`. | `/linkedout-upgrade` skill |
| `linkedout config` | Two subcommands only: `config show` (display current config, secrets redacted) and `config path` (show config file location). No get/set — users edit YAML directly or ask Claude. | User, skills |
| `linkedout report-issue` | Runs diagnostics, redacts privacy-sensitive info (profile names, emails, LinkedIn URLs, API keys, file paths with usernames), shows user the redacted report for approval, then files a GitHub issue via `gh issue create` with structured template. | User |

**Internal-only (not in `linkedout --help`):**

| Command | Purpose | Invoked By |
|---------|---------|------------|
| `linkedout migrate` | Run Alembic migrations. Wraps `alembic upgrade head`. `--dry-run` to preview. | `/linkedout-upgrade` skill only |

---

## Complete CLI Contract

### Help Text Format

Following gstack's pattern — category-grouped, scannable, no ANSI colors:

```
 _     _       _            _
| |   (_)_ __ | | _____  __| |
| |   | | '_ \| |/ / _ \/ _` |
| |___| | | | |   <  __/ (_| |
|_____|_|_| |_|_|\_\___|\__,_|
                            \
                             █▀▀█ █  █ ▀█▀
                             █  █ █  █  █
                             █▄▄█ ▀▄▄▀  █

AI-native professional network intelligence

Commands:
  Import:       import-connections, import-contacts, import-seed
  Seed Data:    download-seed
  Intelligence: compute-affinity, embed
  System:       status, diagnostics, version, config, report-issue
  Server:       start-backend
  Database:     reset-db

Run 'linkedout <command> --help' for details on any command.
```

### Command Reference

#### `linkedout import-connections`

Import your professional connections from a CSV file. Supports LinkedIn's data export format and Google Contacts CSV. Auto-detects the format, or specify explicitly.

**When to use:** During initial setup (the `/linkedout-setup` skill runs this), or whenever you download a fresh LinkedIn export to update your network.

```
linkedout import-connections [CSV_FILE] [OPTIONS]

Arguments:
  CSV_FILE              Path to CSV file (default: auto-detect in ~/Downloads)

Options:
  --format FORMAT       CSV format: linkedin, google, auto (default: auto)
  --dry-run             Parse and report only, do not write to DB
  --batch-size N        Rows per commit batch (default: 1000)
```

Output: Structured summary — rows parsed, profiles created, profiles updated, rows skipped (with reasons), rows failed (with reasons). Persists report to `~/linkedout-data/reports/`.

---

#### `linkedout import-contacts`

Import personal address book contacts from Google Contacts or iCloud vCard exports. These are your personal contacts (phone, email), distinct from LinkedIn connections. Automatically reconciles against existing connections to merge data.

**When to use:** During setup if you want to enrich your network with personal contact info (emails, phone numbers) from your address book.

```
linkedout import-contacts [CONTACTS_DIR] [OPTIONS]

Options:
  --format FORMAT       Contact format: google, icloud, auto (default: auto)
  --dry-run             Parse and report only, do not write to DB
```

Output: Same structured summary pattern as `import-connections`. Reconciles against existing LinkedIn connections automatically.

---

#### `linkedout compute-affinity`

Calculate affinity scores and Dunbar tiers for all connections.

```
linkedout compute-affinity [OPTIONS]

Options:
  --dry-run             Report stats only, do not compute
  --force               Recompute all (default: only unscored connections)
```

Output: Profiles scored, tier distribution (inner circle / close / active / peripheral), top changes since last run. Persists report.

---

#### `linkedout embed`

Generate vector embeddings for all profile text (bio, experience, skills) so semantic search works. Uses OpenAI Batch API (fast, ~$X for 4K profiles) or local nomic model (free, slower). Resumable — if interrupted, picks up where it left off.

**When to use:** During initial setup after importing connections. Also after switching embedding providers (e.g., nomic → OpenAI) to embed everything with `--force`.

```
linkedout embed [OPTIONS]

Options:
  --provider PROVIDER   Embedding provider: openai, local, auto (default: from config)
  --dry-run             Report what would be embedded, do not run
  --resume              Resume from last checkpoint (default: true)
  --force               Re-embed all profiles, even those with current embeddings
```

Output: Profiles total, profiles embedded, profiles skipped, provider used, dimension, estimated time remaining. Progress bar during execution. Resumable from checkpoint.

---

#### `linkedout download-seed`

Download pre-curated reference data from GitHub Releases. Includes company data, role aliases, public profile snapshots, experience, education, skills, and funding data. Two tiers: core (~50MB, ~5K companies + full profiles/roles) and full (~500MB, ~50-100K companies + same profiles/roles).

**When to use:** During initial setup. The `/linkedout-setup` skill runs this automatically. Run again with `--full` to upgrade from core to full company coverage.

**Why it matters:** Without seed data, your DB only has companies/profiles from your own LinkedIn connections. Seed data gives you broader company intelligence and pre-crawled profiles, so queries like "who do I know at Series B AI startups" work immediately.

```
linkedout download-seed [OPTIONS]

Options:
  --full                Download full dataset (~500MB) instead of core (~50MB)
  --output DIR          Download location (default: ~/linkedout-data/seed/)
  --force               Re-download even if file exists and checksum matches
```

Output: Download progress bar, checksum verification result.

---

#### `linkedout import-seed`

Import downloaded seed data into local PostgreSQL. Loads 10 tables: company, company_alias, role_alias, funding_round, startup_tracking, growth_signal, crawled_profile, experience, education, profile_skill.

**When to use:** After `download-seed`. The setup skill chains them: `linkedout download-seed && linkedout import-seed`.

```
linkedout import-seed [OPTIONS]

Options:
  --seed-file PATH      Path to seed SQLite file (default: auto-detect in ~/linkedout-data/seed/)
  --dry-run             Report what would be imported, do not write
```

Output: Per-table counts (imported, updated, skipped). Idempotent — safe to re-run.

---

#### `linkedout diagnostics`

Generate comprehensive system diagnostic report.

```
linkedout diagnostics [OPTIONS]

Options:
  --repair              Auto-fix common issues (missing embeddings, stale affinity, broken config)
  --json                Output as JSON (default: human-readable)
  --output PATH         Write report to file (default: ~/linkedout-data/reports/diagnostics-YYYYMMDD-HHMMSS.json)
```

Output sections:
1. **System:** OS, Python version, PostgreSQL version, disk space
2. **Config:** Active config file, embedding provider, API keys status (present/missing, never the value)
3. **Database:** Profile count, company count, connection count, embedding coverage %, affinity coverage %
4. **Health:** DB connectivity, embedding model loaded, recent errors from logs
5. **Recommendations:** Actionable next steps ("Run `linkedout compute-affinity` — 342 connections unscored")

---

#### `linkedout status`

Quick health check (designed for skill preambles).

```
linkedout status [OPTIONS]

Options:
  --json                Output as JSON (default: one-line human summary)
```

Output (human): `LinkedOut v0.1.0 | 4,012 profiles | 23,456 companies | embeddings: 98.2% | affinity: computed | extension: not connected`

Output (JSON): Same data as structured JSON for skill consumption.

---

#### `linkedout version`

Print version, environment info, and the LinkedOut ASCII logo. Quick way to verify your install.

```
linkedout version
```

Output:
```
 _     _       _            _
| |   (_)_ __ | | _____  __| |
| |   | | '_ \| |/ / _ \/ _` |
| |___| | | | |   <  __/ (_| |
|_____|_|_| |_|_|\_\___|\__,_|
                            \
                             █▀▀█ █  █ ▀█▀
                             █  █ █  █  █
                             █▄▄█ ▀▄▄▀  █

v0.1.0
Python 3.12.3 | PostgreSQL 16.2
Config: ~/.linkedout/config.yaml
Data:   ~/linkedout-data/
```

---

#### `linkedout config`

View current configuration. Two subcommands only — for changes, edit `~/.linkedout/config.yaml` directly (or ask Claude).

```
linkedout config show               Show current config (secrets redacted)
linkedout config path               Show config file location
```

---

#### `linkedout report-issue`

One-command bug reporting. Runs diagnostics internally, redacts privacy-sensitive info (profile names, emails, LinkedIn URLs, API keys, file paths containing usernames), shows you the redacted report for approval, then files a GitHub issue with a structured template.

**When to use:** When something's broken and you want to report it with enough context for remote debugging.

```
linkedout report-issue [OPTIONS]

Options:
  --dry-run             Show the redacted report without filing an issue
```

Requires: `gh` CLI authenticated with GitHub.

---

#### `linkedout start-backend`

Start the backend HTTP API server on localhost. Only needed when using the Chrome extension — the extension talks to this server for profile crawling and enrichment. Not needed for core skill-based usage (skills query the DB directly).

**When to use:** When you've installed the Chrome extension and want to start crawling LinkedIn profiles. The `/linkedout-extension-setup` skill runs this automatically.

```
linkedout start-backend [OPTIONS]

Options:
  --port PORT           Bind port (default: 8001)
  --host HOST           Bind host (default: 127.0.0.1)
  --background          Run as background daemon
```

---

#### `linkedout reset-db`

Reset the database.

```
linkedout reset-db [OPTIONS]

Options:
  --full                Drop all tables and recreate (default: truncate data only)
  --yes                 Skip confirmation prompt
```

---

## Design Decisions

### 1. Flat namespace, no subgroups

**Decision:** `linkedout import-connections`, not `linkedout db import-connections`.

**Rationale:** Users interact with ~12 commands total. Subgroups add cognitive overhead without organizational benefit at this scale. gstack uses flat commands successfully with ~40+ commands. The category-grouped help text provides discoverability without requiring users to remember group names.

### 2. `--dry-run` on every write command

**Decision:** Every command that modifies state supports `--dry-run`.

**Rationale:** Users (and skills) should be able to preview what will happen before committing. This is especially important for OSS where users may be experimenting with their own data.

### 3. Structured output with `--json` where useful

**Decision:** `status` and `diagnostics` support `--json`. Import commands always produce structured summary output.

**Rationale:** Skills need machine-readable output to make decisions. Human-readable is the default for direct CLI use. No need for `--json` on commands like `migrate` or `reset-db` where the output is inherently simple.

### 4. Auto-detection over explicit format flags

**Decision:** `import-connections` auto-detects LinkedIn vs Google CSV format. `import-contacts` auto-detects Google vs iCloud. Explicit `--format` available as override.

**Rationale:** Reduces friction in the skill-driven onboarding flow. The skill says "drop your CSV here" and the CLI figures out what it is.

### 5. One-off backfills rolled into import pipelines

**Decision:** `backfill-seniority`, `classify-roles`, `reconcile-stubs`, `backfill-experience-dates` are not separate commands. Their logic runs as part of `import-connections` and `import-contacts` import pipelines.

**Rationale:** In the private version, these were created as post-hoc fixes for data imported before the classification logic existed. In OSS, imports run the full pipeline from the start. No need for separate backfill commands. If a user needs to re-run classification, `--force` on the import command or a future `linkedout enrich-profiles` command covers it.

### 6. `download-seed` + `import-seed` as separate commands

**Decision:** Two-step flow, not a single `linkedout seed` command.

**Rationale:** Separation of concerns. Download can fail (network issues, disk space) independently of import (DB issues, schema mismatch). Users can inspect the downloaded file before importing. Seeds can be shared/cached across multiple installs. The setup skill chains them: `linkedout download-seed && linkedout import-seed`.

### 7. `start-backend` instead of `be` / `dev start`

**Decision:** `linkedout serve` starts the backend API. No `be` shortcut.

**Rationale:** `be` was a dev convenience. In OSS, the backend is only needed for the Chrome extension. `start-backend` clearly communicates what it does. The `--background` flag supports daemon mode for the extension setup skill.

### 8. `diagnostics` subsumes multiple internal tools

**Decision:** `diagnostics` replaces `verify-seed`, `validate-orm`, and ad-hoc health checks.

**Rationale:** Users don't care about ORM validation or seed verification as separate concepts. They care about "is my system healthy?" `diagnostics` answers that question comprehensively. The `--repair` flag handles the "fix it for me" case.

### 9. No `search` command

**Decision:** No CLI search command. Claude Code queries the DB directly.

**Rationale:** The existing backend search algorithm is outperformed by Claude Code constructing SQL queries against the schema. The skill knows the schema, can write joins, can interpret results in context. A CLI `search` command would be a worse version of what the skill already does.

### 10. No `best-hop` command

**Decision:** No `best-hop` CLI command.

**Rationale:** Best-hop requires mutual connection data, which only exists when the Chrome extension has been actively crawling. It's not a standalone CLI operation — it's an extension feature exposed via the side panel. If demand warrants it, a future `linkedout best-hop <person>` could query the API, but this is out of scope for v1.

---

## Operation Result Pattern

Every CLI command that modifies data follows this output contract:

```
1. Progress during execution:     Processing profiles... 2,847/4,012
2. Summary on completion:         Succeeded: 3,998 | Skipped: 12 | Failed: 2
3. Failures listed with reasons:  FAILED: "John Doe" — duplicate LinkedIn URL
                                  FAILED: "Jane Smith" — missing required field: company
4. Report persisted:              Report saved: ~/linkedout-data/reports/import-connections-20260407-143000.json
```

This pattern is enforced by a shared `OperationResult` class that all commands use. Commands never exit silently with just "Done".

---

## Dev-Only Commands (Not in `linkedout` CLI)

These stay as internal dev tools, documented in CONTRIBUTING.md, not installed as user-facing CLI:

| Command | Access | Purpose |
|---------|--------|---------|
| `pytest tests/` | Direct pytest | Run test suite |
| `alembic revision --autogenerate` | Direct alembic | Create new migration |
| `ruff check src/` | Direct ruff | Lint code |
| `pyright src/` | Direct pyright | Type check |
| `rcv2 db validate-orm` | Keep as dev script | ORM validation |
| `rcv2 db load-fixtures` | Keep as dev script | Load dev fixtures |
| `rcv2 db enrich-companies` | Keep as dev script | PDL enrichment (maintainer only) |

---

## Migration Path

For the existing private codebase (`rcv2` namespace):

1. Create new `linkedout/cli.py` with Click groups refactored to flat commands
2. Reuse existing command implementations — the underlying `main()` functions in `dev_tools/*.py` are stable
3. Add thin wrappers that map new CLI args to existing function signatures
4. `pyproject.toml` gets a single `linkedout = "linkedout.cli:cli"` entry point
5. Legacy `rcv2` entry point can coexist during transition (documented in CONTRIBUTING.md)

---

## Future Commands (Not in v1, but designed for)

These are explicitly **not** in v1 but the namespace is reserved:

| Command | When | Purpose |
|---------|------|---------|
| `linkedout enrich-profiles` | When local enrichment is added | Re-run enrichment pipeline on existing profiles |
| `linkedout export` | When export feature is added | Export network data (CSV, JSON) |
| `linkedout backup` | When backup feature is added | Backup `~/linkedout-data/` |
| `linkedout extension-status` | With extension maturity | Extension health check |

---

## Appendix: Full Existing Command Audit

For completeness, here is every entry point in the current `pyproject.toml` and its disposition:

| Entry Point | Current Function | OSS Disposition |
|-------------|-----------------|-----------------|
| `rcv2` | `dev_tools.cli:cli` | **Replaced** by `linkedout` |
| `pm` | `utilities.prompt_manager.cli:pm` | **Retired** (Langfuse-specific) |
| `dev` | `dev_tools.cli:cli` | **Retired** (alias for rcv2) |
| `be` | `dev_tools.cli:be_command` | **Retired** → `linkedout serve` |
| `fe` | `dev_tools.cli:fe_command` | **Retired** (no frontend in OSS) |
| `fe-setup` | `dev_tools.fe_setup:main` | **Retired** (no frontend in OSS) |
| `run-all-agents` | `dev_tools.run_all_agents:main` | **Retired** (TaskOS-specific) |
| `reset-db` | `dev_tools.cli:reset_db_command` | **Carried** → `linkedout reset-db` |
| `seed-db` | `dev_tools.cli:seed_db_command` | **Retired** → `linkedout import-seed` |
| `verify-seed` | `dev_tools.cli:verify_seed_command` | **Retired** → `linkedout diagnostics` |
| `validate-orm` | `dev_tools.cli:validate_orm_command` | **Retired** (dev-only) |
| `precommit-tests` | `dev_tools.cli:precommit_tests_command` | **Retired** (dev-only, use pytest) |
| `eval-tests` | `dev_tools.cli:eval_tests_command` | **Retired** (dev-only) |
| `load-linkedin-csv` | `dev_tools.cli:db_load_linkedin_csv` | **Carried** → `linkedout import-connections` |
| `load-gmail-contacts` | `dev_tools.cli:db_load_gmail_contacts` | **Carried** → `linkedout import-contacts` |
| `download-profile-pics` | `dev_tools.cli:db_download_profile_pics` | **Retired** (Apify-dependent) |
| `fix-none-names` | `dev_tools.cli:fix_none_names_command` | **Retired** (one-off fix) |
| `backfill-seniority` | `dev_tools.cli:backfill_seniority_command` | **Retired** (rolled into import) |
| `backfill-experience-dates` | `dev_tools.cli:backfill_experience_dates_command` | **Retired** (rolled into import) |
| `compute-affinity` | `dev_tools.cli:compute_affinity_command` | **Carried** → `linkedout compute-affinity` |

### Commands in `rcv2 db` group (via `cli.py`):

| Command | OSS Disposition |
|---------|-----------------|
| `rcv2 db reset` | **Carried** → `linkedout reset-db` |
| `rcv2 db seed` | **Retired** → `linkedout import-seed` |
| `rcv2 db verify-seed` | **Retired** → `linkedout diagnostics` |
| `rcv2 db validate-orm` | **Retired** (dev-only) |
| `rcv2 db enrich-companies` | **Retired** (maintainer-only, keep as dev script) |
| `rcv2 db load-fixtures` | **Retired** (dev-only) |
| `rcv2 db load-apify` | **Retired** (Apify-specific) |
| `rcv2 db generate-embeddings` | **Carried** → `linkedout embed` |
| `rcv2 db seed-companies` | **Retired** → `linkedout download-seed` + `import-seed` |
| `rcv2 db load-linkedin-csv` | **Carried** → `linkedout import-connections` |
| `rcv2 db load-gmail-contacts` | **Carried** → `linkedout import-contacts` |
| `rcv2 db fix-none-names` | **Retired** (one-off) |
| `rcv2 db backfill-seniority` | **Retired** (rolled into import) |
| `rcv2 db classify-roles` | **Retired** (rolled into import) |
| `rcv2 db compute-affinity` | **Carried** → `linkedout compute-affinity` |
| `rcv2 db reconcile-stubs` | **Retired** (rolled into `import-contacts`) |
| `rcv2 db download-profile-pics` | **Retired** (Apify-dependent) |
| `rcv2 db backfill-experience-dates` | **Retired** (rolled into import) |

---

## Summary

| Category | Count | Commands |
|----------|-------|----------|
| **Carried forward** | 6 | `import-connections`, `import-contacts`, `compute-affinity`, `embed`, `reset-db`, `start-backend` |
| **New (user-facing)** | 7 | `download-seed`, `import-seed`, `diagnostics`, `status`, `version`, `config`, `report-issue` |
| **New (internal)** | 1 | `migrate` (invoked by upgrade skill only) |
| **Retired** | ~20 | See audit above |
| **Total user-facing commands** | **13** | Flat namespace under `linkedout` |
