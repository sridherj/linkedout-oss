---
feature: demo-mode
module: backend/src/linkedout/demo
linked_files:
  - backend/src/linkedout/demo/__init__.py
  - backend/src/linkedout/demo/db_utils.py
  - backend/src/linkedout/demo/sample_queries.py
  - backend/src/linkedout/commands/download_demo.py
  - backend/src/linkedout/commands/restore_demo.py
  - backend/src/linkedout/commands/reset_demo.py
  - backend/src/linkedout/commands/use_real_db.py
  - backend/src/linkedout/commands/demo_help.py
  - backend/src/linkedout/setup/demo_offer.py
  - backend/src/linkedout/commands/status.py
  - backend/src/linkedout/cli.py
  - scripts/generate-demo-dump.py
  - scripts/demo-manifest-template.json
version: 1
last_verified: "2026-04-09"
---

# Demo Mode

**Created:** 2026-04-09 -- Written from scratch for LinkedOut OSS

## Intent

Provide a zero-config onboarding experience where new users can explore LinkedOut's search, affinity scoring, and AI agent capabilities using pre-populated demo data before importing their own connections. Demo mode uses a separate PostgreSQL database (`linkedout_demo`) for complete isolation -- the user's real database is never modified during demo use.

## Behaviors

### Demo Database Concept

- **Separate database isolation**: Demo mode uses a dedicated PostgreSQL database named `linkedout_demo`, created alongside the user's real `linkedout` database on the same cluster. Both databases coexist -- switching between them never drops the other. This avoids the complexity of in-DB markers, CASCADE deletes, or "mixed data" bugs.

- **Demo data contents**: The demo database is a `pg_dump` file containing ~2,000 anonymized profiles with stratified sampling by seniority, function area, and country. It includes profiles, experiences, education, skills, connections, company data, pre-computed embeddings, and affinity scores. Profile data ships only via the demo pipeline (not via seed data).

- **Demo user profile**: The demo system user is a composite Founder/CTO at a Bengaluru-based AI startup ("Alex Chen") with 8 years of experience in ML, product management, and data engineering. The profile is defined in `scripts/generate-demo-dump.py` as `DEMO_USER_PROFILE` with specific skills (`Machine Learning`, `Product Management`, `Data Engineering`, `Distributed Systems`, `Python`, `Leadership`, `System Design`, `PostgreSQL`), 3 experiences, and 1 education entry (IIT Bombay). Affinity scores in the demo are relative to this profile, which is why ML engineers and senior ICs tend to score highest.

- **Config flag**: Demo mode is tracked as `demo_mode: bool` in `settings.py` (default `False`) and persisted to `config.yaml`. The `is_demo_mode()` function in `linkedout.demo.__init__` reads this setting.

### Download Flow

- **Command**: `linkedout download-demo [--version TAG] [--force]`

- **Source**: GitHub Releases on `sridherj/linkedout-oss` with tag `demo-v1` (configurable via `--version`). The base URL can be overridden with the `LINKEDOUT_DEMO_URL` environment variable for forks.

- **Manifest**: Downloads `demo-manifest.json` from the release, which contains `name`, `sha256`, and `size_bytes` fields. The manifest is validated for required fields before proceeding.

- **Download mechanics**: Stream-downloads the dump file with a `tqdm` progress bar (8192-byte chunks), writing to a `.tmp` file first and renaming on success. Supports `GITHUB_TOKEN` for authenticated requests.

- **Caching**: Downloaded file is stored at `~/linkedout-data/cache/demo-seed.dump`. If the file already exists and its SHA256 checksum matches the manifest, the download is skipped (unless `--force` is passed). A mismatched checksum triggers re-download.

- **Checksum verification**: Uses `shared.utils.checksum.verify_checksum()` for SHA256 verification after download. On failure, the file is deleted and an error is raised.

### Restore Flow

- **Command**: `linkedout restore-demo`

- **Prerequisites**: Requires `pg_restore` on PATH and a previously downloaded dump file at `~/linkedout-data/cache/demo-seed.dump`.

- **Database creation**: Connects to the `postgres` maintenance database and runs `DROP DATABASE IF EXISTS "linkedout_demo"` followed by `CREATE DATABASE "linkedout_demo"`. Then enables `pgvector` extension in the new database. This makes the command idempotent -- safe to re-run.

- **Restore**: Runs `pg_restore --dbname=<url> --clean --if-exists --no-owner` against the dump file. Exit code 1 (warnings) is tolerated; only exit code 2+ is treated as failure. Timeout is 300 seconds.

- **Post-restore config**: Calls `set_demo_mode(data_dir, enabled=True)` which atomically updates `config.yaml` to set `demo_mode: true` and rewrites `database_url` to point at `linkedout_demo`. Uses tempfile + `os.replace()` for atomic writes.

- **Agent context**: Regenerates `agent-context.env` with the demo database URL so AI agents connect to the correct database.

- **Summary output**: After restore, prints record counts (profiles, companies, connections) queried from the demo database via `get_demo_stats()`, then displays the demo user profile description and sample queries.

### Reset Flow

- **Command**: `linkedout reset-demo [-y/--yes]`

- **Guard**: Only runs when already in demo mode (`is_demo_mode()` check). Prompts for confirmation unless `--yes` is passed.

- **Mechanics**: Drops and re-creates the demo database, then re-restores from the cached dump file. Does not re-download -- uses the existing `~/linkedout-data/cache/demo-seed.dump`. This provides instant reset for experimentation.

- **Output**: Prints record counts after reset.

### Switch to Real Database

- **Command**: `linkedout use-real-db [--drop-demo]`

- **Guard**: No-ops with "Already using real database" if not currently in demo mode.

- **Config update**: Calls `set_demo_mode(data_dir, enabled=False)` which sets `demo_mode: false` and rewrites `database_url` to point at `/linkedout` (the non-demo database name).

- **Optional cleanup**: With `--drop-demo`, drops the `linkedout_demo` database. Without it, the demo database remains available for later `restore-demo`.

- **Agent context**: Regenerates `agent-context.env` with the real database URL.

### Demo Help

- **Command**: `linkedout demo-help`

- **Output**: Displays the demo user profile description and 3 curated sample queries. No guards or side effects.

### Sample Queries

- **Three categories**: Defined in `sample_queries.py` as the `SAMPLE_QUERIES` list:
  1. **Semantic Search**: "Who in my network has experience with distributed systems at a Series B startup?" -- demonstrates intent-based search beyond keyword matching.
  2. **Affinity & Relationships**: "Who are my strongest connections in ML?" -- demonstrates affinity scoring with shared skills and company overlap.
  3. **AI Agent**: "Compare the top 3 data scientists in my network for a founding engineer role" -- demonstrates multi-profile synthesis and reasoning.

- **Each query includes**: category, title, query text, explanation of what it demonstrates, and 2 suggested follow-up queries.

- **Usage context**: Sample queries are labeled "Use these with the /linkedout skill in Claude Code or Codex".

### Demo Status Indicator

- **Status command**: `linkedout status` includes demo mode in its output. In text mode, the title shows `LinkedOut v<version> [DEMO]` and the DB label shows `DB: linkedout_demo (demo)`. In JSON mode, `demo_mode` and `database_name` are included as top-level fields.

- **Demo nudge**: A `result_callback` on the root CLI group appends "Demo mode . linkedout setup to use your own data" after every command while demo mode is active. This runs after every command, not just demo-related ones.

### Setup Integration

- **Demo offer**: During `linkedout setup`, after the first 4 infrastructure steps complete, `offer_demo()` presents a decision gate with ASCII art prompt showing "~375 MB total download (demo data + search model)" and `[Y] Try the demo / [n] Skip to full setup`. Default is yes (empty input = accept).

- **Demo setup steps (D1-D5)**:
  1. **D1**: Download demo data (reuses `download_demo` internals).
  2. **D2**: Download local embedding model via `pre_download_model("local")`. Non-fatal on failure.
  3. **D3**: Restore demo database (reuses `create_demo_database` + `restore_demo_dump`). Also sets `embedding_provider` to `"local"` in config.yaml.
  4. **D4**: Install skills with `auto_accept=True`. Non-fatal on failure.
  5. **D5**: Run readiness check against demo database. Non-fatal on failure.

- **Transition offer**: When `linkedout setup` is run while already in demo mode, `offer_transition()` asks "Ready to set up with your own connections? [Y/n]" instead of re-running demo setup.

### Demo Dump Generation (Maintainer-Only)

- **Script**: `scripts/generate-demo-dump.py` -- connects to production PostgreSQL (read-only), samples ~2,000 profiles with stratified sampling, anonymizes PII using Faker with locale matching (`en_IN`, `en_US`, `en_GB`, etc.), creates a temporary database `linkedout_demo_gen`, inserts anonymized data, and produces a `pg_dump` file.

- **Anonymization**: Names are replaced with locale-appropriate Faker names (seeded by index for reproducibility). LinkedIn URLs become `demo-user-NNNN`. Headlines are reconstructed from position + company. About sections are generic summaries. Counts get +/-20% jitter. Location, company, seniority, and function area are preserved (not PII).

- **Manifest template**: `scripts/demo-manifest-template.json` provides the structure (`version: "demo-v1"`, `tier: "demo"`) with placeholder SHA256 and size fields filled after dump generation.

## Decisions

- **Separate database over in-DB markers**: Demo data lives in a completely separate PostgreSQL database rather than being marked with flags in the real database. This eliminates CASCADE delete complexity, data_source markers, import hooks, and the entire class of "mixed data" bugs. Both databases coexist so switching is non-destructive.

- **pg_dump/pg_restore over SQL scripts**: The demo ships as a binary `pg_dump` custom-format file rather than SQL INSERT scripts. This preserves binary data (embeddings), handles schema creation, and is significantly faster for ~2,000 profiles worth of data.

- **Anonymized real data over synthetic**: Demo profiles are sampled from real production data and anonymized rather than being fully synthetic. This preserves realistic distributions of seniority levels, function areas, company patterns, and location spread that would be difficult to generate synthetically.

- **Local embedding provider for demo**: Demo setup sets `embedding_provider` to `"local"` (nomic) to avoid requiring an OpenAI API key for first-time demo exploration.

## Not Included

- **Demo data migration to real DB**: There is no path to migrate demo profiles into the real database. Demo mode is explore-only; users start fresh with their own data via `linkedout setup`.

- **Partial demo restore**: The restore is all-or-nothing. There is no way to restore only specific tables or a subset of profiles.

- **Demo data versioning/upgrades**: No mechanism to detect that a newer demo dump is available and suggest upgrading. Users would need to `download-demo --force` followed by `restore-demo`.

- **Multi-user demo profiles**: The demo has exactly one demo user identity (Alex Chen). There is no way to switch the reference profile for affinity scoring.
