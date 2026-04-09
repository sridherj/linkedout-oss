---
feature: onboarding-experience
module: src/linkedout/setup, src/linkedout/demo, src/linkedout/commands
linked_files:
  - src/linkedout/setup/orchestrator.py
  - src/linkedout/setup/demo_offer.py
  - src/linkedout/setup/prerequisites.py
  - src/linkedout/setup/api_keys.py
  - src/linkedout/setup/csv_import.py
  - src/linkedout/setup/seed_data.py
  - src/linkedout/setup/user_profile.py
  - src/linkedout/demo/__init__.py
  - src/linkedout/demo/sample_queries.py
  - src/linkedout/demo/db_utils.py
  - src/linkedout/commands/download_demo.py
  - src/linkedout/commands/restore_demo.py
  - src/linkedout/commands/reset_demo.py
  - src/linkedout/commands/use_real_db.py
  - src/linkedout/commands/demo_help.py
  - src/linkedout/commands/setup.py
last_verified: 2026-04-10
version: 3
---

# Onboarding Experience

**Created:** 2026-04-08 -- New spec covering setup flow, demo mode, and transition
**Updated:** 2026-04-08 -- Added full setup prompt principles (WHY before HOW for steps 5-9)
**Updated:** 2026-04-10 -- Added --demo/--full flags, pgvector template1 install, actionable pgvector error

## Intent

Provide two paths from clone to first query: a **demo path** (under 5 minutes, zero
config beyond Postgres) and a **full setup path** (15-30 minutes, real data). Both paths
use the same `linkedout setup` entry point and share the first 4 infrastructure steps.
After step 4, the user chooses: accept the demo (download a pre-built Postgres dump with
2,000 anonymized profiles, pre-computed embeddings, and affinity scores into a separate
`linkedout_demo` database) or continue to full setup (steps 5-14 to import their own
LinkedIn data). Users can transition from demo to full setup at any time via
`linkedout setup`.

## Behaviors

### Common Infrastructure (Steps 1-4)

- **CLI flags for path selection**: `linkedout setup` accepts `--demo` and `--full` flags
  to skip the interactive demo offer. `--demo` proceeds directly to demo setup (D1-D5)
  after infrastructure steps. `--full` proceeds directly to full setup (steps 5-14).
  Without either flag, the interactive demo offer appears after step 4. The
  `/linkedout-setup` skill asks the user conversationally which mode they prefer, then
  invokes `linkedout setup --demo` or `linkedout setup --full`.

- **Four shared infrastructure steps**: Running `linkedout setup` begins with 4 steps
  common to both paths: (1) Prerequisites Detection, (2) System Setup, (3) Database
  Setup, (4) Python Environment. In demo mode these display as "Step N of 4". In full
  setup mode they display as "Step N of 14". Verify all 4 steps execute on a fresh system
  regardless of which path the user chooses.

- **Prerequisites include pg_restore**: Step 1 (Prerequisites Detection) verifies
  `pg_restore` is available alongside `psql`, Python, PostgreSQL, and pgvector. Both
  tools ship in the same PostgreSQL client package. If `psql` exists but `pg_restore`
  does not, report it as a missing prerequisite. Verify the prerequisites check fails
  when `pg_restore` is absent.

- **Idempotent resume**: Re-running `linkedout setup` skips completed steps, printing
  a checkmark and "Already complete" for each. State is persisted in
  `~/linkedout-data/state/setup-state.json`. Verify re-running after a partial failure
  resumes from the failed step.

- **Step failure with diagnostic**: When a step fails, setup stops, saves partial state,
  writes a diagnostic file, and prints a resume hint. Verify the diagnostic includes the
  error, completed steps, and config context.

### Demo Offer (Decision Gate After Step 4)

- **Demo prompt after Python env**: After step 4 (Python Environment) succeeds on a
  fresh install, setup presents a boxed prompt offering to load demo data. The prompt
  describes what the user gets (2,000 sample profiles, search, affinity, AI agent),
  states the total download size (~375 MB: demo data + search model), and offers [Y/n]
  with "Try the demo" as the default. Verify the prompt appears only on first run when
  no steps beyond step 4 are complete.

- **Demo offer not shown on re-run**: If the user has already accepted or declined the
  demo (recorded in setup-state.json), the prompt does not appear on subsequent
  `linkedout setup` runs. Verify re-running setup after accepting demo does not re-offer.

- **Declining demo continues full setup**: If the user presses 'n', setup continues with
  step 5 (API Key Collection) and all remaining steps as normal, with step numbering
  switching to "Step N of 14". Verify declining produces the same flow as if the demo
  prompt were absent.

> Edge: If the user has completed steps beyond step 4 (e.g., they ran step 5 manually
> before the demo feature existed), the demo offer is not shown -- the user is past the
> decision point.

### Demo Path (Accept Flow)

- **Demo-specific step numbering**: After the user accepts the demo offer, remaining
  steps use demo-specific labels D1 through D5 instead of the internal 14-step
  numbering. The user chose demo; the full setup's step numbers are irrelevant. Verify
  demo steps display as "D1:", "D2:", etc., not "Step 12 of 14".

- **D1 downloads demo data**: D1 downloads the demo dump from GitHub Releases (~100 MB)
  to `~/linkedout-data/cache/demo-seed.dump` with a progress bar. Verify the file exists
  at the expected path after download.

- **D2 downloads the search model**: D2 downloads the nomic-embed-text-v1.5 model
  (~275 MB) needed for query-time embedding in demo mode. This is a separate step from
  D1 so progress is clear. Verify the model is available after D2 completes.

- **D3 restores the demo database**: D3 creates a `linkedout_demo` Postgres database and
  restores the dump via `pg_restore`. The pgvector extension is inherited from `template1`
  (installed during the `setup` script). If pgvector is not available, `db_utils.py`
  raises a clear error telling the user to run the superuser command manually — the
  application never attempts `sudo`. Verify the demo database contains the expected
  profile count after restore.

- **D4 auto-installs skills**: D4 installs skills for Claude Code, Codex, and Copilot
  without a Y/n prompt (the user already committed to trying the demo). Displays what is
  being installed and notes "(skip with Ctrl+C)" for users who want to skip. Verify
  skills are installed without prompting. In full setup mode (step 12), the Y/n prompt
  remains.

- **D5 runs readiness check**: D5 runs the readiness check showing profile count,
  company count, embedding status, and affinity status. Verify the readiness report
  reflects the demo database contents.

- **Config switch to demo mode**: After successful restore, setup sets `demo_mode: true`
  and updates `database_url` to point at `linkedout_demo` in `config.yaml`. The
  `embedding_provider` is set to `local` (768-dim nomic model, matching the dump's
  embeddings). Verify `config.yaml` reflects demo mode after acceptance.

- **Agent context updated for demo**: After demo restore, `agent-context.env` is
  regenerated with the demo database URL and system user IDs
  (`tenant_sys_001`, `bu_sys_001`, `usr_sys_001`). Skills read this file for DB access.
  Verify `agent-context.env` points to `linkedout_demo` after demo setup.

- **Demo steps recorded in setup state**: Steps 5-11 are recorded as "demo-skipped" in
  `setup-state.json`. Steps D4 and D5 correspond to the internal steps "skills" and
  "readiness" and are recorded with their normal timestamps. Verify `setup-state.json`
  contains "demo-skipped" for steps 5-11 and timestamps for steps 1-4, skills, and
  readiness.

> Edge: If `pg_restore` fails (e.g., Postgres version mismatch), the demo setup reports
> the error and offers to continue with full setup instead. The user is never stuck.

> Edge: If the network download fails at D1 or D2, setup reports the error with a retry
> hint (`linkedout download-demo --force`) and offers to continue with full setup.

### Demo Terminal Output Narrative

- **Demo path end-to-end output**: After accepting the demo, the user sees the following
  terminal sequence. Verify the output matches this narrative from start to finish.

  Expected terminal flow (demo path):
  ```
  Step 1 of 4: Prerequisites Detection
    [checkmark] All prerequisites met

  Step 2 of 4: System Setup
    [checkmark] Complete

  Step 3 of 4: Database Setup
    [checkmark] Database 'linkedout' created

  Step 4 of 4: Python Environment
    Installing dependencies... done
    [checkmark] Complete

  +----------------------------------------------+
  |  Want to try LinkedOut with demo data first?  |
  |                                               |
  |  We'll load 2,000 sample profiles so you can  |
  |  test search, affinity scoring, and the AI    |
  |  agent before importing your own connections. |
  |                                               |
  |  ~375 MB total download                       |
  |  (demo data + search model)                   |
  |                                               |
  |  [Y] Try the demo   [n] Skip to full setup   |
  +----------------------------------------------+

  D1: Downloading demo data (100 MB)... [progress] done
  D2: Downloading search model (275 MB)... [progress] done
  D3: Restoring demo database... done
  D4: Installing skills for Claude Code, Codex... [checkmark]
      (skip with Ctrl+C)
  D5: Readiness check... [checkmark]

  [checkmark] Demo ready!

  ================================================
  Here's who you are in the demo:

  Your demo profile is a Founder/CTO at a Bengaluru-based
  startup, with 8 years across ML, product, and engineering.
  Affinity scores are relative to this profile -- connections
  with overlapping skills and seniority score higher.

  Try these queries with the /linkedout skill:

  1. "Who in my network has ML experience at a Series B startup?"
     -> Then: "Tell me more about [name]'s background"

  2. "Who are my strongest connections in data science?"
     -> Then: "Why does [name] score higher than [name]?"

  3. "Compare the top 3 engineers for a founding role"
     -> Then: "Draft a reachout message for [name]"
  ================================================

  Demo mode [dot] linkedout setup to use your own data
  ```

### Full Setup Terminal Output Narrative

- **Full setup end-to-end output**: After declining the demo, the user sees all 14 steps
  in order with prompts at steps 5 (API keys), 6 (user profile), 7 (CSV import), and 9
  (seed data tier). Step numbering switches from "of 4" to "of 14" after declining.
  Verify each step prints its number, name, and result.

  Expected terminal flow (full setup path):
  ```
  Step 1 of 14: Prerequisites Detection
    [checkmark] All prerequisites met

  Step 2 of 14: System Setup
    [checkmark] Complete

  Step 3 of 14: Database Setup
    [checkmark] Database 'linkedout' created

  Step 4 of 14: Python Environment
    Installing dependencies... done
    [checkmark] Complete

  +----------------------------------------------+
  |  Want to try LinkedOut with demo data first?  |
  |  ...                                          |
  |  [Y] Try the demo   [n] Skip to full setup   |
  +----------------------------------------------+
  > n

  Step 5 of 14: API Key Collection
    [prompt for OpenAI key or local embeddings choice]

  Step 6 of 14: User Profile
    [prompt for LinkedIn profile URL]

  Step 7 of 14: LinkedIn CSV Import
    [prompt for CSV file path]

  Step 8 of 14: Contacts Import
    ...

  Step 9 of 14: Seed Data
    [prompt for core/full dataset]

  Step 10 of 14: Embedding Generation
    Generating embeddings for N profiles...

  Step 11 of 14: Affinity Computation
    Computing affinity scores...

  Step 12 of 14: Skill Installation
    [Y/n prompt for skill installation]

  Step 13 of 14: Readiness Check
    LinkedOut v0.1.0 | N profiles | N companies
    | embeddings: N% | affinity: computed

  Step 14 of 14: Gap Detection
    [checkmark] No gaps detected
  ```

### Full Setup Prompt Principles (Steps 5-9)

- **WHY-HOW-COST-DO pattern for data prompts**: Every setup step that asks for user data
  or a configuration choice follows a four-part structure: (1) WHY we need it -- what
  value it unlocks, (2) HOW we'll use it -- concrete product behavior it enables,
  (3) WHAT it costs -- money, time, or disk space, with honest numbers, (4) HOW to
  provide it -- the mechanical instructions. This pattern applies to steps 5, 6, 7, and
  9. Verify each prompt in these steps contains all four parts in order.

- **Step 5 OpenAI cost context**: The embedding provider prompt already includes cost
  per 1,000 profiles (~$0.01). No free tier mention — keep the prompt factual about
  actual costs only. Verify the cost-per-profile figure is accurate if the prompt is
  modified.

- **Step 5 Apify cost context**: The Apify key prompt includes typical enrichment cost:
  ~$4 per 1,000 profiles, with a free $5 credit per account per month. This helps users
  understand both the cost and that there's a meaningful free tier for small networks.
  Verify the Apify prompt includes cost and free tier information.

- **Step 7 WHY your connections matter**: Before the mechanical CSV export instructions,
  the prompt includes a one-liner explaining the purpose: "Your LinkedIn connections are
  the foundation of LinkedOut -- this is the network you'll be searching, scoring, and
  getting intelligence about." Verify the prompt leads with WHY before the HOW-to-export
  instructions.

- **Step 6 user profile WHY (already good)**: The user profile prompt already explains
  that the profile is the "anchor for affinity scoring" and describes "career overlap,
  shared education, professional signals." No change needed. Verify the WHY framing is
  preserved if the prompt text is modified.

- **Step 9 seed data WHY (adequate)**: The seed data prompt already explains what seed
  data provides ("queries like 'who do I know at Series B AI startups?' work
  immediately"). No change needed. Verify the WHY framing is preserved if the prompt
  text is modified.

> Edge: These prompt principles apply to the full setup path only. Demo mode (D1-D5)
> skips steps 5-9 entirely. If a user transitions from demo to full setup, they see
> these prompts for the first time during the transition flow.

### Demo Experience (While in Demo Mode)

- **Persistent nudge footer**: While `demo_mode: true` in config, every CLI command
  output ends with the line: "Demo mode [dot] linkedout setup to use your own data". The
  nudge is a one-liner appended by a CLI result callback. It never blocks commands.
  Verify the footer appears on `linkedout status`, skill invocations, and all other
  commands.

- **Demo-help command**: Running `linkedout demo-help` displays the demo user profile
  explanation and all sample queries with followups, regardless of whether demo mode is
  currently active. Verify the output matches the welcome message from initial demo
  setup.

- **Sample queries cover three pillars**: The sample queries demonstrate semantic search,
  affinity/relationship scoring, and the AI agent. Each query includes 1-2 followup
  queries showing conversational flow. Verify all three pillars are represented.

- **Demo profile explanation**: The sample queries section explains the demo user's
  identity (Founder/CTO, Bengaluru, ML + product + data skills, 8 years experience) so
  users understand why certain connections score higher. Verify the explanation is shown
  both at initial setup and via `linkedout demo-help`.

- **Status command shows demo indicator**: Running `linkedout status` while in demo mode
  displays "[DEMO]" and shows "DB: linkedout_demo (demo)". In JSON output, includes
  `"demo_mode": true` and `"database_name": "linkedout_demo"`. Verify both human and
  JSON outputs include demo indicators.

### Transition from Demo to Real Setup

- **Transition via linkedout setup with positive framing**: When a user in demo mode runs
  `linkedout setup`, the system detects demo mode and presents a transition prompt:
  "You're using demo data. Ready to set up with your own connections? [Y/n]" followed by
  "Your network, your profile -- affinity scores will be personalized to you." Accepting
  clears the "demo-skipped" markers for steps 5-11 and runs them. Steps 1-4 show as
  "Already complete". Declining exits with no changes. Verify accepting triggers the
  remaining real-setup steps.

- **Transition updates config**: Accepting the transition sets `demo_mode: false`,
  updates `database_url` to point at the real `linkedout` database, and regenerates
  `agent-context.env`. Steps 5-11 are no longer "demo-skipped" -- they run as normal
  setup steps. Verify config reflects real mode after transition.

- **Step numbering during transition**: After accepting the transition, steps display as
  "Step N of 14" since the user is now in full setup mode. Steps 1-4 show as "Already
  complete". Steps 5-14 run. Verify numbering uses the 14-step scheme after transition.

- **use-real-db as direct command**: Running `linkedout use-real-db` switches to the real
  database without running setup steps. Supports `--drop-demo` to also drop the
  `linkedout_demo` database. Reports "Already using real database" if not in demo mode.
  Verify config switch and optional drop behavior.

- **Demo database not auto-deleted**: The `linkedout_demo` database is never
  automatically deleted during transition. The user must explicitly request deletion via
  `linkedout use-real-db --drop-demo`. Both databases coexist until the user decides.
  Verify transition does not touch the demo database.

> Edge: If the real `linkedout` database doesn't exist yet when `use-real-db` runs,
> that's fine -- the user will run `linkedout setup` next, which creates it.

### Re-running Setup in Demo Mode

- **Re-run with transition prompt**: When a user in demo mode re-runs `linkedout setup`
  and declines the transition prompt, setup checks all step states. Steps 1-4 show as
  "Already complete". Steps 5-11 show as "Skipped (demo mode)". Steps 12-14 show as
  "Already complete" (skills, readiness, gap detection ran during demo setup). No steps
  re-execute. Verify re-running in demo mode after declining transition is a fast no-op.

- **Re-run after transition proceeds with real setup**: When a user accepts the transition
  prompt, setup clears the "demo-skipped" markers for steps 5-11, resets them to
  incomplete, and runs them. Steps 1-4 remain complete (not re-run). Verify steps 5-11
  execute after transition acceptance.

> Edge: Step 4 (Python Env) was already completed during initial setup and is not re-run
> during transition. If the user switches from local to OpenAI embeddings at step 5, the
> python_env step is version-sensitive and will only re-run if the LinkedOut version
> changes.

### Demo Reset

- **Reset restores original state**: Running `linkedout reset-demo` drops and re-creates
  `linkedout_demo` from the cached dump file at `~/linkedout-data/cache/demo-seed.dump`.
  No re-download occurs. Supports `--yes` to skip confirmation. Verify the database
  matches the original dump after reset.

- **Reset requires cached dump**: If no cached dump exists, `reset-demo` errors with:
  "Run `linkedout download-demo` first". Verify the error message is actionable.

### Standalone Demo Commands

- **download-demo**: Running `linkedout download-demo` downloads the demo dump from
  GitHub Releases to `~/linkedout-data/cache/demo-seed.dump`. Skips download if the file
  exists and the checksum matches. Supports `--force` to re-download. Verify the file
  exists at the expected path after download.

- **restore-demo**: Running `linkedout restore-demo` creates `linkedout_demo` and
  restores the dump. Idempotent (drops and recreates on repeat). Updates config to demo
  mode. Regenerates `agent-context.env`. Prints profile count and sample queries. Verify
  the database is functional after restore.

> Edge: The standalone commands (`download-demo`, `restore-demo`) exist for users who
> want manual control. The `linkedout setup` flow calls them internally -- users on the
> happy path never need to invoke them directly.

### Demo Database Isolation

- **Separate database, never mixed**: Demo data lives in `linkedout_demo`, real data in
  `linkedout`. No data is shared between them. No markers, cleanup hooks, or cascade
  deletes are needed. Verify the two databases have no foreign key references between
  them.

- **Demo dump contents**: The dump contains a complete LinkedOut instance: organization
  tables (system tenant/BU/user), ~48K company records, ~2,000 anonymized profiles with
  ~12K experiences, ~4.4K education records, ~10K skills, ~2,000 connections, pre-computed
  embeddings (pgvector, 768-dim local), pre-computed affinity scores, and the Alembic
  version table. Verify all tables are populated after restore.

- **Demo IDs and markers**: All demo records use prefixed IDs (`cp_demo_`, `exp_demo_`,
  `edu_demo_`, `psk_demo_`, `conn_demo_`) and `data_source='demo-seed'`. Connections
  reference the system user (`usr_sys_001`). Verify all records use demo ID prefixes.

## Decisions

### Database isolation over in-DB markers -- 2026-04-08
**Chose:** Separate `linkedout_demo` database
**Over:** Mixing demo data into the real database with data_source markers and cleanup hooks
**Because:** Eliminates all mixed-data complexity (CASCADE deletes, import hooks, stray
data). Cleanup is `DROP DATABASE`. Dump includes embeddings and affinity so everything
works without additional steps.

### Demo offer after step 4, not step 3 -- 2026-04-08
**Chose:** Present the demo offer after step 4 (Python Environment) completes
**Over:** After step 3 (Database Setup)
**Because:** Steps 1-4 are common infrastructure for all users. Python env is needed
regardless of path (CLI commands, skill execution). The CLI is fully available before
the demo decision point.

### Demo offer as inline gate, not a formal step -- 2026-04-08
**Chose:** Inline decision gate in the orchestrator after step 4
**Over:** Adding a formal 15th setup step
**Because:** Avoids re-numbering the existing 14 steps, which would break
`setup-state.json` for users who have already run setup. The demo offer is a branch,
not a step.

### Demo-specific step numbering (D1-D5) -- 2026-04-08
**Chose:** Demo steps labeled D1-D5 with steps 1-4 showing "of 4"
**Over:** Reusing the 14-step numbering and showing "Step 12 of 14" after skipping 5-11
**Because:** The user chose demo; internal 14-step numbering is irrelevant to them.
Showing "Step 5 of 14" then "Step 12 of 14" is jarring. Demo-specific labels make the
experience feel intentional, not like a broken version of full setup.

### Honest download size disclosure -- 2026-04-08
**Chose:** Demo offer states "~375 MB total download (demo data + search model)"
**Over:** Hiding the download size or promising "2 minutes"
**Because:** Users on slow connections deserve to know what they're committing to. Honesty
builds trust. The value proposition (skip 30 minutes of setup) is strong enough without
false time promises.

### Skills auto-install in demo mode -- 2026-04-08
**Chose:** D4 auto-installs skills without Y/n prompt, with Ctrl+C opt-out
**Over:** Prompting for confirmation like the full setup path (step 12)
**Because:** The user already committed to trying the demo. Skills are needed for the
sample queries to work. The Ctrl+C escape hatch respects user autonomy without adding
friction to the happy path.

### Transition via linkedout setup with positive framing -- 2026-04-08
**Chose:** `linkedout setup` detects demo mode and offers transition with positive framing
**Over:** Requiring users to know about `linkedout use-real-db` or using warning language
**Because:** The nudge footer says "linkedout setup to use your own data". The user
follows that hint naturally. "Personalized to you" frames the transition as an upgrade,
not a loss. `use-real-db` exists as a power-user escape hatch.

### Local embeddings in demo mode, no API key required -- 2026-04-08
**Chose:** Demo dump uses 768-dim nomic-embed-text-v1.5 (local) embeddings
**Over:** OpenAI 1536-dim embeddings
**Because:** Zero API key requirement for demo mode. Smaller dump size. Users who want
OpenAI embeddings choose that during full setup (step 5). Demo mode auto-sets
`embedding_provider: local`.

### WHY-before-HOW prompt structure for setup steps -- 2026-04-08
**Chose:** Every data-collection prompt follows WHY -> HOW -> COST -> DO
**Over:** Leading with mechanical instructions (HOW to export, WHERE to paste)
**Because:** Users who understand WHY their data matters are more likely to complete setup
and less likely to feel surveilled. "This is your network" is more motivating than "paste
your CSV path here." Cost transparency removes anxiety and builds trust. Only mention
free tiers when they are accurate and meaningful (e.g., Apify's $5/month free credit).

### Embedding model download as separate demo step (D2) -- 2026-04-08
**Chose:** D2 downloads the ~275 MB nomic model as a visible demo step
**Over:** Bundling it into Python env (step 4) or into the demo dump download (D1)
**Because:** Step 4 only creates the venv, installs deps, and verifies the CLI -- no model
download. Separating model download into D2 gives the user clear progress visibility
for a large download and keeps step 4 identical in both paths.

## Not Included

- Chrome extension behavior in demo mode (may work incidentally, not specified)
- Multi-user demo support (demo uses a single system user)
- Demo data updates or versioning (dump is regenerated manually by the maintainer)
- Demo expiration or degradation (demo never expires or locks features)
- Data migration from demo to real database (demo is disposable)
- Generation pipeline (maintainer-only tooling, not a user-facing behavior)
- Async demo download with background progress (download is synchronous with progress bar)
- Gap detection step in demo mode (D5 is readiness only; gap detection is for full setup)
