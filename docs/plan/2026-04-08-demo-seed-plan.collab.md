# Demo Seed Experience: CLI Integration & Dump Generation

## Overview

Deliver a zero-effort demo mode for LinkedOut OSS so new users can experience semantic
search, affinity scoring, and the AI agent shortly after cloning the repo. The approach
uses a separate Postgres database (`linkedout_demo`) restored from a pre-built `pg_dump`
file hosted as a GitHub Release asset (~100 MB dump + ~275 MB embedding model = ~375 MB
total download). The generation pipeline anonymizes 2,000 profiles from SJ's production
database, re-embeds them with the local nomic model, computes affinity, and produces the
dump. The CLI integration adds a demo offer after setup step 4, demo-specific D1-D5 steps,
nudge footers, sample queries, and reset/transition flows.

**Spec reference:** `backend/docs/specs/onboarding-experience.md` is the source of truth
for user-facing behavior. This plan implements that spec.

## Operating Mode

**HOLD SCOPE** -- Requirements are specific and fully resolved (0 open unknowns, high
confidence across all dimensions). No signals for expansion or reduction. Every sub-phase
adheres strictly to the stated requirements.

---

## Sub-phase 1: Demo Infrastructure & Config Plumbing

**Outcome:** The application can detect, switch between, and persist which database mode
it's in (demo vs real). A `demo_mode` flag exists in config, the `linkedout_demo` database
name is a constant, and all downstream code can ask "am I in demo mode?" without touching
the orchestrator or CLI yet.

**Dependencies:** None

**Estimated effort:** 1 session (~3 hours)

**Verification:**
- `LinkedOutSettings` has a `demo_mode: bool` field defaulting to `False`
- `config.yaml` written by setup includes `demo_mode: false`
- `get_config().demo_mode` returns the correct value based on config
- Unit test: settings parse `demo_mode: true` from YAML correctly
- The constant `DEMO_DB_NAME = "linkedout_demo"` exists in a shared location

Key activities:

- Add `demo_mode: bool = Field(default=False)` to `LinkedOutSettings` in
  `backend/src/shared/config/settings.py`. Add it in the "Core" section next to
  `database_url`. No validation needed -- it's a simple boolean.

- Add `DEMO_DB_NAME = "linkedout_demo"` constant to a new file
  `backend/src/linkedout/demo/__init__.py`. This becomes the single source of truth for
  the demo database name. Also add `DEMO_CACHE_DIR = "cache"` and
  `DEMO_DUMP_FILENAME = "demo-seed.dump"` constants.

- Add a `demo_mode` line to `_CONFIG_YAML_TEMPLATE` in
  `backend/src/linkedout/setup/database.py`:
  ```
  demo_mode: false          # true when using demo database
  ```

- Create a helper function `is_demo_mode()` in `backend/src/linkedout/demo/__init__.py`
  that reads from config and returns the boolean. This is the canonical check all code uses.

- Create a helper `get_demo_db_url(base_url: str) -> str` that takes a database URL and
  replaces the database name with `linkedout_demo`. Uses simple string replacement on the
  URL path component.

- Create a helper `set_demo_mode(data_dir: Path, enabled: bool)` that reads config.yaml,
  sets `demo_mode`, and writes it back. Also updates `database_url` to point at
  `linkedout_demo` or `linkedout` accordingly. Uses atomic write (tempfile + rename).

- Write tests in `backend/tests/unit/test_demo_config.py`:
  - `test_demo_mode_default_false`
  - `test_demo_mode_from_yaml`
  - `test_get_demo_db_url`
  - `test_set_demo_mode_toggles_config`

**Design review:**
- Naming: `demo_mode` follows the `snake_case` boolean pattern used by `auto_upgrade`,
  `debug`, `langfuse_enabled` in the same settings class. Consistent.
- Architecture: Adding to `LinkedOutSettings` means it participates in the standard
  config resolution chain (env > .env > secrets.yaml > config.yaml > defaults). A user
  could override with `LINKEDOUT_DEMO_MODE=true` env var if needed. Consistent with
  existing patterns.
- Config write-back: `set_demo_mode` modifies config.yaml, which is the same pattern used
  by `write_config_yaml` in database.py. The atomic write pattern (tempfile + rename) is
  already used by `save_setup_state`. Consistent.

---

## Sub-phase 2: Demo Download & Restore Commands

**Outcome:** Two new CLI commands exist: `linkedout download-demo` downloads the demo dump
from GitHub Releases to `~/linkedout-data/cache/demo-seed.dump`, and
`linkedout restore-demo` creates the `linkedout_demo` database and restores the dump into
it. Both are idempotent. The download command supports `--force` for re-download.

**Dependencies:** Sub-phase 1 (needs demo constants and config helpers)

**Estimated effort:** 2 sessions (~6 hours)

**Verification:**
- `linkedout download-demo` downloads a file to `~/linkedout-data/cache/demo-seed.dump`
  (or skips if cached and checksum matches)
- `linkedout download-demo --force` re-downloads even if cached
- `linkedout restore-demo` creates `linkedout_demo` DB if not exists, runs `pg_restore`
- `linkedout restore-demo` is idempotent (drop + recreate on repeat)
- After restore, `psql linkedout_demo -c "SELECT count(*) FROM crawled_profile"` returns
  the expected count
- Config is updated to `demo_mode: true` and `database_url` points to `linkedout_demo`
- `agent-context.env` is regenerated with the demo database URL
- Both commands registered in `cli.py` and appear in `linkedout --help`

Key activities:

- Create `backend/src/linkedout/commands/download_demo.py`:
  - Click command `download-demo` with `--force` and `--version` options
  - Reuse patterns from `download_seed.py`: GitHub Release URL resolution, manifest
    fetching, checksum verification, progress bar download
  - The demo dump is a separate GitHub Release asset (tag: `demo-v1` or similar) with
    its own manifest (`demo-manifest.json`) containing `{name, sha256, size_bytes}`
  - Cache location: `~/linkedout-data/cache/demo-seed.dump` (not `seed/` -- demo is
    separate from seed data)
  - On success: print cache location and next step hint ("Run `linkedout restore-demo`")
  - Constants: `DEMO_RELEASE_TAG = "demo-v1"`,
    `DEMO_REPO = "sridherj/linkedout-oss"` (same repo, different release tag)

- Create `backend/src/linkedout/commands/restore_demo.py`:
  - Click command `restore-demo`
  - Check that `~/linkedout-data/cache/demo-seed.dump` exists (error with helpful message
    if not: "Run `linkedout download-demo` first")
  - Read current `database_url` from config to extract host/port/user/password
  - Create database: `CREATE DATABASE linkedout_demo` via psql (handle "already exists"
    gracefully: `DROP DATABASE IF EXISTS linkedout_demo` then create)
  - Enable pgvector: `CREATE EXTENSION IF NOT EXISTS vector` in the new DB
  - Run `pg_restore --dbname=linkedout_demo --clean --if-exists --no-owner` on the dump
  - Call `set_demo_mode(data_dir, enabled=True)` to update config
  - Regenerate `agent-context.env` with the demo database URL
  - Print success: profile count, company count, sample query suggestion
  - Print the demo user profile explanation (founder/CTO composite)

- Register both commands in `backend/src/linkedout/cli.py` under a new `# --- Demo ---`
  section.

- Create `backend/src/linkedout/demo/db_utils.py` with shared helpers:
  - `create_demo_database(db_url: str) -> str`: creates `linkedout_demo`, returns its URL
  - `drop_demo_database(db_url: str) -> bool`: drops `linkedout_demo` if it exists
  - `restore_demo_dump(demo_db_url: str, dump_path: Path) -> bool`: runs pg_restore
  - `get_demo_stats(demo_db_url: str) -> dict`: queries profile/company/connection counts
  - `check_pg_restore() -> bool`: verifies `pg_restore` is available on the system
  - All functions use `subprocess.run` with `psql`/`pg_restore` -- matching the pattern
    in `database.py` and `reset_db.py`

- Update `backend/src/linkedout/setup/prerequisites.py`:
  - Add `pg_restore` availability check alongside existing `psql` check
  - `pg_restore` ships with the PostgreSQL client package (same as `psql`)
  - If `psql` exists but `pg_restore` is missing, add to blockers list

- Write tests:
  - Unit: `test_download_demo.py` -- mock HTTP, test cache hit/miss/force logic
  - Integration: `test_restore_demo.py` -- requires a running Postgres (skip in CI if
    unavailable). Test create/drop/restore cycle.

**Design review:**
- Naming: `download-demo` and `restore-demo` follow the `verb-noun` pattern used by
  `download-seed`, `import-seed`, `compute-affinity`, `reset-db`. Consistent.
- Error paths: What if `pg_restore` fails partway? The `--clean --if-exists` flags mean
  partial restores can be re-run. The `DROP DATABASE IF EXISTS` before create ensures
  a clean slate. No rollback needed -- the user just re-runs.
- Security: The demo database URL uses the same credentials as the main database (same
  Postgres user `linkedout`). The user already trusts this user with their real data,
  so no escalation. The dump file is downloaded over HTTPS from GitHub.
- Naming convention note: Considered `linkedout demo download` / `linkedout demo restore`
  as a subcommand group, but the existing CLI is flat (no subgroups except `config`). Flat
  commands with `demo` in the name are more discoverable and consistent.

---

## Sub-phase 3: Orchestrator Integration & Demo Fork

**Outcome:** When a user runs `linkedout setup`, after step 4 (Python Env) completes,
they see a prompt offering to load demo data. Steps 1-4 are common infrastructure for
ALL users. If the user accepts, setup runs demo-specific steps D1-D5 (download dump,
download embedding model, restore DB, install skills, readiness check) with their own
numbering — no "Step 12 of 14" leaking through. If they decline, setup continues with
steps 5-14 as normal.

**Dependencies:** Sub-phase 2 (needs download/restore commands)

**Estimated effort:** 2 sessions (~6 hours)

**Verification:**
- Fresh setup: after step 4, user sees the demo offer prompt
- Steps 1-4 show "Step N of 4" (not "of 14") when demo path is taken
- Accepting demo: D1-D5 execute with demo-specific labels
- Declining demo: steps 5-14 run as normal (steps show "Step N of 14")
- Re-running setup after demo: steps 1-4 skip (already complete), no re-prompt for demo
- `setup-state.json` records `demo_mode: true` when demo is accepted
- Demo steps show progress output with download sizes

Key activities:

- Modify `backend/src/linkedout/setup/orchestrator.py`:
  - The demo offer is a "decision gate" inserted in `run_setup` after step 4 completes.
    NOT a formal `SetupStep`. This keeps the 14-step structure intact.
  - After the python_env step succeeds:
    1. Check if this is a fresh setup (no steps beyond python_env are complete)
    2. Check if `demo_mode` is already set in config (don't re-offer)
    3. If eligible, call `_offer_demo(context)` which presents the prompt
    4. If accepted, run the D1-D5 demo steps (see below), then return — don't continue
       with steps 5-14
    5. Mark steps 5-11 as `"demo-skipped"` in `SetupState.steps_completed`
  - Add `DEMO_SKIPPABLE_STEPS` constant:
    `{"api_keys", "user_profile", "csv_import", "contacts_import", "seed_data", "embeddings", "affinity"}`
  - **Step numbering logic:** When the demo offer is eligible (fresh setup, steps 1-4
    only), display steps 1-4 as "Step N of 4". When demo is declined, restart numbering
    as "Step 5 of 14" for the remaining steps. When demo is not eligible (re-run),
    show "Step N of 14" as normal.

- **Demo steps D1-D5** (executed only when user accepts demo):
  ```
  D1: Downloading demo data (100 MB)...        → download_demo()
  D2: Downloading search model (275 MB)...     → pre_download_model('local')
  D3: Restoring demo database...               → restore_demo()
  D4: Installing skills for Claude Code...     → setup_skills() with auto_accept=True
  D5: Readiness check...                       → generate_readiness_report()
  ```
  These are NOT formal SetupSteps. They are inline in `_run_demo_setup()` with their
  own D-prefixed output labels.

- Create `backend/src/linkedout/setup/demo_offer.py`:
  - `offer_demo(context: SetupContext) -> bool`: presents the demo prompt with download
    size (~375 MB), returns True if user accepts
  - `run_demo_setup(context: SetupContext) -> OperationReport`: orchestrates D1-D5,
    returns combined report
  - Demo offer prompt explicitly states: "~375 MB total download (demo data + search model)"
  - Handles errors gracefully: if download fails (network), report the error and offer
    to continue with full setup instead

- Modify `setup_skills()` in `skill_install.py`:
  - Add `auto_accept: bool = False` parameter
  - When `auto_accept=True` (demo mode), skip the Y/n prompt. Instead print what's
    being installed with "(skip with Ctrl+C)" note
  - Default behavior (full setup) unchanged — Y/n prompt remains

- Modify `should_run_step` to recognize `"demo-skipped"` as a completed state:
  - Currently checks `if not completed_at:` -- `"demo-skipped"` counts as completed

- **Transition flow** (re-running setup in demo mode):
  - When `linkedout setup` detects `demo_mode: true` in config, present transition
    prompt: "You're using demo data. Ready to set up with your own connections? [Y/n]"
  - Below the prompt: "Your network, your profile — affinity scores will be personalized
    to you."
  - If accepted: clear `"demo-skipped"` markers for steps 5-11, set `demo_mode: false`,
    update `database_url` to `linkedout`, regenerate `agent-context.env`, then run
    steps 5-14 as normal
  - If declined: show all steps as complete/skipped (fast no-op), exit

- Write tests:
  - `test_demo_offer_flow.py`: mock user input, verify D1-D5 execute in order
  - `test_orchestrator_demo_mode.py`: verify demo steps run, steps 5-14 do NOT run
  - `test_should_run_step_demo_skipped.py`: verify `"demo-skipped"` is treated as complete
  - `test_step_numbering.py`: verify "Step N of 4" in demo-eligible run, "Step N of 14" otherwise
  - `test_transition_flow.py`: verify accepting transition clears demo-skipped, runs 5-14
  - `test_demo_rerun_noop.py`: verify re-running setup in demo mode (declining transition) is fast no-op

**Design review:**
- Architecture: Inserting the demo offer as inline logic in `run_setup` rather than a
  formal step avoids re-numbering all 14 steps — a breaking change to `setup-state.json`.
- The D1-D5 numbering is presentation-only — no new SetupStep objects, no state file changes.
- Error paths: If any D-step fails, the system falls back to offering full setup.
  `setup-state.json` only records demo-skipped states after a successful D3 (restore).
- Transition: `linkedout setup` is the ONE path for transitioning. `use-real-db` exists
  as a power-user escape hatch. The nudge footer says "linkedout setup to use your own
  data" — consistent with the transition trigger.
- Spec: See `backend/docs/specs/onboarding-experience.md` for the full terminal narratives.

---

## Sub-phase 4: Demo Nudges, Reset & Transition

**Outcome:** While in demo mode, all CLI output includes a one-line footer nudging toward
real setup. A `linkedout reset-demo` command re-restores from the cached dump. A
`linkedout use-real-db` command switches config to the real database and optionally drops
the demo DB.

**Dependencies:** Sub-phase 3 (needs demo mode detection and config switching)

**Estimated effort:** 1.5 sessions (~5 hours)

**Verification:**
- In demo mode, every CLI command output ends with:
  `Demo mode -- linkedout setup to use your own data`
- The nudge does not appear when `demo_mode: false`
- `linkedout reset-demo` drops and re-restores `linkedout_demo` from cached dump
- `linkedout reset-demo` without cached dump errors with "Run linkedout download-demo first"
- `linkedout use-real-db` sets `demo_mode: false`, points config at `linkedout` DB
- `linkedout use-real-db --drop-demo` also drops `linkedout_demo`
- `linkedout use-real-db` when not in demo mode says "Already using real database"
- `linkedout status` shows which database is active (demo vs real)

Key activities:

- Implement the nudge footer via a CLI hook in `backend/src/linkedout/cli.py`:
  - Add a `result_callback` to the main CLI group that appends the nudge line after
    every command's output when `demo_mode` is True
  - Implementation: `@cli.result_callback()` / `def _append_demo_nudge(**kwargs):`
  - The nudge text: `"\nDemo mode \u00b7 linkedout setup to use your own data"`
  - Read demo_mode lazily (only import config when the callback runs) to avoid slowing
    down CLI startup
  - Alternative approach if result_callback doesn't work well with lazy loading:
    use a `click.get_current_context().call_on_close()` pattern in each command,
    or a shared decorator. Prefer result_callback for DRY.

- Create `backend/src/linkedout/commands/reset_demo.py`:
  - Click command `reset-demo` with `--yes/-y` confirmation skip
  - Check demo dump exists at cache path
  - Call `drop_demo_database` + `create_demo_database` + `restore_demo_dump` from
    `demo/db_utils.py`
  - Do NOT re-download -- reuse cached file (instant reset)
  - Print success with profile count

- Create `backend/src/linkedout/commands/use_real_db.py`:
  - Click command `use-real-db` with `--drop-demo` flag
  - Check that demo mode is currently active
  - Call `set_demo_mode(data_dir, enabled=False)` to switch config
  - If `--drop-demo`: call `drop_demo_database`
  - Regenerate `agent-context.env`
  - Print: "Switched to real database. Run `linkedout setup` to continue setup."

- Update `linkedout status` in `backend/src/linkedout/commands/status.py`:
  - Show `[DEMO]` indicator when demo mode is active
  - Show which database is connected: `DB: linkedout_demo (demo)` vs `DB: linkedout`
  - In JSON output, add `"demo_mode": true/false` and `"database_name": "..."` fields

- Register `reset-demo` and `use-real-db` commands in `cli.py` under the `# --- Demo ---`
  section.

- Write tests:
  - `test_nudge_footer.py`: verify footer appears in demo mode, absent otherwise
  - `test_reset_demo.py`: verify drop+restore cycle
  - `test_use_real_db.py`: verify config switch and optional drop

**Design review:**
- Naming: `reset-demo` follows the `verb-noun` pattern. `use-real-db` is slightly
  different -- it's more of a state transition than an action on an object. Considered
  `switch-to-real` or `exit-demo`, but `use-real-db` is the most descriptive and
  unambiguous from skill context. The command name should be obvious without reading
  help text.
- Error paths: `reset-demo` without a cached dump is a clear error with a recovery
  action. `use-real-db` when the real `linkedout` DB doesn't exist yet is fine -- the
  user will run `linkedout setup` next, which creates it. No need to pre-validate.
- The nudge footer approach (persistent one-liner) is the simplest possible
  implementation -- no state tracking, no dismissal, no frequency logic. Matches the
  resolved requirement exactly.

---

## Sub-phase 5: Sample Queries & Demo Experience Polish

**Outcome:** After demo restore, the user sees sample queries demonstrating all three
pillars (search, affinity, AI agent). Each query has followups. The demo user's profile
is explained so affinity scores make sense. A `linkedout demo-help` command re-shows
these at any time.

**Dependencies:** Sub-phase 3 (needs successful demo restore flow)

**Estimated effort:** 1 session (~3 hours)

**Verification:**
- After `linkedout restore-demo` or setup demo acceptance, sample queries are printed
- Sample queries cover: semantic search, affinity/relationship, AI agent
- Each sample includes 1-2 followup queries
- The demo user profile is described (role, company, location, skills, experience years)
- `linkedout demo-help` re-displays all sample queries and profile explanation
- Explanations include "why" behind affinity scores (shared company, skills, seniority)

Key activities:

- Create `backend/src/linkedout/demo/sample_queries.py`:
  - `DEMO_USER_PROFILE_DESCRIPTION`: Multi-line string describing the demo user's
    identity (founder/CTO composite, Bengaluru-based, ML + product + data skills,
    8 years experience). Written as prose, not a data structure.
  - `SAMPLE_QUERIES`: List of dicts, each with `category` (search/affinity/agent),
    `query`, `explanation`, `followups` (list of strings).
  - Example queries:
    1. **Semantic search:** "Who in my network has experience with distributed systems at
       a Series B startup?" -- Followup: "Tell me more about [name]'s background"
    2. **Affinity:** "Who are my strongest connections in ML?" -- Followup: "Why does
       [name] score higher than [name]?" -- Explanation: scores reflect shared skills,
       company overlap, seniority proximity
    3. **AI agent:** "Compare the top 3 data scientists in my network for a founding
       engineer role" -- Followup: "Draft a reachout message for [name]"
  - `format_sample_queries() -> str`: Returns formatted string with all queries, suitable
    for terminal output. Uses section headers, indentation, and color (via click.style).
  - `format_demo_profile() -> str`: Returns the profile description formatted for
    terminal output.

- Create `backend/src/linkedout/commands/demo_help.py`:
  - Click command `demo-help`
  - Prints the demo profile description followed by sample queries
  - Works regardless of demo mode (informational, not gated)

- Modify `restore_demo.py` to call `format_demo_profile()` and `format_sample_queries()`
  after successful restore.

- Modify `demo_offer.py` to show sample queries after successful demo setup in the
  orchestrator flow.

- Register `demo-help` in `cli.py`.

**Design review:**
- The sample queries are hardcoded strings, not generated from DB content. This is
  intentional -- they're curated for educational value, and they'll work with any demo
  dump that has the expected profile distribution. If the dump changes significantly,
  the queries should be updated in the same PR.
- The demo user profile description must match what's actually in the dump. This creates
  a coupling between the generation script (Sub-phase 6) and this file. Mitigated by
  using the same constant for generation and display.

---

## Sub-phase 6: Generation Pipeline (scripts/generate-demo-dump.py)

**Outcome:** A maintainer-only script connects to the production Postgres database,
samples 2,000 profiles with stratified sampling, anonymizes PII, re-embeds with fresh
embeddings, computes affinity, creates connection records for the system user, and
produces a `pg_dump --format=custom` file ready for upload as a GitHub Release asset.

**Dependencies:** Sub-phase 1 (needs demo constants for IDs and data_source markers)

**Estimated effort:** 3 sessions (~10 hours)

**Verification:**
- Script runs: `python scripts/generate-demo-dump.py --db-url=<prod> --output=demo-seed.dump`
- Output file exists and is 50-150 MB
- Restore the dump into a test database and verify:
  - `SELECT count(*) FROM crawled_profile` = ~2,000
  - `SELECT count(*) FROM experience` = ~12,000
  - `SELECT count(*) FROM education` = ~4,400
  - `SELECT count(*) FROM profile_skill` = ~10,000
  - `SELECT count(*) FROM connection` = ~2,000
  - `SELECT count(*)` from company tables matches seed data (~48K)
  - No real names in `crawled_profile`: `SELECT first_name FROM crawled_profile LIMIT 20`
    returns Faker names
  - All IDs start with `cp_demo_`, `exp_demo_`, etc.
  - All `data_source = 'demo-seed'`
  - Embeddings exist: `SELECT count(*) FROM crawled_profile WHERE embedding_local IS NOT NULL`
  - Affinity scores exist: `SELECT count(*) FROM connection WHERE affinity_score IS NOT NULL`
  - Alembic version table exists: `SELECT * FROM alembic_version`
  - Connection records reference `usr_sys_001`
- Stratified sampling check: distribution of `seniority_level`, `function_area`,
  `location_country` in demo data roughly matches production distribution
- PII check: no LinkedIn URLs contain real public identifiers

Key activities:

- Create `scripts/generate-demo-dump.py` (gitignored):
  - CLI args: `--db-url` (required), `--output` (default: `demo-seed.dump`),
    `--sample-size` (default: 2000), `--seed` (random seed for reproducibility)
  - High-level flow:
    1. Connect to production database (read-only)
    2. Run stratified sampling query
    3. Create a temporary database (`linkedout_demo_gen`)
    4. Run Alembic migrations against the temp DB (creates clean schema)
    5. Insert anonymized data in FK-safe order
    6. Run `linkedout embed` against the temp DB
    7. Run `linkedout compute-affinity` against the temp DB
    8. Run `pg_dump --format=custom` on the temp DB
    9. Drop the temp DB
    10. Print summary stats

- Implement stratified sampling in the script:
  - Query production for seniority_level/function_area/location_country distribution
  - Calculate per-bucket sample sizes proportional to production distribution
  - For each bucket, `SELECT * FROM crawled_profile WHERE seniority_level = X AND
    function_area = Y AND location_country = Z ORDER BY RANDOM() LIMIT N`
  - Handle small buckets: if a bucket has fewer profiles than its proportional share,
    take all and redistribute remainder to larger buckets

- Implement anonymization functions:
  - `anonymize_name(profile) -> (first, last, full)`: Uses Faker with locale matching
    (`en_IN` for India, `en_US` for US, `en_GB` for UK, etc.)
  - `anonymize_linkedin_url(index) -> str`:
    `f"https://www.linkedin.com/in/demo-user-{index:04d}"`
  - `anonymize_headline(profile) -> str`:
    `f"{profile.current_position} at {profile.current_company_name}"`
  - `anonymize_about(profile, skills) -> str`:
    `f"Experienced {profile.current_position} with expertise in {', '.join(skills[:3])}..."`
  - `jitter_count(count, pct=0.20) -> int`: `count * random.uniform(1-pct, 1+pct)`
  - `generate_demo_id(prefix, index) -> str`: `f"{prefix}{index:04d}"` for profiles,
    `f"{prefix}{index:06d}"` for experiences/education/skills

- Implement data insertion (FK-safe order):
  1. Organization tables (tenant, BU, user) -- use system IDs from agent_context.py
  2. Company reference data -- copy all ~48K companies from production as-is
  3. Company aliases, funding rounds -- copy as-is
  4. Role aliases -- copy as-is
  5. Anonymized crawled_profiles (2K)
  6. Experiences (~12K) -- real positions/companies/dates, new IDs
  7. Education (~4.4K) -- real schools/degrees/fields, new IDs
  8. Skills (~10K, capped at 5 per profile) -- real skill names, new IDs
  9. Connection records (2K) -- one per profile, linked to system user

- Embed and compute affinity:
  - Set `DATABASE_URL` env var to point at temp DB
  - Call `linkedout embed` as subprocess (reuses existing embedding infrastructure)
  - Call `linkedout compute-affinity` as subprocess
  - Both commands are idempotent and will process all profiles/connections

- Create the demo user profile record:
  - The system user (`usr_sys_001`) needs a crawled_profile record in the demo DB
    representing the "founder/CTO composite" profile described in requirements
  - This profile is NOT from production -- it's a synthetic profile modeled after SJ
  - Include: founder/CTO title, Bengaluru location, broad skills (ML, product, data,
    distributed systems, Python, leadership), 8 years experience
  - This profile gets embedded along with the 2K sampled profiles

- Add `scripts/generate-demo-dump.py` to `.gitignore`

- Create `scripts/demo-manifest-template.json`:
  ```json
  {
    "version": "demo-v1",
    "files": [
      {
        "name": "demo-seed.dump",
        "tier": "demo",
        "sha256": "<computed-after-dump>",
        "size_bytes": 0
      }
    ]
  }
  ```

**Design review:**
- Security: The script connects to production with provided credentials. It reads
  only -- no writes. The output dump contains no real PII. However, the script itself
  is gitignored to prevent accidental exposure of production connection patterns.
- Error paths: If embedding fails (e.g., local model not downloaded), the script should
  error clearly: "Download the nomic-embed-text-v1.5 model first." No API key needed.
- Architecture: Using a temporary database (`linkedout_demo_gen`) for generation means
  we can run Alembic migrations to get a clean schema, then insert data, then embed/score.
  This guarantees the dump's schema matches what `pg_restore` expects on the user's end.
  If we instead tried to dump from production, we'd need to handle schema differences.
- Data coupling: The demo user profile (founder/CTO) must be consistent between:
  (a) the generation script where it's inserted, (b) `sample_queries.py` where it's
  described, and (c) the affinity scores which are relative to it. Any change to the
  demo user requires regenerating the dump AND updating the description.
- Dump size estimate: 2K profiles * ~6KB embedding = 12MB for embeddings. 2K profiles +
  12K experiences + 4.4K education + 10K skills + 48K companies = ~75K rows of
  structured data, maybe 20-30MB. Total raw ~40MB, pg_dump custom format compresses
  well. Estimate: 50-100MB. Within the 50-150MB target.

---

## Sub-phase 7: Documentation & Getting-Started Update

**Outcome:** `docs/getting-started.md` describes the demo experience prominently. Users
who read the docs know they can try demo mode. The README links to it. All demo CLI
commands are documented with examples.

**Dependencies:** Sub-phases 4 and 5 (needs all commands finalized)

**Estimated effort:** 0.5 sessions (~2 hours)

**Verification:**
- `docs/getting-started.md` has a "Try the Demo" section before the "Clone & Setup" section
  or immediately after prerequisites
- All demo commands are listed with descriptions and examples:
  `download-demo`, `restore-demo`, `reset-demo`, `use-real-db`, `demo-help`
- The demo flow is shown as an alternative path in the setup instructions
- `README.md` mentions "try with demo data" in the quick-start section

Key activities:

- Update `docs/getting-started.md`:
  - Add a "Quick Demo (2 minutes)" section right after Prerequisites
  - Show the demo setup flow: `linkedout setup` -> accept demo offer -> try sample queries
  - Explain what's in the demo: 2K profiles, search, affinity, AI agent
  - Explain how to reset and transition
  - Link to the full setup for real data

- Add demo command reference to `docs/getting-started.md` or a new `docs/demo.md`:
  - `linkedout download-demo` -- download demo database dump
  - `linkedout restore-demo` -- restore demo into `linkedout_demo`
  - `linkedout reset-demo` -- reset demo to original state
  - `linkedout use-real-db` -- switch to real database
  - `linkedout demo-help` -- show sample queries and demo profile

- Update `README.md` quick-start to mention demo option

**Design review:** No flags.

---

## Sub-phase 8: Testing & CI

**Outcome:** Comprehensive test coverage for the demo experience: a synthetic test dump
for development, unit/integration tests for all demo flows, and a CI end-to-end smoke
test that proves the demo works on Ubuntu and macOS.

**Dependencies:** Sub-phases 1-5 and 7 (all user-facing code and docs must be complete)

**Estimated effort:** 2 sessions (~6 hours)

**Verification:**
- All unit tests pass without Postgres
- All integration tests pass with a running Postgres
- CI smoke test passes on Ubuntu (latest) and macOS (latest)
- CI smoke test executes 2 real queries against the demo DB and verifies results

Key activities:

- **Create a synthetic test dump** (`backend/tests/fixtures/demo-seed-test.dump`):
  - A tiny pg_dump with ~10 profiles, ~50 experiences, ~20 education records, ~30 skills,
    ~10 connections, ~100 companies, pre-computed local embeddings, and affinity scores
  - Created by a script `backend/tests/fixtures/generate_test_demo_dump.py` that builds
    a temporary DB, inserts fixture data, runs embed + compute-affinity, then pg_dumps
  - This dump is committed to the repo (small, ~1-2 MB) so all tests can use it
  - Includes the system user profile (founder/CTO composite) with known affinity patterns

- **Unit tests** (no Postgres needed):
  - `test_demo_config.py`: demo_mode parsing, get_demo_db_url, set_demo_mode
  - `test_demo_offer_flow.py`: mock user input (accept/decline), verify D1-D5 sequence
  - `test_step_numbering.py`: verify "Step N of 4" vs "Step N of 14" logic
  - `test_nudge_footer.py`: footer appears in demo mode, absent otherwise
  - `test_transition_flow.py`: mock transition accept/decline, verify config changes
  - `test_sample_queries.py`: verify sample query content covers all 3 pillars
  - `test_demo_rerun_noop.py`: re-running setup in demo mode (decline transition) is fast

- **Integration tests** (require Postgres):
  - `test_restore_demo.py`: create/drop/restore cycle with the synthetic test dump
  - `test_reset_demo.py`: reset restores to original state
  - `test_use_real_db.py`: config switch and optional drop
  - `test_demo_query.py`: restore synthetic dump, run a semantic search query, verify
    results are returned (this proves embeddings + pgvector + the full search stack work)
  - `test_demo_stats.py`: verify get_demo_stats returns correct counts after restore
  - `test_prerequisites_pg_restore.py`: verify pg_restore check works

- **CI end-to-end smoke test** (`.github/workflows/demo-smoke-test.yml`):
  - Runs on: `ubuntu-latest` and `macos-latest`
  - Triggered on: PRs that touch `backend/src/linkedout/demo/`, `backend/src/linkedout/setup/`,
    or `backend/src/linkedout/commands/*demo*`
  - Steps:
    1. Install Python 3.12, PostgreSQL 16, pgvector
    2. Clone repo
    3. Run `linkedout setup` with mock input accepting demo (use synthetic test dump, not
       the real ~100MB dump — keep CI fast)
    4. Verify demo mode is active: `linkedout status --json | jq '.demo_mode'` == true
    5. Run query 1: `linkedout query "ML engineer"` → verify non-empty results
    6. Run query 2: `linkedout query "Series B startup"` → verify non-empty results
    7. Run `linkedout reset-demo` → verify DB restored
    8. Run `linkedout use-real-db --drop-demo` → verify demo DB gone
  - Timeout: 10 minutes
  - Uses the synthetic test dump from fixtures (not GitHub Releases download)

- **Manual verification checklist** (for the REAL dump from Sub-phase 6):
  - Restore the real dump on a clean Ubuntu 24.04 machine
  - Run all 3 sample queries from demo-help
  - Verify affinity scores are intuitive for the founder/CTO demo profile
  - Verify the nudge footer appears
  - Run transition flow and complete full setup
  - This is done once before publishing the dump as a GitHub Release

---

## Build Order

```
Sub-phase 1 (Config) ──► Sub-phase 2 (CLI) ──► Sub-phase 3 (Orchestrator) ──► Sub-phase 4 (Nudges/Reset)
                    │                                                                    │
                    │                                                                    ▼
                    └──► Sub-phase 6 (Generation) ──────────────────────► Sub-phase 5 (Sample Queries)
                                                                                         │
                                                                                         ▼
                                                                                Sub-phase 7 (Docs)
                                                                                         │
                                                                                         ▼
                                                                                Sub-phase 8 (Testing & CI)
```

**Critical path:** 1 → 2 → 3 → 4 → 7 → 8

**Parallel track:** Sub-phase 6 (Generation) runs in parallel with 2-4. Sub-phase 5
comes after 6 because the demo user profile in queries must match what the generation
script creates.

**Testing strategy:** Sub-phases 2-4 can be developed and tested using the synthetic
test dump (created in Sub-phase 8's first task). The real production-sourced dump from
Sub-phase 6 is only needed for the final manual verification before publishing.

---

## Design Review Flags

| Sub-phase | Flag | Action |
|-----------|------|--------|
| Sub-phase 1 | Spec exists: `backend/docs/specs/onboarding-experience.md` | Check spec before implementing any user-facing behavior |
| Sub-phase 3 | Demo fork is after step 4 (not step 3), uses D1-D5 numbering | No orchestrator step re-numbering needed |
| Sub-phase 3 | Dependency chain for steps 12-14 when 5-11 are skipped | Steps must be marked in `steps_completed` as `"demo-skipped"` to satisfy dependency checks |
| Sub-phase 4 | Nudge footer via `result_callback` -- may not fire for commands that call `sys.exit()` | Test with `reset-db`, `status`, and error cases. Fallback: decorator approach |
| Sub-phase 6 | Demo user profile must match between generation script and sample_queries.py | Use shared constant or document the coupling explicitly |
| Sub-phase 6 | Embedding generation uses local model (`nomic-embed-text-v1.5`) | Model must be downloaded locally before running generation script |

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Demo dump too large (>150 MB) | Slow download, GitHub Release asset limits | Monitor dump size during Sub-phase 6. If too large: reduce profile count, use local (768-dim) embeddings instead of OpenAI (1536-dim), or compress further |
| `pg_restore` version mismatch between dump creator and user | Restore fails with cryptic error | Pin pg_dump format version. Document required Postgres version. Consider shipping SQL dump as fallback |
| Alembic version in dump drifts from repo HEAD | Restore works but subsequent migrations fail or skip incorrectly | Document: "new Alembic migrations require a new demo dump release." Add version check in restore that warns if dump is older than repo's migration head |
| Faker locale coverage gaps | Some countries produce English names instead of locale-matched | Pre-test Faker locales for top 10 countries in the data. Fallback to `en_US` for unsupported locales |
| Demo user profile affinity scores unrealistic | Scores don't demonstrate the product well | Hand-tune the demo profile to produce interesting affinity variation. Test with sample queries before publishing dump |

## Resolved Questions

1. **GitHub Release strategy:** Same `linkedout-oss` repo, separate release tag (`demo-v1`). No separate repo needed. GitHub Release assets support up to 2GB; dump is well under 150MB.

2. **Embedding provider for generation:** Local model (`nomic-embed-text-v1.5`, 768-dim). Free, no API key required during generation. Embeddings stored in `embedding_local` column. Smaller dump size.

3. **Embedding column compatibility at query time:** Demo mode auto-configures `embedding_provider: local`. When `set_demo_mode(enabled=True)` runs, it also sets the embedding provider to local so query-time embeddings use the same 768-dim model. Dimensions match, search works immediately with zero config. No API key needed for demo users.

## Spec References

- **`backend/docs/specs/onboarding-experience.md`** — Source of truth for all user-facing
  onboarding behavior (demo path, full setup path, transition, nudges, terminal narratives).
  All sub-phases must conform to this spec. The spec includes concrete terminal output
  examples showing exactly what the user sees at each step.
