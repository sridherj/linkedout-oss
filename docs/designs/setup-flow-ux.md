# Setup Flow UX Design — `/linkedout-setup`

**Phase:** 9A — AI-Native Setup Flow  
**Status:** Draft — Awaiting SJ Approval (DESIGN GATE)  
**Date:** 2026-04-07  
**Author:** Claude (taskos-subphase-runner agent)

---

## Overview

This document specifies every user-facing interaction in the `/linkedout-setup` skill. The user is a developer interacting through a Claude Code / Codex / Copilot skill. All output is plain text rendered in a terminal. The skill orchestrates CLI commands under the hood — the user sees progress, prompts, and results.

The setup flow takes a fresh clone of the LinkedOut repo and produces a fully working system with a quantified readiness report.

---

## Section 1: Step Inventory

The setup flow consists of 14 steps. Steps 1–5 are infrastructure (always required). Steps 6–11 are data pipeline (some optional). Steps 12–14 are finalization (always run).

| # | Step | Purpose | Interactive? |
|---|------|---------|-------------|
| 1 | Prerequisites Detection | Detect OS, PostgreSQL, Python, disk space | No (auto-detect) |
| 2 | System Setup | Install PostgreSQL, pgvector, pg_trgm via sudo script | Yes (confirm before sudo) |
| 3 | Database Setup | Generate password, write config, run migrations | No (auto) |
| 4 | Python Environment | Create .venv, install packages, verify CLI | No (auto) |
| 5 | API Key Collection | Choose embedding provider, collect API keys | Yes (prompts) |
| 6 | User Profile | Accept LinkedIn URL, create profile record | Yes (prompt) |
| 7 | LinkedIn CSV Import | Guide CSV export, auto-detect file, import | Yes (confirm file) |
| 8 | Contacts Import | Optionally import Google/iCloud contacts | Yes (opt-in) |
| 9 | Seed Data | Download and import company reference data | Yes (tier choice) |
| 10 | Embedding Generation | Generate vector embeddings for all profiles | Yes (confirm before start) |
| 11 | Affinity Computation | Calculate affinity scores and Dunbar tiers | No (auto) |
| 12 | Skill Installation | Detect platforms, install skills | Yes (confirm per platform) |
| 13 | Readiness Check | Produce quantified readiness report | No (auto) |
| 14 | Gap Detection & Repair | Offer to fix any gaps found | Yes (per-gap prompts) |

---

## Section 2: User Prompts

Every question the user is asked, in order, with exact wording. Prompts are formatted as skill text output — no ANSI colors, no emoji beyond the checkmark (✓) and warning (⚠) symbols.

### Step 1: Prerequisites Detection

No user prompts. Auto-detection only.

Output on ambiguous WSL detection:

```
Detected platform: Windows Subsystem for Linux (WSL2)
Distribution: Ubuntu 24.04

Note: LinkedOut runs natively inside WSL. All commands and paths
refer to the WSL filesystem, not Windows.
```

### Step 2: System Setup

**Prompt 2a — Review sudo script:**

```
Step 2 of 14: System Setup

LinkedOut needs PostgreSQL with the pgvector and pg_trgm extensions.
The setup script will run the following actions with sudo:

  1. Install postgresql and postgresql-contrib
  2. Install postgresql-16-pgvector
  3. Start the PostgreSQL service
  4. Create database user 'linkedout'
  5. Create database 'linkedout'
  6. Enable extensions: vector, pg_trgm

You can review the script: cat scripts/system-setup.sh

Run the system setup script? [Y/n]
```

If user declines or has no sudo access:

```
  Skipping system setup. You can run it later:
    sudo bash scripts/system-setup.sh

  Or install the prerequisites manually — see CONTRIBUTING.md
  for platform-specific instructions (Ubuntu, macOS, Arch).
```

On macOS (detected automatically):

```
Step 2 of 14: System Setup

LinkedOut needs PostgreSQL with the pgvector and pg_trgm extensions.

  macOS detected — using Homebrew (no sudo required).

  The setup will run:
    1. brew install postgresql@16
    2. brew install pgvector
    3. brew services start postgresql@16
    4. createuser linkedout
    5. createdb linkedout
    6. Enable extensions: vector, pg_trgm

  Proceed? [Y/n]
```

On system-setup.sh failure:

```
  ✗ System setup script failed at step: {failed_step}

  Error output:
    {last_5_lines_of_stderr}

  This is usually a package manager issue. Try running manually:
    sudo bash scripts/system-setup.sh 2>&1 | tail -20

  If the issue is a missing package repository or GPG key,
  see the troubleshooting section in CONTRIBUTING.md.

  After fixing, re-run /linkedout-setup.
```

If PostgreSQL is already installed and all prerequisites are met:

```
Step 2 of 14: System Setup

  ✓ PostgreSQL 16.2 is installed and running
  ✓ pgvector extension available
  ✓ pg_trgm extension available
  ✓ Database user 'linkedout' exists
  ✓ Database 'linkedout' exists

System setup: nothing to do.
```

### Step 3: Database Setup

No user prompts. Auto-generates password and writes config.

Output shown to user:

```
Step 3 of 14: Database Setup

  Generating secure database password...
  Writing ~/linkedout-data/config/config.yaml...
  Running database migrations...
    Applied 12 migrations in 1.8s
  Verifying schema: 10 tables confirmed
  Writing ~/linkedout-data/config/agent-context.env...

Database setup complete.

Your database password is stored in ~/linkedout-data/config/config.yaml.
You do not need to remember it — LinkedOut reads it automatically.
```

### Step 4: Python Environment

No user prompts.

```
Step 4 of 14: Python Environment

  Creating virtual environment: .venv/
  Installing dependencies via uv...
    62 packages installed in 8.3s
  Verifying CLI entry point...
    linkedout v0.1.0 — OK

Python environment ready.
```

### Step 5: API Key Collection

**Prompt 5a — Embedding provider choice:**

```
Step 5 of 14: API Key Collection

LinkedOut uses vector embeddings for semantic search ("who do I know
in climate tech?"). Choose an embedding provider:

  [1] OpenAI  (recommended)
      Fast. Uses the Batch API with text-embedding-3-small.
      Cost: ~$0.01 for 1,000 profiles. A typical network of 4,000
      connections costs about $0.04 total, one-time.
      Requires an OpenAI API key.

  [2] Local   (free, slower)
      Uses nomic-embed-text-v1.5 running on your CPU.
      Downloads a ~275 MB model on first use.
      Takes ~5–15 minutes for 4,000 profiles on a typical laptop.
      No API key needed.

Choose embedding provider [1/2] (default: 1):
```

**Prompt 5b — OpenAI API key (if OpenAI chosen):**

```
Enter your OpenAI API key.
You can find it at: https://platform.openai.com/api-keys

OpenAI API key: sk-...
```

On successful validation:

```
  ✓ OpenAI API key validated (test embedding succeeded)
```

On failed validation:

```
  ✗ OpenAI API key invalid: 401 Unauthorized

  Check that your key is correct and has not been revoked.
  Get a new key at: https://platform.openai.com/api-keys

  Options:
    [1] Enter a different key
    [2] Switch to local embeddings (free, no key needed)

  Choice [1/2]:
```

**Prompt 5c — Apify API key (optional):**

```
Apify API key (optional)

Apify enriches LinkedIn profiles with data beyond what the
Voyager API provides (full work history, education details,
skills). The Chrome extension crawls profiles directly via
LinkedIn's API — Apify is used only for deeper enrichment.

Skip this if you are not planning to use the Chrome extension.
You can always add this key later in ~/linkedout-data/config/secrets.yaml.

Enter Apify API key (or press Enter to skip):
```

### Step 6: User Profile

**Prompt 6a — LinkedIn URL:**

```
Step 6 of 14: User Profile

Your LinkedIn profile is the anchor for affinity scoring — it
determines how "close" each connection is to you based on career
overlap, shared education, and professional signals.

Enter your LinkedIn profile URL
(e.g., https://linkedin.com/in/yourname):
```

On invalid URL:

```
  ✗ That does not look like a LinkedIn profile URL.
    Expected format: https://linkedin.com/in/yourname
    or https://www.linkedin.com/in/yourname

  Enter your LinkedIn profile URL:
```

### Step 7: LinkedIn CSV Import

**Prompt 7a — Export guidance:**

```
Step 7 of 14: LinkedIn CSV Import

To import your connections, you need a CSV export from LinkedIn.

How to get it:
  1. Go to linkedin.com/mypreferences/d/download-my-data
  2. Select "Connections" (you only need this one)
  3. Click "Request archive"
  4. Wait for the email from LinkedIn (~10 minutes)
  5. Download and unzip the archive
  6. The file you need is "Connections.csv"

If you already have the CSV, great — we will auto-detect it.
```

**Prompt 7b — File confirmation (auto-detected):**

```
  Found: ~/Downloads/Connections.csv (3.2 MB, modified today)

  Use this file? [Y/n]
```

**Prompt 7b-alt — File not found:**

```
  Could not find a Connections CSV in ~/Downloads/.

  Options:
    [1] Enter the file path manually
    [2] Skip for now (you can import later with: linkedout import-connections)

  Choice [1/2]:
```

**Prompt 7b-skip — User chooses to skip:**

```
  Skipping CSV import.

  When you have your CSV ready, run:
    linkedout import-connections ~/path/to/Connections.csv

  Then re-run /linkedout-setup to complete embedding generation
  and affinity scoring for the new connections.
```

### Step 8: Contacts Import

**Prompt 8a — Opt-in:**

```
Step 8 of 14: Contacts Import (optional)

You can import your personal contacts (Google or iCloud) to
enrich your network with phone numbers and email addresses.
These are matched against your LinkedIn connections automatically.

Import personal contacts? [y/N]
```

If yes:

**Prompt 8b — Format selection:**

```
  Contact format:
    [1] Google Contacts CSV  (export from contacts.google.com)
    [2] iCloud vCard          (export from icloud.com/contacts)

  Choice [1/2]:
```

**Prompt 8c — File path (Google):**

```
  Export your contacts:
    1. Go to contacts.google.com
    2. Click the gear icon → Export
    3. Select "Google CSV" format
    4. Save the file

  Enter path to Google Contacts CSV
  (or press Enter to auto-detect in ~/Downloads/):
```

**Prompt 8c-alt — File path (iCloud):**

```
  Export your contacts:
    1. Go to icloud.com/contacts
    2. Select All (Cmd+A / Ctrl+A)
    3. Click the gear icon → Export vCard

  Enter path to iCloud vCard file
  (or press Enter to auto-detect in ~/Downloads/):
```

### Step 9: Seed Data

**Prompt 9a — Seed tier:**

```
Step 9 of 14: Seed Data

LinkedOut ships pre-curated company data so queries like "who do I
know at Series B AI startups?" work immediately, even before you
crawl any profiles with the Chrome extension.

  Core dataset (default):  ~50 MB download
    ~5,000 companies with funding data, role aliases, and
    pre-crawled public profile snapshots

  Full dataset:            ~500 MB download
    ~50,000+ companies — same data, broader coverage

You can upgrade from core to full at any time by running:
  linkedout download-seed --full && linkedout import-seed

Download which dataset? [core/full] (default: core):
```

### Step 10: Embedding Generation

**Prompt 10a — Confirmation with estimates:**

Using OpenAI:

```
Step 10 of 14: Embedding Generation

  Profiles needing embeddings: 4,012
  Provider: OpenAI (text-embedding-3-small, Batch API)
  Estimated time: ~2–3 minutes
  Estimated cost: ~$0.04 (one-time, via Batch API)

  Generate embeddings now? [Y/n]
```

Using local:

```
Step 10 of 14: Embedding Generation

  Profiles needing embeddings: 4,012
  Provider: Local (nomic-embed-text-v1.5, 768 dimensions)
  Model size: ~275 MB (will download if not cached)
  Estimated time: ~5–15 minutes (depends on CPU)
  Cost: Free

  Generate embeddings now? [Y/n]
```

### Step 11: Affinity Computation

No user prompts. Runs automatically after embeddings.

### Step 12: Skill Installation

**Prompt 12a — Per-platform confirmation:**

```
Step 12 of 14: Skill Installation

  Detected AI platforms:
    ✓ Claude Code  (~/.claude/)
    ✓ Codex        (~/.agents/)

  Install LinkedOut skills for these platforms? [Y/n]
```

If user says yes, for each platform:

```
  Installing skills for Claude Code...
    Generated 4 skill files from templates
    Installed to ~/.claude/skills/linkedout/
    Updated ~/.claude/CLAUDE.md with routing rules
  ✓ Claude Code skills installed

  Installing skills for Codex...
    Generated 4 skill files from templates
    Installed to ~/.agents/skills/linkedout/
    Updated ~/.agents/AGENTS.md with routing rules
  ✓ Codex skills installed
```

### Step 13: Readiness Check

No user prompts. See Section 6 for output format.

### Step 14: Gap Detection & Repair

Per-gap prompts. See Section 6 for context.

**Prompt 14a — Missing embeddings:**

```
  ⚠ 14 profiles have no embedding vector.

  Generate embeddings for these 14 profiles now? [Y/n]
```

**Prompt 14b — Missing affinity scores:**

```
  ⚠ 47 connections have no affinity score.

  Compute affinity for these 47 connections now? [Y/n]
```

**Prompt 14c — Stale embeddings (provider mismatch):**

```
  ⚠ 200 profiles have openai embeddings, but your config uses local.
  Re-embedding these profiles takes ~1–3 minutes locally.

  Re-embed with local provider? [y/N]
```

---

## Section 3: Progress Format

### Step Header

Every step starts with a header showing position in the flow:

```
Step N of 14: Step Name
```

There is one blank line before and after the header. No box-drawing characters or borders around step headers — keep it light.

### Sub-Step Progress

For operations that process multiple items, show a progress bar:

```
  Importing connections... 2,847/4,012 profiles
  [=========================>          ] 71%
```

The progress bar is 40 characters wide. Updates in place (carriage return). For terminals that do not support CR, falls back to periodic line updates:

```
  Importing connections... 1,000/4,012 profiles (25%)
  Importing connections... 2,000/4,012 profiles (50%)
  Importing connections... 3,000/4,012 profiles (75%)
  Importing connections... 4,012/4,012 profiles (100%)
```

### Time Estimates

Shown before long operations (embedding generation, seed download):

```
  Estimated time: ~5–15 minutes
```

During execution, show elapsed time after completion:

```
  Embedding generation complete (7m 23s)
```

### Cost Estimates

Shown before API-dependent operations:

```
  Estimated cost: ~$0.04 (one-time, via OpenAI Batch API)
```

After completion:

```
  Actual cost: $0.038 (4,012 profiles × ~500 tokens avg)
```

Cost is only shown for OpenAI embedding. All other steps are free.

---

## Section 4: Success Messages

Every step follows the Phase 3 operation result pattern: Progress → Summary → Gaps → Next steps → Report path. Not every step has gaps or next steps.

### Step 1: Prerequisites Detection

```
Step 1 of 14: Prerequisites Detection

  Platform:       Ubuntu 24.04 (x86_64)
  PostgreSQL:     16.2 — running on localhost:5432
  pgvector:       0.7.0 — available
  pg_trgm:        available
  Python:         3.12.3
  pip:            available
  venv module:    available
  Disk free:      45.2 GB (minimum: 2 GB, recommended: 5 GB)

  All prerequisites met.
```

### Step 2: System Setup

```
Step 2 of 14: System Setup

  ✓ PostgreSQL 16.2 installed and running
  ✓ pgvector extension enabled
  ✓ pg_trgm extension enabled
  ✓ Database user 'linkedout' created
  ✓ Database 'linkedout' created

  System setup complete (42s).
```

### Step 3: Database Setup

```
Step 3 of 14: Database Setup

  ✓ Database password generated
  ✓ ~/linkedout-data/config/config.yaml written
  ✓ 12 database migrations applied (1.8s)
  ✓ Schema verified: 10 tables present
  ✓ ~/linkedout-data/config/agent-context.env generated

  Database setup complete (3.2s).
```

### Step 4: Python Environment

```
Step 4 of 14: Python Environment

  ✓ Virtual environment created: .venv/
  ✓ 62 packages installed via uv (8.3s)
  ✓ CLI verified: linkedout v0.1.0

  Python environment ready (12.1s).
```

### Step 5: API Key Collection

```
Step 5 of 14: API Key Collection

  Embedding provider: OpenAI (text-embedding-3-small)
  ✓ OpenAI API key validated and saved
  ✓ Apify API key saved (optional — for Chrome extension)
  ✓ ~/linkedout-data/config/secrets.yaml written (chmod 600)

  API keys configured.
```

### Step 6: User Profile

```
Step 6 of 14: User Profile

  ✓ Profile created for linkedin.com/in/yourname
  ✓ Marked as affinity anchor

  User profile configured.
```

### Step 7: LinkedIn CSV Import

```
Step 7 of 14: LinkedIn CSV Import

  Source:    ~/Downloads/Connections.csv
  Imported:  3,847 new connections
  Skipped:   23 (already in database)
  Failed:    0

  Coverage:
    Companies matched:  3,691 / 3,847 (95.9%)
    Missing companies:  156 (will resolve after seed import)

  Report saved: ~/linkedout-data/reports/import-connections-20260407-143000.json
```

### Step 8: Contacts Import

If imported:

```
Step 8 of 14: Contacts Import

  Source:    ~/Downloads/contacts.csv (Google CSV)
  Imported:  1,247 contacts
  Matched:   892 against existing connections
  New:       355 contacts without LinkedIn match
  Skipped:   12 (duplicates)
  Failed:    0

  Report saved: ~/linkedout-data/reports/import-contacts-20260407-143200.json
```

If skipped:

```
Step 8 of 14: Contacts Import

  Skipped (you can import contacts later with: linkedout import-contacts)
```

### Step 9: Seed Data

```
Step 9 of 14: Seed Data

  Downloading core seed data...
  [========================================] 50.2 MB — done (12s)
  ✓ Checksum verified (SHA-256)

  Importing seed data...
    company:          5,012 imported
    company_alias:    8,347 imported
    role_alias:       2,847 imported
    funding_round:    12,456 imported
    startup_tracking: 3,891 imported
    growth_signal:    7,234 imported
    crawled_profile:  1,205 imported
    experience:       4,890 imported
    education:        2,100 imported
    profile_skill:    6,780 imported

  Seed data imported (18.4s).
  Report saved: ~/linkedout-data/reports/seed-import-20260407-143500.json
```

### Step 10: Embedding Generation

```
Step 10 of 14: Embedding Generation

  Provider:   OpenAI (text-embedding-3-small, Batch API)
  Profiles:   4,012 embedded
  Skipped:    0 (already had embeddings)
  Failed:     0
  Dimension:  1536
  Duration:   2m 18s
  Cost:       $0.038

  Report saved: ~/linkedout-data/reports/embed-20260407-144000.json
```

### Step 11: Affinity Computation

```
Step 11 of 14: Affinity Computation

  Connections scored: 3,870 / 3,870 (100%)

  Dunbar tier distribution:
    Inner circle (< 5):     12 connections
    Close (5–15):           38 connections
    Active (15–50):         187 connections
    Acquaintance (50–150):  892 connections
    Peripheral (150+):      2,741 connections

  Report saved: ~/linkedout-data/reports/compute-affinity-20260407-144200.json
```

### Step 12: Skill Installation

```
Step 12 of 14: Skill Installation

  ✓ Claude Code — 4 skills installed to ~/.claude/skills/linkedout/
  ✓ Codex — 4 skills installed to ~/.agents/skills/linkedout/

  Skills installed for 2 platforms.
```

### Steps 13 & 14: Readiness Check and Gap Repair

See Section 6 for the full readiness report format. See Section 2 (Prompt 14a–14c) for gap repair prompts.

---

## Section 5: Error Messages

Every error follows this structure:

```
  ✗ <What went wrong — one line, user-readable>

  <How to fix it — specific instructions>

  <How to retry>
```

### 5.1 Missing Prerequisite — Python Too Old

```
  ✗ Python 3.9.7 found, but LinkedOut requires Python 3.11 or newer.

  Install Python 3.11+:
    Ubuntu/Debian:  sudo apt install python3.11
    macOS:          brew install python@3.12
    Arch:           sudo pacman -S python
    Other:          https://www.python.org/downloads/

  After installing, re-run /linkedout-setup.
```

### 5.2 Missing Prerequisite — No PostgreSQL

```
  ✗ PostgreSQL is not installed.

  LinkedOut uses PostgreSQL with the pgvector extension for
  vector search. The setup script can install it for you.

  To install manually:
    Ubuntu/Debian:  sudo apt install postgresql postgresql-contrib
    macOS:          brew install postgresql@16
    Arch:           sudo pacman -S postgresql

  After installing, re-run /linkedout-setup.
```

### 5.3 Missing Prerequisite — No pgvector

```
  ✗ PostgreSQL 16.2 is installed, but the pgvector extension is missing.

  Install pgvector:
    Ubuntu/Debian:  sudo apt install postgresql-16-pgvector
    macOS:          brew install pgvector
    Arch:           yay -S pgvector (AUR)

  Then enable it:
    sudo -u postgres psql -d linkedout -c "CREATE EXTENSION IF NOT EXISTS vector;"

  Or let the system setup script handle it — re-run /linkedout-setup.
```

### 5.4 Wrong Python Version

```
  ✗ Python 3.10.12 found, but LinkedOut requires Python 3.11+.

  Python 3.11 introduced features LinkedOut depends on (ExceptionGroup,
  tomllib, TaskGroup improvements).

  Upgrade:
    Ubuntu/Debian:  sudo apt install python3.11 python3.11-venv
    macOS:          brew install python@3.12
    Arch:           sudo pacman -S python

  After upgrading, re-run /linkedout-setup.
```

### 5.5 Database Creation Failure — Permission Denied

```
  ✗ Database setup failed: permission denied for createdb.

  The PostgreSQL user 'linkedout' does not have permission to
  create databases. This usually means the system setup script
  did not complete successfully.

  Fix manually:
    sudo -u postgres createuser --createdb linkedout
    sudo -u postgres createdb --owner=linkedout linkedout

  Or re-run the system setup script:
    sudo bash scripts/system-setup.sh

  Then re-run /linkedout-setup.
```

### 5.6 Database Creation Failure — Port In Use

```
  ✗ Database setup failed: could not connect to localhost:5432.

  PostgreSQL may not be running, or another service is using port 5432.

  Check PostgreSQL status:
    sudo systemctl status postgresql     (Linux)
    brew services info postgresql@16     (macOS)

  Start PostgreSQL:
    sudo systemctl start postgresql      (Linux)
    brew services start postgresql@16    (macOS)

  If another service is using port 5432, stop it or configure
  LinkedOut to use a different port in ~/linkedout-data/config/config.yaml.

  Then re-run /linkedout-setup.
```

### 5.7 Network Error During Seed Download

```
  ✗ Seed data download failed: connection timed out.

  Could not reach GitHub to download seed data. Check your
  internet connection and try again.

  Retry:
    linkedout download-seed

  Manual download (if GitHub is blocked):
    Download the seed file from the GitHub Releases page and
    place it in ~/linkedout-data/seed/. Then run:
    linkedout import-seed

  Or re-run /linkedout-setup — it will resume from this step.
```

### 5.8 Invalid API Key — OpenAI

```
  ✗ OpenAI API key validation failed: 401 Unauthorized.

  The API key you entered was rejected by OpenAI. Common causes:
    - Key was copied incorrectly (check for trailing whitespace)
    - Key has been revoked or expired
    - Key belongs to an organization with no available credits

  Get a new key at: https://platform.openai.com/api-keys

  Options:
    [1] Enter a different key
    [2] Switch to local embeddings (free, no key needed)

  Choice [1/2]:
```

### 5.9 Invalid API Key — Apify

```
  ✗ Apify API key validation failed.

  The key you entered was rejected by Apify. Check that it is
  correct at: https://console.apify.com/account/integrations

  This key is optional — skip it? [Y/n]
```

### 5.10 CSV Parse Error

```
  ✗ Could not parse CSV file: ~/Downloads/Connections.csv

  The file does not appear to be a valid LinkedIn connections export.
  Expected columns: "First Name", "Last Name", "Email Address",
  "Company", "Position", "Connected On".

  Common causes:
    - Wrong file (this might be a different LinkedIn export)
    - File was modified after download
    - File encoding issue (expected UTF-8)

  LinkedIn export instructions:
    1. Go to linkedin.com/mypreferences/d/download-my-data
    2. Select only "Connections"
    3. Download and unzip the archive
    4. Use the "Connections.csv" file

  Enter a different file path, or re-run /linkedout-setup.
```

### 5.11 Embedding Failure — Model Download Failed

```
  ✗ Local embedding model download failed: connection timed out.

  Could not download nomic-embed-text-v1.5 (~275 MB).
  Check your internet connection and try again.

  Retry:
    linkedout embed --provider local

  If the download keeps failing, switch to OpenAI embeddings:
    Edit ~/linkedout-data/config/config.yaml:
      embedding_provider: openai
    Add your OpenAI key to ~/linkedout-data/config/secrets.yaml:
      openai_api_key: sk-...

  Then re-run /linkedout-setup.
```

### 5.12 Embedding Failure — OpenAI Rate Limit

```
  ✗ OpenAI embedding failed: rate limit exceeded (429 Too Many Requests).

  The Batch API rate limit was hit. This is temporary.

  Embedded so far: 2,847 / 4,012 profiles (progress saved).

  Retry — it will resume from where it left off:
    linkedout embed

  Or re-run /linkedout-setup — it will resume from this step.
```

### 5.13 Disk Space Insufficient

```
  ✗ Insufficient disk space.

  Available: 1.2 GB on the partition containing ~/linkedout-data/
  Required:  2 GB minimum (5 GB recommended for full seed data)

  Free up disk space and re-run /linkedout-setup.

  Tip: You can change the data directory to a partition with
  more space by setting LINKEDOUT_DATA_DIR before running setup:
    export LINKEDOUT_DATA_DIR=/path/to/bigger/disk/linkedout-data
```

---

## Section 6: Readiness Report Format

The readiness report is the final output of setup. It is always generated, even on re-runs. It is both printed to the terminal and saved as JSON.

### Console Output

```
╔══════════════════════════════════════════════════════╗
║            LinkedOut Setup — Readiness               ║
╚══════════════════════════════════════════════════════╝

  Data
  ────────────────────────────────────────────────────
  Profiles:        4,012 loaded
  Embeddings:      3,998 / 4,012 (99.7%)
  Companies:       52,000 loaded
  Company match:   3,691 / 3,847 connections (95.9%)
  Affinity:        3,870 / 3,870 connections scored (100%)

  Configuration
  ────────────────────────────────────────────────────
  Embedding:       OpenAI (text-embedding-3-small)
  Data directory:  ~/linkedout-data/
  Database:        postgresql://localhost:5432/linkedout
  OpenAI key:      configured
  Apify key:       not configured
  Agent context:   ~/linkedout-data/config/agent-context.env

  Skills
  ────────────────────────────────────────────────────
  Claude Code:     installed (4 skills)
  Codex:           installed (4 skills)
  Copilot:         not detected

  Extension
  ────────────────────────────────────────────────────
  Chrome extension: not installed (optional — run /linkedout-extension-setup)
  Backend server:   not running

  Gaps
  ────────────────────────────────────────────────────
  ⚠ 14 profiles without embeddings
  ⚠ 156 companies without aliases (will resolve on next seed update)

  Next Steps
  ────────────────────────────────────────────────────
  → Run `linkedout embed` to cover remaining 14 profiles
  → Try: /linkedout "who do I know at Stripe?"
  → Try: /linkedout "find me warm intros to Series B AI startups"
  → Install the Chrome extension for passive profile enrichment

Report saved: ~/linkedout-data/reports/setup-readiness-20260407-143000.json
```

### Zero-Gap Variant

When setup is fully complete with no gaps:

```
╔══════════════════════════════════════════════════════╗
║            LinkedOut Setup — Readiness               ║
╚══════════════════════════════════════════════════════╝

  Data
  ────────────────────────────────────────────────────
  Profiles:        4,012 loaded
  Embeddings:      4,012 / 4,012 (100%)
  Companies:       52,000 loaded
  Company match:   3,847 / 3,847 connections (100%)
  Affinity:        3,870 / 3,870 connections scored (100%)

  Configuration
  ────────────────────────────────────────────────────
  Embedding:       Local (nomic-embed-text-v1.5, 768d)
  Data directory:  ~/linkedout-data/
  Database:        postgresql://localhost:5432/linkedout
  OpenAI key:      not configured
  Apify key:       not configured
  Agent context:   ~/linkedout-data/config/agent-context.env

  Skills
  ────────────────────────────────────────────────────
  Claude Code:     installed (4 skills)

  No gaps found. Your network is fully indexed.

  Get Started
  ────────────────────────────────────────────────────
  → Try: /linkedout "who do I know at Stripe?"
  → Try: /linkedout "find me warm intros to Series B AI startups"
  → Try: /linkedout "who in my network works in climate tech?"
  → Install the Chrome extension for passive profile enrichment

Report saved: ~/linkedout-data/reports/setup-readiness-20260407-143000.json
```

### JSON Report

The JSON report saved to disk contains all data in machine-readable form. See the phase plan (9M section) for the full JSON schema. The console output above is derived from this JSON — the JSON is the source of truth.

---

## Section 7: Diagnostic Report Format

When setup fails at any step, a diagnostic report is automatically written to `~/linkedout-data/logs/setup-diagnostic-YYYYMMDD-HHMMSS.txt`. This file is designed to be attached to a GitHub issue for remote debugging.

### Diagnostic File Contents

```
================================================================================
LinkedOut Setup Diagnostic Report
Generated: 2026-04-07 14:35:42 UTC
================================================================================

SYSTEM
------
OS:               Ubuntu 24.04.1 LTS (x86_64)
Kernel:           6.8.0-45-generic
Python:           3.12.3 (/usr/bin/python3)
PostgreSQL:       16.2
pgvector:         0.7.0
pg_trgm:          available
Disk free:        45.2 GB (on /home)
RAM:              15.6 GB total, 8.2 GB available
LinkedOut:        v0.1.0

CONFIGURATION (secrets redacted)
--------------------------------
Data directory:       ~/linkedout-data/
Config file:          ~/linkedout-data/config/config.yaml (exists)
Secrets file:         ~/linkedout-data/config/secrets.yaml (exists, chmod 600)
Agent context:        ~/linkedout-data/config/agent-context.env (exists)
Embedding provider:   openai
Database URL:         postgresql://linkedout:****@localhost:5432/linkedout
OpenAI API key:       configured (sk-...XXXX)
Apify API key:        not configured

SETUP PROGRESS
--------------
  ✓ Step  1: Prerequisites Detection         2026-04-07 14:20:01 (0.8s)
  ✓ Step  2: System Setup                    2026-04-07 14:20:45 (42s)
  ✓ Step  3: Database Setup                  2026-04-07 14:21:30 (3.2s)
  ✓ Step  4: Python Environment              2026-04-07 14:21:50 (12.1s)
  ✓ Step  5: API Key Collection              2026-04-07 14:23:10 (user input)
  ✓ Step  6: User Profile                    2026-04-07 14:24:00 (0.3s)
  ✓ Step  7: LinkedIn CSV Import             2026-04-07 14:25:15 (14.8s)
  ✓ Step  8: Contacts Import                 skipped (user declined)
  ✓ Step  9: Seed Data                       2026-04-07 14:26:30 (18.4s)
  ✗ Step 10: Embedding Generation            FAILED at 2026-04-07 14:35:42

FAILURE DETAILS
---------------
Step:      10 — Embedding Generation
Command:   linkedout embed --provider openai
Exit code: 1
Error:     openai.RateLimitError: 429 Too Many Requests

Traceback (most recent call last):
  File "/home/user/linkedout-oss/backend/src/linkedout/setup/embeddings.py", line 87, in generate
    result = await provider.embed_batch(texts, batch_size=100)
  File "/home/user/linkedout-oss/backend/src/linkedout/embedding/openai_provider.py", line 45, in embed_batch
    response = await self.client.embeddings.create(input=batch, model=self.model)
  ...
openai.RateLimitError: Error code: 429 - Rate limit exceeded. Please retry after 60s.

Progress at failure: 2,847 / 4,012 profiles embedded (progress saved)

RECENT LOG ENTRIES (last 50 lines of ~/linkedout-data/logs/setup.log)
---------------------------------------------------------------------
2026-04-07 14:35:00.123 | INFO     | setup.embeddings:generate:70 | Embedding batch 29/41 complete (100 profiles, 3.2s)
2026-04-07 14:35:03.456 | INFO     | setup.embeddings:generate:70 | Embedding batch 30/41 complete (100 profiles, 3.1s)
2026-04-07 14:35:06.789 | WARNING  | setup.embeddings:generate:78 | Rate limit warning: 3 retries remaining
2026-04-07 14:35:42.012 | ERROR    | setup.embeddings:generate:85 | Embedding generation failed: 429 Too Many Requests
2026-04-07 14:35:42.015 | ERROR    | setup.orchestrator:run:120 | Step 10 failed: openai.RateLimitError
2026-04-07 14:35:42.020 | INFO     | setup.orchestrator:run:125 | Writing diagnostic report

================================================================================
To report this issue:
  linkedout report-issue

Or file manually at:
  https://github.com/{owner}/linkedout-oss/issues/new

Attach this file: ~/linkedout-data/logs/setup-diagnostic-20260407-143542.txt
================================================================================
```

### What Is Always Redacted

- Full database password (shown as `****`)
- Full API keys (shown as `sk-...XXXX` — first 3 + last 4 chars)
- LinkedIn profile URLs of connections (only the user's own URL, if present)
- Email addresses and phone numbers
- File paths containing the username are kept (needed for debugging)

### What Is Never Included

- Contents of `secrets.yaml`
- Database row data
- Connection names or personal data
- Full API responses

---

## Section 8: Idempotency Behavior

When running `/linkedout-setup` on a system where setup has already completed, the flow becomes a fast health check.

### Re-Run Output

```
Step 1 of 14: Prerequisites Detection
  ✓ Already complete — all prerequisites met (skipping)

Step 2 of 14: System Setup
  ✓ Already complete — PostgreSQL 16.2 with pgvector (skipping)

Step 3 of 14: Database Setup
  ✓ Already complete — config exists, checking migrations...
  ✓ Database up to date (12 migrations applied)

Step 4 of 14: Python Environment
  ✓ Already complete — .venv/ exists, linkedout v0.1.0 (skipping)
  ✓ Checking for new dependencies... none found

Step 5 of 14: API Key Collection
  ✓ Already complete — OpenAI key configured, Apify key configured (skipping)

Step 6 of 14: User Profile
  ✓ Already complete — profile exists for linkedin.com/in/yourname (skipping)

Step 7 of 14: LinkedIn CSV Import
  ✓ Already complete — 3,847 connections in database (skipping)

Step 8 of 14: Contacts Import
  ✓ Already complete — 1,247 contacts in database (skipping)

Step 9 of 14: Seed Data
  ✓ Already complete — core seed imported (skipping)

Step 10 of 14: Embedding Generation
  ✓ Already complete — 4,012 / 4,012 profiles embedded (skipping)

Step 11 of 14: Affinity Computation
  ✓ Already complete — 3,870 connections scored (skipping)

Step 12 of 14: Skill Installation
  ✓ Already complete — skills installed for Claude Code, Codex (skipping)

Step 13 of 14: Readiness Check
  [always runs — generating fresh readiness report]

╔══════════════════════════════════════════════════════╗
║            LinkedOut Setup — Readiness               ║
╚══════════════════════════════════════════════════════╝
  ...

Step 14 of 14: Gap Detection
  No gaps found. Your network is fully indexed.

Setup check complete (2.1s). Everything looks good.
```

### Always-Run Steps on Re-Run

These steps always execute, even on a fully set-up system:

| Step | Why |
|------|-----|
| 3. Database Setup — migration check only | New migrations may exist after a `git pull` or version upgrade |
| 4. Python Environment — dependency check only | New pip packages may exist after upgrade |
| 13. Readiness Check | Always produces a fresh readiness report |
| 14. Gap Detection | Always scans for gaps, even if previously clean |

### Gap Detection on Re-Run

Even on a "complete" system, gaps can appear over time:
- New profiles imported via extension but not yet embedded
- New connections without affinity scores
- Config changes (e.g., switched embedding provider)

The gap detection step catches these and offers repairs.

### Data Safety

Re-running setup never:
- Regenerates the database password (keeps existing)
- Drops or truncates tables
- Deletes any imported data
- Overwrites API keys (offers to keep or replace)
- Re-downloads seed data (unless checksum mismatch or `--full` upgrade)

---

## Section 9: Skip/Resume Behavior

### State Tracking

Setup progress is tracked in `~/linkedout-data/state/setup-state.json`:

```json
{
  "steps_completed": {
    "prerequisites": "2026-04-07T14:20:01Z",
    "system_setup": "2026-04-07T14:20:45Z",
    "database": "2026-04-07T14:21:30Z",
    "python_env": "2026-04-07T14:21:50Z",
    "api_keys": "2026-04-07T14:23:10Z",
    "user_profile": "2026-04-07T14:24:00Z",
    "csv_import": "2026-04-07T14:25:15Z",
    "contacts_import": null,
    "seed_data": "2026-04-07T14:26:30Z",
    "embeddings": null,
    "affinity": null,
    "skill_install": null,
    "readiness": null,
    "gap_repair": null
  },
  "setup_version": "0.1.0",
  "last_run": "2026-04-07T14:35:42Z",
  "last_failure": {
    "step": "embeddings",
    "error": "openai.RateLimitError: 429 Too Many Requests",
    "timestamp": "2026-04-07T14:35:42Z"
  }
}
```

A `null` value means the step has not completed. User-declined steps (like contacts import) are recorded with a `"skipped"` string value instead of a timestamp.

### Resume After Interruption

When setup is interrupted (Ctrl+C, terminal closed, system crash), the next run resumes from where it left off:

```
Resuming setup from step 10 (Embedding Generation)...

Step 1 of 14: Prerequisites Detection
  ✓ Already complete (skipping)

Step 2 of 14: System Setup
  ✓ Already complete (skipping)

...

Step 9 of 14: Seed Data
  ✓ Already complete (skipping)

Step 10 of 14: Embedding Generation
  Resuming from checkpoint: 2,847 / 4,012 profiles embedded
  ...
```

### Mid-Step Interruption

If setup is interrupted during a step:

| Step | Recovery Behavior |
|------|-------------------|
| 2. System Setup | Re-runs the sudo script (idempotent) |
| 3. Database Setup | Re-runs migrations (idempotent — Alembic tracks applied migrations) |
| 4. Python Environment | Re-creates venv if corrupt, re-installs packages |
| 7. LinkedIn CSV Import | Re-runs import (idempotent — deduplicates by LinkedIn URL) |
| 8. Contacts Import | Re-runs import (idempotent — deduplicates by email/phone) |
| 9. Seed Data | Re-downloads if checksum mismatch, re-imports (idempotent — upsert) |
| 10. Embeddings | Resumes from checkpoint (`~/linkedout-data/state/embedding_progress.json`) |
| 11. Affinity | Re-runs (only scores unscored connections) |
| 12. Skills | Re-generates and re-installs (overwrites existing) |

### Skippable vs. Always-Run Steps

| Step | On Resume | On Re-Run (complete system) |
|------|-----------|----------------------------|
| 1. Prerequisites | Skip if passed | Skip (just validate) |
| 2. System Setup | Skip if passed | Skip |
| 3. Database Setup | Re-run migrations only | Re-run migrations only |
| 4. Python Environment | Skip if .venv valid | Check for new deps |
| 5. API Keys | Skip if keys exist | Skip (offer to replace) |
| 6. User Profile | Skip if profile exists | Skip |
| 7. CSV Import | Skip if imported | Skip |
| 8. Contacts Import | Skip if imported or declined | Skip |
| 9. Seed Data | Skip if imported | Skip |
| 10. Embeddings | Resume from checkpoint | Skip if all embedded |
| 11. Affinity | Skip if all scored | Skip if all scored |
| 12. Skills | Skip if installed | Skip (update on version change) |
| 13. Readiness | Always run | Always run |
| 14. Gap Repair | Always run | Always run |

### Version-Aware Re-Runs

The `setup_version` field in state tracks which version of LinkedOut ran setup. When the version changes (after `git pull` or upgrade):

```
Setup was last run with LinkedOut v0.1.0. Current version: v0.2.0.

Checking for required updates...
  ✓ Step  3: New database migrations found — will apply
  ✓ Step  4: New dependencies found — will install
  ✓ Step 12: Updated skill templates — will reinstall

Running required updates...
```

Only steps affected by the version change are re-run. Steps that check underlying state (migrations, dependencies, skills) detect changes automatically. Steps that are purely data-driven (CSV import, seed import, embeddings) are not re-run unless the user explicitly requests it.

---

## Appendix: Design Decisions and Judgment Calls

### A. No ANSI Colors

All output is plain text. The setup flow runs inside a skill context where terminal capabilities vary. Checkmarks (✓), crosses (✗), and warning symbols (⚠) are used instead of color for status indication. Box-drawing characters (╔═╗║╚═╝──) are used only for the readiness report header.

### B. Default Choices

- Embedding provider defaults to OpenAI (faster, negligible cost for typical networks)
- Seed data defaults to core (~50 MB) rather than full (~500 MB)
- Contacts import defaults to skip (N)
- All confirmations for required steps default to yes (Y)
- Re-embed on provider mismatch defaults to no (N) — it is a potentially long operation

### C. Cost Transparency

OpenAI embedding costs are shown both as estimates (before) and actuals (after). The estimates use real OpenAI Batch API pricing for text-embedding-3-small ($0.01 per 1M tokens) with an average of ~500 tokens per profile. Users are never surprised by costs.

### D. Progressive Disclosure

The setup flow does not dump all 14 steps upfront. Each step is shown as it begins. The step header (`Step N of 14: Name`) provides orientation without overwhelming the user with a preview of everything that will happen.

### E. Embedding Provider Cost Math

For reference, the cost estimates in this document are based on:

- **OpenAI text-embedding-3-small Batch API**: $0.01 per 1M tokens
- Average LinkedIn profile text (name, headline, company, summary, experiences): ~500 tokens
- 4,000 profiles × 500 tokens = 2M tokens = **$0.02** (batch pricing)
- Displayed as "~$0.04" to account for variance and seed data profiles (conservative estimate)

- **Local nomic-embed-text-v1.5**: Free, ~275 MB model download
- On a 4-core CPU laptop: ~15–30 profiles/second
- 4,000 profiles / 20 profiles/sec = ~200 seconds ≈ **3–4 minutes**
- Displayed as "~5–15 minutes" to account for slower hardware and seed data

### F. The Skill Is the Interface

This setup flow runs as a Claude Code / Codex / Copilot skill, not as a standalone CLI command. The "user" is a developer chatting with their AI assistant. All prompts are written as text the skill outputs, and all user responses come through the natural language interface. There is no `linkedout setup` CLI command — only the `/linkedout-setup` skill.
