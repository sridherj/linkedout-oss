# Phase 9: AI-Native Setup Flow — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Ready for detailed planning review
**Phase goal:** A user clones the repo, runs `/linkedout-setup`, and has a fully working system — with a quantified readiness report proving it.
**Dependencies:** Phases 2 (env & config), 3 (logging & observability), 4 (constants externalization), 5 (embedding abstraction), 6 (code cleanup), 7 (seed data), 8 (skill system)
**Delivers:** The `/linkedout-setup` skill, the `scripts/system-setup.sh` sudo script, the complete onboarding flow, an installation test suite, and a quantified readiness report framework.

---

## Phase 0 Decisions That Constrain This Phase

| Decision Doc | Constraint on Phase 9 |
|---|---|
| `docs/decision/cli-surface.md` | Setup invokes flat `linkedout` namespace commands: `import-connections`, `import-contacts`, `embed`, `compute-affinity`, `download-seed`, `import-seed`, `diagnostics`, `status`. No subgroups. |
| `docs/decision/env-config-design.md` | All config under `~/linkedout-data/config/`. Three-layer hierarchy: env vars > config.yaml > secrets.yaml > defaults. `agent-context.env` generated for Claude skills. `DATABASE_URL` in config.yaml (not secrets). `LINKEDOUT_DATA_DIR` overridable. |
| `docs/decision/logging-observability-strategy.md` | Setup logs to `~/linkedout-data/logs/setup.log`. Each step follows operation result pattern: Progress → Summary → Gaps → Next steps → Report path. loguru with human-readable format. Failed setup produces `setup-diagnostic-*.txt`. |
| `docs/decision/queue-strategy.md` | No Procrastinate. Enrichment runs synchronously. No worker setup needed. |
| `docs/decision/2026-04-07-data-directory-convention.md` | Default `~/linkedout-data/`. Env var override via `LINKEDOUT_DATA_DIR`. |
| `docs/decision/2026-04-07-embedding-model-selection.md` | Default local model is nomic-embed-text-v1.5 (768d, ~275MB). Not MiniLM. OpenAI is the fast alternative (Batch API). |
| `docs/decision/2026-04-07-skill-distribution-pattern.md` | SKILL.md manifest, git-clone + setup script pattern. Skills installed to platform-specific directories. |

---

## Dependencies on Prior Phases

| Phase | What Phase 9 Needs From It |
|---|---|
| Phase 2 (Env & Config) | `LinkedOutSettings` pydantic-settings class, `~/linkedout-data/` directory layout, config.yaml/secrets.yaml generation, `agent-context.env` generation |
| Phase 3 (Logging & Observability) | `get_logger()` with component binding, `OperationReport` dataclass, readiness report framework, metrics module, setup-specific log file routing |
| Phase 4 (Constants) | All hardcoded values externalized to config. Setup can reference config defaults. |
| Phase 5 (Embedding) | `EmbeddingProvider` ABC, `OpenAIEmbeddingProvider`, `LocalEmbeddingProvider`, `linkedout embed` CLI command, progress tracking & resumability |
| Phase 6 (Code Cleanup) | CLI surface refactored to `linkedout` namespace. Procrastinate removed. `project_mgmt` stripped. Tests green. |
| Phase 7 (Seed Data) | `linkedout download-seed` and `linkedout import-seed` working. Seed manifest on GitHub Releases. |
| Phase 8 (Skill System) | SKILL.md template system, host configs for Claude Code/Codex/Copilot, `bin/generate-skills`, skill installation paths defined |

---

## DESIGN GATE (Task 9A — Must Complete First)

> **Before ANY implementation begins**, produce a UX design doc (`docs/design/setup-flow-ux.md`) that specifies:
> - Every question asked to the user, in order, with exact wording
> - Every message/output shown to the user at each step
> - Progress display format (step N of M, time estimates, cost estimates)
> - Error messages and recovery guidance for each failure mode
> - What the readiness report looks like
> - What the diagnostic report looks like when setup fails
>
> **This doc must be reviewed and approved by SJ before implementation starts.**

---

## Task Breakdown

### 9A. UX Design Doc

**Goal:** Complete user-facing flow specification — every screen, question, message, error, and output the user sees during setup. This is the blueprint for all subsequent tasks.

**File to create:** `docs/design/setup-flow-ux.md`

**Contents:**
1. **Step inventory** — Numbered list of every setup step with its purpose
2. **User prompts** — Exact wording of every question asked (OS detection, DB password, API keys, CSV path, seed tier, embedding provider)
3. **Progress format** — Step N of M header, sub-step progress bars, time estimates, cost estimates for API-dependent steps
4. **Success messages** — What the user sees after each step completes
5. **Error messages** — For every failure mode: missing prerequisite, wrong Python version, DB creation failure, network error during seed download, invalid API key, CSV parse error, embedding failure. Each with: (a) what went wrong, (b) how to fix it, (c) how to retry
6. **Readiness report format** — The final output: profile count, embedding coverage, company count, affinity status, gap list, next steps
7. **Diagnostic report format** — What gets written to `setup-diagnostic-*.txt` on failure
8. **Idempotency behavior** — What the user sees when re-running setup on a working system (skip messages, gap detection, repair offers)
9. **Skip/resume behavior** — How partially completed setup resumes

**Integration points:**
- References Phase 3 operation result pattern for step output format
- References Phase 3 readiness report framework for final report
- References `docs/decision/env-config-design.md` for config file locations
- References `docs/decision/cli-surface.md` for CLI commands invoked

**Acceptance criteria:**
- [ ] Every user interaction is specified with exact wording
- [ ] Every error has a recovery path
- [ ] Readiness report mock-up included
- [ ] SJ has approved the document

**Complexity:** M

---

### 9B. Prerequisites Detection

**Goal:** Detect the user's OS and verify/guide installation of system dependencies (PostgreSQL, Python 3.11+). This runs before the sudo script — it determines what the sudo script needs to do.

**Files to create/modify:**
- `backend/src/linkedout/setup/prerequisites.py` — OS detection, version checks, dependency verification
- `backend/src/linkedout/setup/__init__.py` — Package init

**Implementation details:**

1. **OS detection** — Detect and classify:
   - Linux: Debian/Ubuntu (apt), Arch (pacman), RPM/Fedora (dnf/yum)
   - macOS (brew)
   - Windows/WSL (detect WSL2, recommend WSL if native Windows)
   - Return: `PlatformInfo(os, distro, package_manager, arch)`

2. **PostgreSQL check:**
   - Check `psql --version` for PostgreSQL client
   - Check `pg_isready` for running server
   - Check PostgreSQL version >= 14 (for pgvector compatibility)
   - Check `pgvector` extension available: `psql -c "SELECT * FROM pg_available_extensions WHERE name = 'vector'"`
   - Check `pg_trgm` extension available
   - Return: `PostgresStatus(installed, running, version, has_pgvector, has_pg_trgm)`

3. **Python check:**
   - Check `python3 --version` >= 3.11
   - Check `pip` or `pip3` available
   - Check `venv` module available (`python3 -c "import venv"`)
   - Return: `PythonStatus(installed, version, has_pip, has_venv)`

4. **Disk space check:**
   - Check free space on `~/linkedout-data/` mount point
   - Minimum: 2GB (core seed + DB + embeddings). Recommended: 5GB (full seed).

**Integration points:**
- Uses Phase 3 `get_logger(__name__, component="setup", operation="prerequisites")` for logging
- Uses Phase 2 `LINKEDOUT_DATA_DIR` for disk space check location
- Results feed into `scripts/system-setup.sh` (task 9C) and setup flow UX

**Acceptance criteria:**
- [ ] Correctly detects Ubuntu, Arch, Fedora, macOS, WSL
- [ ] Correctly reports PostgreSQL version, pgvector/pg_trgm availability
- [ ] Correctly reports Python version and pip/venv availability
- [ ] Disk space check returns human-readable free space
- [ ] All checks are non-destructive (read-only)

**Complexity:** M

---

### 9C. Sudo Setup Script (`scripts/system-setup.sh`)

**Goal:** A minimal, auditable shell script that does ONLY the things requiring sudo. Users can read it before running. Everything after this script is user-space.

**File to create:** `scripts/system-setup.sh`

**Design principles:**
- **Auditable:** Every action has a comment explaining what and why
- **Idempotent:** Safe to re-run. Uses `CREATE IF NOT EXISTS`, `createuser --no-op-if-exists` patterns
- **Minimal:** Only 5 operations require sudo (see below)
- **Detectable:** Takes platform info as argument or auto-detects

**Script contents:**

```bash
#!/usr/bin/env bash
# LinkedOut OSS — System Setup (requires sudo)
# This script installs system-level dependencies.
# Read it before running: cat scripts/system-setup.sh
#
# What this script does:
#   1. Installs postgresql + postgresql-contrib (for pg_trgm)
#   2. Installs postgresql-XX-pgvector (version-matched)
#   3. Ensures PostgreSQL service is running
#   4. Creates the 'linkedout' database user
#   5. Creates the 'linkedout' database
#   6. Installs SQL extensions (vector, pg_trgm) as superuser
#
# What this script does NOT do:
#   - Install Python (user should have Python 3.11+ already)
#   - Create venvs or install pip packages
#   - Write any config files
#   - Touch ~/linkedout-data/
```

**Platform-specific logic:**
- **Debian/Ubuntu:** `apt install postgresql postgresql-contrib postgresql-XX-pgvector`
- **Arch:** `pacman -S postgresql` + AUR `pgvector`
- **Fedora/RPM:** `dnf install postgresql-server postgresql-contrib pgvector_XX`
- **macOS:** `brew install postgresql@16 pgvector` — **Note (review finding 2026-04-07):** Homebrew's `pgvector` formula may not version-match automatically with `postgresql@16`. The script must detect whether `brew install pgvector` installs a compatible version, and if not, fall back to building pgvector from source against the installed PostgreSQL. Add a post-install verification step: `psql -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>&1` to confirm pgvector loads.
- **WSL:** Same as Debian/Ubuntu (most WSL distros are Ubuntu-based)

**PostgreSQL version matching:** The script must detect the installed PostgreSQL major version and install the matching pgvector package (e.g., `postgresql-16-pgvector` for PostgreSQL 16).

**Database setup:**
```bash
sudo -u postgres createuser --no-superuser --createdb --no-createrole linkedout 2>/dev/null || true
sudo -u postgres createdb --owner=linkedout linkedout 2>/dev/null || true
sudo -u postgres psql -d linkedout -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d linkedout -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

**Integration points:**
- Called by the `/linkedout-setup` skill with user confirmation
- Prerequisites detection (9B) runs first to determine what's needed
- The setup skill shows the user what the script will do before running it

**Acceptance criteria:**
- [ ] Script is idempotent (re-run produces no errors, no duplicate resources)
- [ ] PostgreSQL is running and accepting connections after script completes
- [ ] `linkedout` database exists with `vector` and `pg_trgm` extensions
- [ ] `linkedout` user exists and owns the database
- [ ] Script works on Ubuntu 22.04/24.04, macOS with Homebrew
- [ ] Every action has an explanatory comment
- [ ] Script exits with clear error message if a step fails

**Complexity:** M

---

### 9D. Database Setup (User-Space)

**Goal:** Configure the database connection, generate a secure password, run Alembic migrations, and write config files. All user-space — no sudo required.

**Files to create/modify:**
- `backend/src/linkedout/setup/database.py` — DB setup logic
- Modifies `~/linkedout-data/config/config.yaml` (generated)
- Modifies `~/linkedout-data/config/agent-context.env` (generated)

**Implementation details:**

1. **Password generation:** Generate a cryptographically secure random password (32 chars, alphanumeric). Use `secrets.token_urlsafe(24)`.

2. **Set PostgreSQL password:**
   ```sql
   ALTER USER linkedout WITH PASSWORD 'generated_password';
   ```

3. **Write config.yaml:** Generate `~/linkedout-data/config/config.yaml` with the `database_url` containing the generated password. Use the template from `docs/decision/env-config-design.md`.

4. **Run Alembic migrations:** `linkedout migrate` (internal command wrapping `alembic upgrade head`). Use the newly written `DATABASE_URL` from config.

5. **Verify schema:** Check that key tables exist: `crawled_profile`, `company`, `connection`, `experience`, `education`, `profile_skill`, `role_alias`, `company_alias`, `funding_round`.

6. **Generate agent-context.env:**
   ```env
   DATABASE_URL=postgresql://linkedout:GENERATED@localhost:5432/linkedout
   LINKEDOUT_TENANT_ID=system
   LINKEDOUT_BU_ID=default
   LINKEDOUT_USER_ID=system
   ```

**Integration points:**
- Uses Phase 2 `LinkedOutSettings` for config file path resolution
- Uses Phase 2 directory layout (creates `~/linkedout-data/config/` if not exists)
- Uses Phase 6 `linkedout migrate` internal command
- Uses Phase 3 `get_logger(__name__, component="setup", operation="db_setup")` for logging
- Produces `OperationReport` (Phase 3) with migration results

**Acceptance criteria:**
- [ ] Password is cryptographically random, not guessable
- [ ] `config.yaml` is generated with correct `database_url`
- [ ] Alembic migrations run successfully
- [ ] All expected tables exist after migration
- [ ] `agent-context.env` is generated with correct values
- [ ] Re-running skips password generation if `config.yaml` already has a `database_url`
- [ ] Re-running still runs migrations (to catch new migrations after upgrade)

**Complexity:** M

---

### 9E. Python Environment Setup

**Goal:** Create a virtual environment, install dependencies, and install CLI entry points.

**Files to create/modify:**
- `backend/src/linkedout/setup/python_env.py` — venv creation and package installation

**Implementation details:**

1. **Create venv:** `python3 -m venv .venv` in the repo root (not in `~/linkedout-data/` — venv is part of the development install)

2. **Activate and install:**
   ```bash
   .venv/bin/pip install uv
   .venv/bin/uv pip install -r backend/requirements.txt
   .venv/bin/uv pip install -e backend/
   ```

3. **Verify CLI entry point:** `.venv/bin/linkedout --help` returns help text

4. **Optional: local embedding model pre-download:** If embedding provider is `local`, trigger model download of nomic-embed-text-v1.5 (~275MB). Show download progress. This avoids a surprise download later during `linkedout embed`.

**Integration points:**
- Uses Phase 2 `LINKEDOUT_EMBEDDING_PROVIDER` config to decide whether to pre-download local model
- Uses Phase 5 `LocalEmbeddingProvider` for model download
- Verifies CLI works via `linkedout version` (Phase 6)

**Acceptance criteria:**
- [ ] `.venv/` created in repo root
- [ ] All pip packages installed without errors
- [ ] `linkedout --help` works from the venv
- [ ] `linkedout version` shows correct version info
- [ ] Re-running skips venv creation if `.venv/` exists and is valid
- [ ] Re-running still runs `uv pip install -r` (to catch new dependencies after upgrade)

**Complexity:** S

---

### 9F. API Key Collection

**Goal:** Guide the user through providing API keys with cost explanations and provider choice.

**Files to create/modify:**
- `backend/src/linkedout/setup/api_keys.py` — API key collection and validation logic

**Implementation details:**

1. **Embedding provider choice:**
   - Present two options with clear cost/speed tradeoffs:
     - **OpenAI** (recommended for speed): Batch API, ~$0.02 per 1K profiles, ~minutes for 4K profiles. Requires `OPENAI_API_KEY`.
     - **Local nomic** (free, slower): nomic-embed-text-v1.5, ~275MB model download, ~N hours for 4K profiles on CPU. No API key needed.
   - Write choice to `~/linkedout-data/config/config.yaml` as `embedding_provider: openai|local`

2. **OpenAI API key** (if openai chosen):
   - Prompt for key
   - Validate: make a test embedding call with a short string
   - On success: write to `~/linkedout-data/config/secrets.yaml`
   - On failure: show error, offer to retry or switch to local

3. **Apify API key** (optional):
   - Explain: only needed for Chrome extension LinkedIn crawling
   - Explain: $5 per 1000 profiles, first 5000 free on Apify
   - If provided: write to `~/linkedout-data/config/secrets.yaml`
   - If skipped: note that extension enrichment won't work without it

4. **Secrets file permissions:**
   - `chmod 600 ~/linkedout-data/config/secrets.yaml`
   - Warn if file has open permissions

**Integration points:**
- Uses Phase 2 `LinkedOutSettings` for config/secrets file paths
- Uses Phase 5 `OpenAIEmbeddingProvider` for key validation
- Uses Phase 3 `get_logger()` for logging API key status (never log the key itself)
- UX design doc (9A) specifies exact prompt wording and cost numbers

**Acceptance criteria:**
- [ ] User can choose between OpenAI and local embedding provider
- [ ] OpenAI key is validated before being stored
- [ ] Invalid key produces a clear error with retry option
- [ ] `secrets.yaml` has `chmod 600` permissions
- [ ] API keys are NEVER logged (not even at DEBUG level)
- [ ] Re-running detects existing keys and offers to keep or replace
- [ ] Apify key is clearly communicated as optional

**Complexity:** M

---

### 9G. User Profile Setup

**Goal:** Accept the user's LinkedIn profile URL, enrich their own profile, and explain affinity scoring.

**Files to create/modify:**
- `backend/src/linkedout/setup/user_profile.py` — User profile setup logic

**Implementation details:**

1. **Accept LinkedIn URL:**
   - Prompt for LinkedIn profile URL (e.g., `https://linkedin.com/in/username`)
   - Validate URL format (must be a valid LinkedIn profile URL)
   - Extract LinkedIn public ID from URL

2. **Create/update user's profile in DB:**
   - Create a `crawled_profile` record for the user
   - Mark as the owner profile (used for affinity calculation base)
   - Store LinkedIn URL and public ID

3. **Explain affinity scoring:**
   - Brief explanation: "Affinity scoring measures how close each connection is to you based on career overlap, shared education, mutual connections, and interaction signals."
   - Explain that the user's own profile is the anchor for all affinity calculations

4. **Note about enrichment:**
   - If Apify key is configured: offer to enrich the user's profile via Apify (gets full experience, education, skills)
   - If no Apify key: explain that manual data entry or CSV import will provide the base data

**Integration points:**
- Uses existing `crawled_profile` domain (Phase 6 verified working)
- Uses Phase 3 logging
- Feeds into Phase 9L (affinity computation)

**Acceptance criteria:**
- [ ] Valid LinkedIn URL accepted and parsed
- [ ] User profile created in DB
- [ ] Invalid URL produces clear error
- [ ] Re-running detects existing user profile and offers to update or keep
- [ ] Affinity explanation is concise and understandable

**Complexity:** S

---

### 9H. LinkedIn CSV Import

**Goal:** Guide the user through downloading their LinkedIn connections CSV and importing it.

**Files to create/modify:**
- `backend/src/linkedout/setup/csv_import.py` — Guided CSV import flow

**Implementation details:**

1. **Guidance step:**
   - Provide link to LinkedIn data export page
   - Step-by-step instructions: Settings → Data Privacy → Get a copy of your data → Connections
   - Note: LinkedIn takes ~10 minutes to prepare the export
   - Provide screenshot references (stored in `docs/images/linkedin-export-*.png`)

2. **CSV file location:**
   - Auto-detect: scan `~/Downloads/` for files matching `Connections*.csv` or `connections*.csv`
   - If found: confirm with user ("Found Connections.csv in ~/Downloads/ — use this? [Y/n]")
   - If not found: prompt for path
   - Copy CSV to `~/linkedout-data/uploads/` for record-keeping

3. **Import execution:**
   - Run `linkedout import-connections <csv_path>`
   - Show progress: "Importing connections... X/Y profiles"
   - Show result summary (Phase 3 operation result pattern)

**Integration points:**
- Uses Phase 6 `linkedout import-connections` CLI command
- Uses Phase 3 `OperationReport` for import results
- Uses existing `import_pipeline` module (`backend/src/linkedout/import_pipeline/`)
- CSV converter: `backend/src/linkedout/import_pipeline/converters/linkedin_csv.py`

**Acceptance criteria:**
- [ ] LinkedIn CSV auto-detected in ~/Downloads/
- [ ] Manual path entry works
- [ ] Import produces structured result summary (imported, skipped, failed counts)
- [ ] Report persisted to `~/linkedout-data/reports/import-connections-*.json`
- [ ] Re-running on same CSV produces "skipped: already imported" (idempotent)
- [ ] Invalid CSV produces clear error with format guidance

**Complexity:** S

---

### 9I. Contacts Import (Optional)

**Goal:** Optionally import Google or iCloud contacts to enrich the network with personal contact info.

**Files to create/modify:**
- `backend/src/linkedout/setup/contacts_import.py` — Guided contacts import flow

**Implementation details:**

1. **Ask user:** "Would you like to import your Google or iCloud contacts? This adds phone numbers and emails to your network. [y/N]"

2. **If yes — Google Contacts:**
   - Guide: contacts.google.com → Export → Google CSV
   - Auto-detect in ~/Downloads/
   - Run `linkedout import-contacts <path> --format google`

3. **If yes — iCloud Contacts:**
   - Guide: icloud.com/contacts → Select All → Export vCard
   - Run `linkedout import-contacts <path> --format icloud`

4. **Reconciliation:** The import command automatically reconciles against existing LinkedIn connections (matching by name, email, company).

**Integration points:**
- Uses Phase 6 `linkedout import-contacts` CLI command
- Uses existing `import_pipeline/converters/google_*.py` converters
- Uses Phase 3 `OperationReport` for import results

**Acceptance criteria:**
- [ ] Skip works cleanly (user says N, no further prompts)
- [ ] Google CSV import works with reconciliation
- [ ] iCloud vCard import works with reconciliation
- [ ] Result summary shows reconciliation stats (matched, new, skipped)
- [ ] Idempotent on re-run

**Complexity:** S

---

### 9J. Seed Data Setup

**Goal:** Download and import the seed company database.

**Files to create/modify:**
- `backend/src/linkedout/setup/seed_data.py` — Seed download and import orchestration

**Implementation details:**

1. **Core seed (mandatory):**
   - Run `linkedout download-seed` — downloads core seed (~50MB) from GitHub Releases
   - Show download progress bar
   - Run `linkedout import-seed` — imports into local PostgreSQL
   - Show import progress with per-table counts

2. **Full seed (optional):**
   - Prompt: "Download the full company database (~500MB, ~50-100K companies)? This gives broader company intelligence. [y/N]"
   - If yes: `linkedout download-seed --full` then `linkedout import-seed`

3. **Checksum verification:** Both download commands verify SHA256 checksum from seed manifest.

**Integration points:**
- Uses Phase 7 `linkedout download-seed` and `linkedout import-seed` CLI commands
- Uses Phase 7 seed manifest (`seed-manifest.json`) for checksum verification
- Downloads from GitHub Releases (Phase 7 publishes assets)
- Uses Phase 3 `OperationReport` for import results

**Acceptance criteria:**
- [ ] Core seed downloads with progress bar
- [ ] Checksum verification passes
- [ ] Import reports per-table counts (company, company_alias, role_alias, etc.)
- [ ] Full seed prompt is clear about size and benefit
- [ ] Re-running skips download if checksum matches existing file
- [ ] Network failure produces actionable error (retry instructions, manual download URL)

**Complexity:** S

---

### 9K. Embedding Generation

**Goal:** Generate vector embeddings for all imported profiles using the chosen provider.

**Files to create/modify:**
- `backend/src/linkedout/setup/embeddings.py` — Embedding generation orchestration

**Implementation details:**

1. **Provider selection:** Read from config (set in 9F): `openai` or `local`

2. **Pre-generation info:**
   - Count profiles needing embeddings
   - Estimate time: OpenAI Batch API (~minutes for 4K profiles), local nomic (~X seconds per profile on CPU)
   - Estimate cost: OpenAI (~$0.02 per 1K profiles)
   - Show: "Generating embeddings for N profiles using [provider]. Estimated time: ~X minutes."

3. **Execute:** Run `linkedout embed --provider <provider>`
   - Progress bar with profile count
   - Resumable — if interrupted, picks up where it left off (Phase 5 progress tracking)

4. **Result:** Show embedding output artifact summary (profiles embedded, duration, provider, dimension)

**Integration points:**
- Uses Phase 5 `linkedout embed` CLI command
- Uses Phase 5 `EmbeddingProvider` (OpenAI or Local)
- Uses Phase 5 progress tracking (`~/linkedout-data/state/embedding_progress.json`)
- Uses Phase 3 `OperationReport` for results

**Acceptance criteria:**
- [ ] Correct provider used based on config
- [ ] Time/cost estimate shown before starting
- [ ] Progress bar displays during generation
- [ ] Resumable after interruption
- [ ] Report persisted with profiles embedded, skipped, failed counts
- [ ] Re-running only embeds profiles without embeddings (idempotent)

**Complexity:** M

---

### 9L. Affinity Computation

**Goal:** Compute affinity scores for all connections.

**Files to create/modify:**
- `backend/src/linkedout/setup/affinity.py` — Affinity computation orchestration

**Implementation details:**

1. **Pre-computation check:** Verify user profile exists (set in 9G) — required as affinity anchor.

2. **Execute:** Run `linkedout compute-affinity`
   - Progress: "Computing affinity scores... X/Y connections"

3. **Result summary:**
   - Profiles scored, tier distribution (inner circle / close / active / peripheral)
   - Brief explanation of what the tiers mean

**Integration points:**
- Uses Phase 6 `linkedout compute-affinity` CLI command
- Uses existing affinity scoring logic in `backend/src/linkedout/intelligence/scoring/`
- Uses Phase 3 `OperationReport` for results
- Depends on user profile from 9G being set as the anchor

**Acceptance criteria:**
- [ ] Affinity computed for all connections
- [ ] Tier distribution shown (how many in each Dunbar tier)
- [ ] Report persisted to `~/linkedout-data/reports/compute-affinity-*.json`
- [ ] Clear error if user profile not set (with instruction to run 9G)
- [ ] Re-running recomputes only unscored connections (unless `--force`)

**Complexity:** S

---

### 9M. Quantified Readiness Check

**Goal:** Produce a detailed, quantified readiness report — NOT a pass/fail boolean. This is the definitive "is setup complete?" artifact.

**Files to create/modify:**
- `backend/src/linkedout/setup/readiness.py` — Readiness check and report generation

**Implementation details:**

The readiness report collects data from all setup steps and produces a comprehensive JSON artifact:

```json
{
  "operation": "setup-readiness",
  "timestamp": "2026-04-07T14:30:00Z",
  "linkedout_version": "0.1.0",
  "counts": {
    "profiles_loaded": 4012,
    "profiles_with_embeddings": 3998,
    "profiles_without_embeddings": 14,
    "companies_loaded": 52000,
    "companies_missing_aliases": 156,
    "role_aliases_loaded": 2847,
    "connections_with_affinity": 3870,
    "connections_without_affinity": 0,
    "seed_tables_populated": 10
  },
  "coverage": {
    "embedding_coverage_pct": 99.7,
    "affinity_coverage_pct": 100.0,
    "company_match_pct": 95.9
  },
  "config": {
    "embedding_provider": "openai",
    "data_dir": "~/linkedout-data",
    "db_connected": true,
    "openai_key_configured": true,
    "apify_key_configured": false,
    "agent_context_env_exists": true
  },
  "gaps": [
    {"type": "missing_embeddings", "count": 14, "detail": "14 profiles have no embedding vector"},
    {"type": "missing_company_aliases", "count": 156, "detail": "156 companies have no aliases"}
  ],
  "next_steps": [
    "Run `linkedout embed` to generate embeddings for 14 remaining profiles",
    "Try: `/linkedout \"who do I know at Stripe?\"`"
  ]
}
```

**Console output:** Human-readable summary derived from the JSON:
```
╔══════════════════════════════════════════════╗
║         LinkedOut Setup — Readiness          ║
╚══════════════════════════════════════════════╝

  Profiles:     4,012 loaded | 3,998 with embeddings (99.7%)
  Companies:    52,000 loaded | 95.9% of connections matched
  Affinity:     3,870 / 3,870 connections scored (100%)
  Config:       OpenAI embeddings | ~/linkedout-data/

  Gaps:
    ⚠ 14 profiles without embeddings
    ⚠ 156 companies without aliases

  Next steps:
    → Run `linkedout embed` to cover remaining 14 profiles
    → Try: /linkedout "who do I know at Stripe?"

  Report saved: ~/linkedout-data/reports/setup-readiness-20260407-143000.json
```

**Integration points:**
- Uses Phase 3 readiness report framework (`OperationReport`)
- Queries database for counts (profiles, companies, embeddings, affinity)
- Reads config files for config status
- Report format must be consistent with Phase 3K specification

**Acceptance criteria:**
- [ ] JSON report contains all fields shown above
- [ ] Console output is human-readable and informative
- [ ] Report persisted to `~/linkedout-data/reports/setup-readiness-*.json`
- [ ] Precise counts — never "done" or "complete", always numbers
- [ ] Gaps listed with actionable remediation
- [ ] Report is sufficient for remote diagnosis when shared in a GitHub issue

**Complexity:** M

---

### 9N. Gap Detection & Auto-Repair

**Goal:** After readiness check, detect and offer to fix gaps automatically.

**Files to create/modify:**
- `backend/src/linkedout/setup/auto_repair.py` — Gap detection and repair orchestration

**Implementation details:**

1. **Read readiness report** from 9M

2. **For each gap type, offer repair:**
   - **Missing embeddings:** "Found 14 profiles without embeddings. Generate now? [Y/n]" → runs `linkedout embed`
   - **Missing affinity scores:** "Found 47 connections without affinity scores. Compute now? [Y/n]" → runs `linkedout compute-affinity --force`
   - **Stale embeddings (wrong provider):** "Found 200 profiles with openai embeddings but config is set to local. Re-embed? [y/N]" (default no — this is expensive)

3. **After repairs:** Re-run readiness check to produce updated report

4. **Idempotent:** Each repair only processes items that actually need fixing

**Integration points:**
- Uses Phase 3 auto-repair hooks (3M) framework
- Invokes Phase 6 CLI commands (`linkedout embed`, `linkedout compute-affinity`)
- Uses Phase 3 `OperationReport` for repair results
- Re-runs 9M readiness check after repairs

**Acceptance criteria:**
- [ ] Each gap type has a targeted repair action
- [ ] User is prompted before each repair (no silent actions)
- [ ] Repairs are idempotent
- [ ] Updated readiness report generated after repairs
- [ ] User can decline individual repairs

**Complexity:** M

---

### 9O. Skill Installation

**Goal:** Install LinkedOut skills to the detected AI platform directories.

**Files to create/modify:**
- `backend/src/linkedout/setup/skill_install.py` — Skill detection and installation

**Implementation details:**

1. **Detect installed platforms:**
   - Claude Code: check for `~/.claude/` directory
   - Codex: check for `~/.agents/` directory
   - Copilot: check for `~/.copilot/` or `~/.github/` directory

2. **For each detected platform:**
   - Generate skills from templates: run `bin/generate-skills` (Phase 8)
   - Copy/symlink generated skills to platform directory:
     - Claude Code: `~/.claude/skills/linkedout/`
     - Codex: `~/.agents/skills/linkedout/`
     - Copilot: `~/.copilot/skills/linkedout/`
   - Verify: skill files exist at target location

3. **CLAUDE.md / AGENTS.md update:**
   - Add routing rules to the platform's dispatch file
   - Include path to `agent-context.env` so skills can find DB credentials

4. **Report:** "Skills installed for: Claude Code, Codex. Try: /linkedout \"who do I know at Stripe?\""

**Integration points:**
- Uses Phase 8 `bin/generate-skills` for template rendering
- Uses Phase 8 host configs for platform-specific paths
- Uses Phase 8 SKILL.md template system
- References `~/linkedout-data/config/agent-context.env` (generated in 9D)

**Acceptance criteria:**
- [ ] Correctly detects installed AI platforms
- [ ] Skills installed to correct directories per platform
- [ ] Routing rules added to dispatch files
- [ ] `agent-context.env` path referenced in skill configs
- [ ] Re-running updates skills (handles skill upgrades)
- [ ] Missing platform (e.g., no Codex) skipped gracefully

**Complexity:** M

---

### 9P. Setup Logging Integration

**Goal:** Every setup step logs consistently using Phase 3 infrastructure. Failed setup produces a shareable diagnostic file.

**Files to create/modify:**
- `backend/src/linkedout/setup/logging_integration.py` — Setup-specific logging configuration

**Implementation details:**

1. **Setup correlation ID:** Generate `setup_{timestamp}` correlation ID at setup start. All steps use this ID.

2. **Per-step logging:** Each step logs:
   - Start: `"Starting step 4/12: Database setup"`
   - Key parameters: `"PostgreSQL 16.2, database: linkedout"`
   - Progress milestones: `"Migration 001: applied (45ms)"`
   - Result: `"Database setup complete (3.2s)"`
   - Or failure: `"Database setup FAILED: connection refused (localhost:5432)"`

3. **Setup log file:** All setup output routed to `~/linkedout-data/logs/setup.log` (appended across re-runs)

4. **Failure diagnostic:**
   - On any step failure, auto-generate `~/linkedout-data/logs/setup-diagnostic-YYYYMMDD-HHMMSS.txt`
   - Contents: system info, config summary (redacted), step-by-step log, error details, last 50 lines of relevant log files
   - Tell user: "Setup failed. Diagnostic saved to: ~/linkedout-data/logs/setup-diagnostic-*.txt — attach this to a GitHub issue for help."

5. **Each step produces an artifact:** Every step that processes items uses Phase 3L operation result pattern (progress → summary → gaps → report path)

**Integration points:**
- Uses Phase 3 `get_logger()` with `component="setup"` binding
- Uses Phase 3 correlation ID infrastructure
- Uses Phase 3 `OperationReport` for per-step results
- Uses Phase 3 log file routing to `~/linkedout-data/logs/setup.log`

**Acceptance criteria:**
- [ ] All setup steps log to `~/linkedout-data/logs/setup.log`
- [ ] Correlation ID traces through all steps
- [ ] Failed setup produces a diagnostic file
- [ ] Diagnostic file is sufficient for remote debugging
- [ ] No API keys or passwords in log files or diagnostics

**Complexity:** M

---

### 9Q. Idempotent Re-Run

**Goal:** Running `/linkedout-setup` on an already-setup system skips completed steps, detects gaps, and offers repairs. Never corrupts existing data.

**Files to create/modify:**
- `backend/src/linkedout/setup/orchestrator.py` — Main setup orchestrator with step tracking

**Implementation details:**

1. **Step state tracking:** Persist step completion to `~/linkedout-data/state/setup-state.json`:
   ```json
   {
     "steps_completed": {
       "prerequisites": "2026-04-07T14:20:00Z",
       "system_setup": "2026-04-07T14:21:00Z",
       "database": "2026-04-07T14:22:00Z",
       "python_env": "2026-04-07T14:23:00Z",
       "api_keys": "2026-04-07T14:24:00Z",
       "user_profile": "2026-04-07T14:25:00Z",
       "csv_import": "2026-04-07T14:26:00Z",
       "seed_data": "2026-04-07T14:28:00Z",
       "embeddings": "2026-04-07T14:35:00Z",
       "affinity": "2026-04-07T14:36:00Z",
       "skills": "2026-04-07T14:37:00Z"
     },
     "setup_version": "0.1.0",
     "last_run": "2026-04-07T14:37:00Z"
   }
   ```

2. **Skip logic:** For each step:
   - Check if step is marked complete AND the underlying state is still valid
   - If valid: show "✓ Step N: Already complete (skipping)"
   - If invalid (e.g., DB exists but migrations are behind): re-run the step

3. **Re-run as health check:** On an already-setup system, the flow becomes:
   - Skip all completed steps (showing ✓ for each)
   - Run readiness check (9M) — always runs
   - Detect and offer repairs (9N) — always runs
   - Produce fresh readiness report

4. **Version-aware:** If `setup_version` in state < current version, force re-run of relevant steps (e.g., new migrations, updated skills).

**Integration points:**
- All previous tasks (9B-9P) — orchestrates them
- Uses Phase 2 `LINKEDOUT_DATA_DIR` for state file path
- Uses Phase 3 logging throughout

**Acceptance criteria:**
- [ ] Second run on a complete setup takes <5 seconds (just validation)
- [ ] Second run produces a fresh readiness report
- [ ] Partially completed setup resumes from where it left off
- [ ] No data loss or duplication on re-run
- [ ] Version upgrade triggers appropriate step re-runs
- [ ] State file is human-readable JSON

**Complexity:** L

---

### 9R. Installation Test Suite

**Goal:** Dedicated test suite for the setup/installation flow. These are integration tests that touch the real OS — too heavy for every CI push, run on nightly schedule.

**Files to create:**
- `tests/installation/test_fresh_install.py` — End-to-end fresh install test
- `tests/installation/test_prerequisites.py` — Prerequisite detection tests
- `tests/installation/test_idempotency.py` — Re-run safety tests
- `tests/installation/test_partial_recovery.py` — Interrupted install recovery
- `tests/installation/test_permissions.py` — Security and permission tests
- `tests/installation/test_degraded.py` — Degraded environment (no internet, bad keys)
- `tests/installation/conftest.py` — Shared fixtures (temp data dir, test DB)
- `tests/installation/README.md` — How to run installation tests

**Test categories:**

| Test | What It Catches | How |
|------|----------------|-----|
| **Fresh install smoke test** | "Works on my machine" bugs | Provision clean env, run full setup, assert readiness report has zero gaps |
| **Prerequisite detection** | Users with partial installs | Test correct detection of: missing PostgreSQL, wrong Python version, missing pgvector, insufficient disk |
| **Idempotency test** | Re-run corruption | Run setup twice — second run skips completed steps, produces clean readiness report, zero data loss |
| **Partial failure recovery** | Interrupted installs | Kill setup mid-way (after DB creation, before seed import). Re-run. Verify graceful recovery. |
| **Permission tests** | Security and trust | Verify `secrets.yaml` gets `chmod 600`. Verify no secrets in log files. |
| **Degraded environment** | Clear error messages | Test: GitHub down during seed download (timeout → actionable error). Invalid OpenAI key (clear message). |
| **Readiness report as assertion** | Quantified pass/fail | Every test ends by reading readiness report JSON and asserting: zero gaps, expected counts |
| **Upgrade path test** | Broken upgrades | Install v0.1.0, run setup. Simulate upgrade. Verify migrations run, data intact. |

**Fixtures:**
- `temp_data_dir` — creates isolated `~/linkedout-data-test-{uuid}/` for each test
- `test_db` — creates isolated PostgreSQL database `linkedout_test_{uuid}`
- `mock_github_releases` — serves seed data from local files (no network)
- `mock_openai` — validates key format without real API call

**Running:**
```bash
# Full installation test suite (requires real PostgreSQL)
pytest tests/installation/ -v --tb=long

# Just prerequisite detection (no DB needed)
pytest tests/installation/test_prerequisites.py -v
```

**CI integration:** Not in the main CI workflow. Separate GitHub Actions workflow triggered:
- Nightly on `main`
- On release branches
- Manually via `workflow_dispatch`
- Matrix: Ubuntu 24.04 + macOS-latest × Python 3.11/3.12/3.13 × PostgreSQL 16/17

**Integration points:**
- Tests all tasks 9B-9Q
- Uses Phase 3 readiness report as test oracle
- CI workflow defined in Phase 13 (13A)

**Acceptance criteria:**
- [ ] All 8 test categories have at least one test
- [ ] Tests pass on Ubuntu 24.04 with PostgreSQL 16
- [ ] Tests use isolated data dirs and databases (no interference with real data)
- [ ] Tests clean up after themselves
- [ ] `README.md` documents how to run tests and what they require
- [ ] Tests are skippable individually (for platforms not available)

**Complexity:** L

---

## File Map: What Gets Created

| Path (relative to repo root) | Task | Type |
|---|---|---|
| `docs/design/setup-flow-ux.md` | 9A | UX design doc |
| `backend/src/linkedout/setup/__init__.py` | 9B | Package init |
| `backend/src/linkedout/setup/prerequisites.py` | 9B | OS/dependency detection |
| `scripts/system-setup.sh` | 9C | Sudo install script |
| `backend/src/linkedout/setup/database.py` | 9D | DB setup |
| `backend/src/linkedout/setup/python_env.py` | 9E | Venv setup |
| `backend/src/linkedout/setup/api_keys.py` | 9F | API key collection |
| `backend/src/linkedout/setup/user_profile.py` | 9G | User profile |
| `backend/src/linkedout/setup/csv_import.py` | 9H | CSV import guide |
| `backend/src/linkedout/setup/contacts_import.py` | 9I | Contacts import |
| `backend/src/linkedout/setup/seed_data.py` | 9J | Seed orchestration |
| `backend/src/linkedout/setup/embeddings.py` | 9K | Embedding generation |
| `backend/src/linkedout/setup/affinity.py` | 9L | Affinity computation |
| `backend/src/linkedout/setup/readiness.py` | 9M | Readiness report |
| `backend/src/linkedout/setup/auto_repair.py` | 9N | Gap detection/repair |
| `backend/src/linkedout/setup/skill_install.py` | 9O | Skill installation |
| `backend/src/linkedout/setup/logging_integration.py` | 9P | Setup logging |
| `backend/src/linkedout/setup/orchestrator.py` | 9Q | Main orchestrator |
| `tests/installation/conftest.py` | 9R | Test fixtures |
| `tests/installation/test_fresh_install.py` | 9R | Smoke test |
| `tests/installation/test_prerequisites.py` | 9R | Detection tests |
| `tests/installation/test_idempotency.py` | 9R | Re-run tests |
| `tests/installation/test_partial_recovery.py` | 9R | Recovery tests |
| `tests/installation/test_permissions.py` | 9R | Security tests |
| `tests/installation/test_degraded.py` | 9R | Degraded env tests |
| `tests/installation/README.md` | 9R | Test docs |

---

## Testing Strategy

### Unit Tests (run in CI)

- `backend/src/linkedout/setup/prerequisites.py` — mock OS detection, version parsing
- `backend/src/linkedout/setup/database.py` — mock subprocess calls, verify config generation
- `backend/src/linkedout/setup/api_keys.py` — mock API validation, verify secrets.yaml generation
- `backend/src/linkedout/setup/readiness.py` — mock DB queries, verify report format
- `backend/src/linkedout/setup/orchestrator.py` — comprehensive orchestrator tests (review finding 2026-04-07: this is the most complex module, needs thorough coverage):
  - **State file loading:** missing file (first run) → returns empty state; valid file → parses correctly; corrupted/malformed JSON → recovers gracefully (treats as first run, logs warning, does NOT crash)
  - **State file writing:** writes atomically (temp file + rename, never leaves partial write); state file reflects exact steps completed
  - **Skip/resume logic:** uncompleted step → runs; completed step with valid underlying state → skips; completed step with `always_run=True` → runs; step marked complete but underlying state invalid (e.g., DB dropped) → re-runs with explanation
  - **Version-aware re-runs:** `setup_version` < current version → forces re-run of `database`, `python_env`, `skills`; same version → normal skip logic
  - **Partial failure recovery:** step 6 fails → state saves steps 1-5 as complete; re-run skips steps 1-5, retries step 6; step failure does NOT corrupt state of already-completed steps
  - **Step ordering:** steps execute in defined order; step with unmet dependency raises clear error; mutable `SetupContext` passes data between steps correctly (e.g., `db_url` from step 3 available to step 7)
  - **Performance:** second run on fully-complete setup completes in < 5 seconds (mock all steps, verify no expensive validation on skip)
  - **Edge cases:** empty data directory (first install); `LINKEDOUT_DATA_DIR` override; read-only state directory → clear error

### Integration Tests (require real PostgreSQL)

- DB setup: create real DB, run migrations, verify tables
- CSV import: import real test CSV, verify profile count
- Seed import: import test seed data, verify table counts
- Readiness check: verify counts against real DB

### Installation Tests (nightly, real OS — task 9R)

- Full end-to-end flows on clean environments
- Platform-specific tests (Ubuntu, macOS)

---

## Exit Criteria Verification Checklist

- [ ] New user on fresh Ubuntu can go from `git clone` to `/linkedout "who do I know at..."` in one session
- [ ] New user on fresh macOS can do the same
- [ ] Readiness report shows precise coverage numbers (never "done", always N/M)
- [ ] Re-running setup on a working system produces a clean readiness report with zero gaps
- [ ] Re-running setup on a working system takes <5 seconds (skips completed steps)
- [ ] Any issue filed can include a readiness JSON with enough data to diagnose remotely
- [ ] Failed setup produces a diagnostic file with system info, config, and error details
- [ ] No API keys, passwords, or LinkedIn URLs appear in any log file
- [ ] `scripts/system-setup.sh` is readable and auditable
- [ ] Every setup step follows the operation result pattern (Progress → Summary → Gaps → Report path)
- [ ] All installation tests pass on Ubuntu 24.04 + macOS

---

## Complexity Summary

| Task | Complexity | Estimated Effort |
|------|-----------|-----------------|
| 9A. UX Design Doc | M | Requires SJ review — GATE |
| 9B. Prerequisites Detection | M | Cross-platform detection logic |
| 9C. Sudo Setup Script | M | Multi-distro package management |
| 9D. Database Setup | M | Config generation + migration |
| 9E. Python Environment | S | Straightforward venv + pip |
| 9F. API Key Collection | M | Validation + cost guidance UX |
| 9G. User Profile Setup | S | Simple DB write |
| 9H. LinkedIn CSV Import | S | Wraps existing CLI command |
| 9I. Contacts Import | S | Wraps existing CLI command |
| 9J. Seed Data Setup | S | Wraps existing CLI commands |
| 9K. Embedding Generation | M | Provider selection + progress |
| 9L. Affinity Computation | S | Wraps existing CLI command |
| 9M. Quantified Readiness | M | Multi-table DB queries + report format |
| 9N. Gap Detection & Repair | M | Per-gap-type repair logic |
| 9O. Skill Installation | M | Multi-platform detection + symlinks |
| 9P. Setup Logging | M | Correlation IDs + diagnostic generation |
| 9Q. Idempotent Re-Run | L | State tracking + skip/resume + version awareness |
| 9R. Installation Test Suite | L | Multi-platform, real OS, CI integration |

**Total: 5 S + 9 M + 2 L**

---

## Open Questions

1. **WSL detection reliability:** How reliably can we detect WSL2 vs native Windows vs other Linux-in-Windows solutions (Cygwin, MSYS2)? Need to test `/proc/version` heuristics. May need to just ask the user if detection is ambiguous.

2. **macOS Homebrew PostgreSQL pgvector version matching:** Homebrew's `pgvector` formula may not version-match automatically with `postgresql@16`. Need to verify: does `brew install pgvector` work alongside `postgresql@16`, or does it need `postgresql@16`-specific pgvector?

3. **Venv location:** The plan says `.venv` in repo root. But if the user clones to a read-only location or a location without write permissions, this fails. Should we support `LINKEDOUT_VENV_DIR` override, or is repo root always safe to assume writable?

4. **Skill installation on first clone:** Phase 8 must deliver `bin/generate-skills` before Phase 9 can install skills. If skills aren't generated yet (fresh clone, no Phase 8 artifacts), should setup generate them automatically, or should setup require Phase 8 to have been completed first?

5. **Setup step ordering for API key skip:** If a user skips OpenAI key (choosing local embedding), the embedding step (9K) will take significantly longer. Should we re-confirm after showing the time estimate? e.g., "Generating embeddings locally will take ~4 hours. Switch to OpenAI? [y/N]"

6. **Database password storage in config.yaml:** Per `docs/decision/env-config-design.md`, `DATABASE_URL` (including password) goes in `config.yaml`, not `secrets.yaml`. This is intentional (single-user localhost), but should the setup flow explicitly explain this decision to the user, or just do it silently?

7. **Seed data unavailability at v0.1.0:** At initial launch, GitHub Releases may not have seed data published yet. Setup needs a graceful fallback: "Seed data not yet available. Your database will contain only your imported connections. Seed data will be available in a future release."
