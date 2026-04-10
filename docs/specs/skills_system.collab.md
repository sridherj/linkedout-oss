---
feature: skills-system
module: skills
linked_files:
  - skills/lib/__init__.py
  - skills/lib/config.py
  - skills/lib/template.py
  - skills/lib/frontmatter.py
  - skills/routing/ROUTING.md.tmpl
  - skills/linkedout/SKILL.md.tmpl
  - skills/linkedout/schema-reference.md
  - skills/linkedout-setup/SKILL.md.tmpl
  - skills/linkedout-extension-setup/SKILL.md.tmpl
  - skills/linkedout-upgrade/SKILL.md.tmpl
  - skills/linkedout-history/SKILL.md.tmpl
  - skills/linkedout-report/SKILL.md.tmpl
  - skills/linkedout-setup-report/SKILL.md.tmpl
  - skills/linkedout-dev/SKILL.md
  - skills/hosts/claude.yaml
  - skills/hosts/codex.yaml
  - skills/hosts/copilot.yaml
  - skills/claude-code/CLAUDE.md
  - skills/codex/AGENTS.md
  - skills/copilot/COPILOT.md
  - bin/generate-skills
  - bin/generate-schema-ref
  - setup
  - backend/src/linkedout/setup/skill_install.py
version: 3
last_verified: "2026-04-10"
---

# Skills System

**Created:** 2026-04-09 -- Written from scratch for LinkedOut OSS
**Updated:** 2026-04-10 -- v3: Skills Catalog updated for Skills v2 plan (query logging, graceful degradation, setup-report/report/history rewrites, extension disclaimer, upgrade dirty-check)

## Intent

Provide a multi-host AI skill system that lets users interact with their LinkedOut network data through natural language across different AI coding assistants (Claude Code, OpenAI Codex, GitHub Copilot). Skills are authored once as parameterized templates, then compiled into host-specific instruction files that each platform can consume natively. The system handles routing (which skill to invoke), template rendering (variable substitution and conditionals), frontmatter filtering (per-host metadata rules), and path/tool rewrites (platform naming differences).

## Architecture Overview

The skills system has four layers:

1. **Skill templates** (`skills/<skill-name>/SKILL.md.tmpl`) -- the canonical source of truth for each skill's instructions, written with template variables and conditional blocks.
2. **Host configurations** (`skills/hosts/<host>.yaml`) -- per-platform settings that control output paths, frontmatter filtering, path rewrites, and tool name mappings.
3. **Shared library** (`skills/lib/`) -- Python modules for template rendering, frontmatter processing, and configuration loading.
4. **Generated output** (`skills/<host-output-dir>/`) -- the rendered, host-specific SKILL.md files that AI assistants actually read at runtime.

### Directory Layout

```
skills/
  routing/
    ROUTING.md.tmpl           # Skill router template (rendered to per-host top-level file)
  linkedout/
    SKILL.md.tmpl             # Main query skill template
    schema-reference.md       # Auto-generated DB schema (included via {{DB_SCHEMA_SNIPPET}})
  linkedout-setup/
    SKILL.md.tmpl
  linkedout-extension-setup/
    SKILL.md.tmpl
  linkedout-upgrade/
    SKILL.md.tmpl
  linkedout-history/
    SKILL.md.tmpl
  linkedout-report/
    SKILL.md.tmpl
  linkedout-setup-report/
    SKILL.md.tmpl
  linkedout-dev/
    SKILL.md                  # Static (no template variables), not compiled per-host
  hosts/
    claude.yaml
    codex.yaml
    copilot.yaml
  lib/
    __init__.py               # Public API re-exports
    config.py                 # Host config loader, global context, version reader
    template.py               # Template engine (conditionals + variable substitution)
    frontmatter.py            # YAML frontmatter split/filter/rejoin
  claude-code/                # Generated output for Claude Code
    CLAUDE.md                 # Routing file (skill catalog)
    linkedout/SKILL.md
    linkedout-setup/SKILL.md
    ...
  codex/                      # Generated output for Codex
    AGENTS.md
    linkedout/SKILL.md
    ...
  copilot/                    # Generated output for Copilot
    COPILOT.md
    linkedout/SKILL.md
    ...
```

## Behaviors

### B1: Template Engine

The template engine (`skills/lib/template.py`) supports two constructs:

- **Variable substitution:** `{{VARIABLE_NAME}}` is replaced with the corresponding value from the merged variable dictionary. Variable names must match `[A-Z_][A-Z0-9_]*`. Unresolved variables raise `ValueError`.
- **Conditional blocks:** `{{#if VAR == "value"}}...{{/if}}` and `{{#if VAR != "value"}}...{{/if}}` include or exclude content based on variable comparisons. Conditionals are evaluated iteratively (sequential, not nested) until no more `{{#if` blocks remain.

The rendering pipeline for a skill template is: load template string -> resolve conditionals -> resolve variables.

`render_template_file()` is the high-level entry point that merges host variables with global context before rendering.

### B2: Global Context Variables

`get_global_context()` in `skills/lib/config.py` returns these variables shared across all hosts and skills:

| Variable | Value | Source |
|----------|-------|--------|
| `VERSION` | e.g. `0.3.0` | Parsed from `backend/pyproject.toml` `version` field; falls back to `VERSION` file at repo root; defaults to `0.0.0` |
| `DATA_DIR` | `~/linkedout-data/` | Hardcoded |
| `CONFIG_DIR` | `~/linkedout-data/config/` | Hardcoded |
| `CLI_PREFIX` | `linkedout` | Hardcoded |
| `AGENT_CONTEXT_PATH` | `~/linkedout-data/config/agent-context.env` | Hardcoded |
| `DB_SCHEMA_SNIPPET` | Full schema reference markdown | Read from `skills/linkedout/schema-reference.md`, with auto-generated header comments stripped. If file is missing, renders a placeholder instructing the user to run `bin/generate-schema-ref`. |

### B3: Host Configuration

Each host is defined by a YAML file in `skills/hosts/`. Required fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Host identifier (e.g. `claude`, `codex`, `copilot`) |
| `display_name` | string | Human-readable name (e.g. `Claude Code`, `Codex`, `GitHub Copilot`) |
| `skill_install_path` | string | Where skills are installed on the user's machine |
| `local_skill_path` | string | Relative path from the project root to skills (used in routing file) |
| `output_dir` | string | Directory under `skills/` for generated output (defaults to `name`) |
| `frontmatter` | object | Frontmatter processing rules (see B4) |
| `path_rewrites` | list | Find-and-replace rules for path strings (see B5) |
| `tool_rewrites` | object | Tool name remapping (see B5) |

Host-specific variables added on top of global context: `HOST_NAME`, `DISPLAY_NAME`, `SKILL_INSTALL_PATH`, `LOCAL_SKILL_PATH`.

The three configured hosts are:

**Claude Code** (`claude.yaml`):
- Output dir: `claude-code`
- Install path: `~/.claude/skills`
- Local path: `.claude/skills`
- Frontmatter: denylist mode, no fields stripped, no description limit
- No path or tool rewrites

**Codex** (`codex.yaml`):
- Output dir: `codex` (default)
- Install path: `~/.agents/skills`
- Local path: `.agents/skills`
- Frontmatter: allowlist mode, keeps only `name` and `description`, description truncated to 200 characters
- Path rewrites: `.claude/skills/` -> `.agents/skills/`
- Tool rewrites: `AskUserQuestion` -> `input`

**GitHub Copilot** (`copilot.yaml`):
- Output dir: `copilot` (default)
- Install path: `~/.github/skills`
- Local path: `.github/skills/linkedout`
- Frontmatter: denylist mode, no fields stripped, no description limit
- Path rewrites: `.claude/skills/` -> `.github/skills/`
- No tool rewrites

### B4: Frontmatter Processing

`process_frontmatter()` in `skills/lib/frontmatter.py` filters YAML frontmatter according to per-host rules. The frontmatter block is delimited by `---\n` at the start of the file.

Two modes:

- **Denylist** (Claude Code, Copilot): starts with all fields and removes those listed in `strip_fields`. Currently no fields are stripped for either host, so the full frontmatter (name, description, tools, version) passes through.
- **Allowlist** (Codex): keeps only fields listed in `keep_fields`. Codex keeps only `name` and `description`, stripping `tools`, `version`, and any other fields. This produces minimal frontmatter since Codex has its own tool discovery mechanism.

`description_limit` (Codex only, set to 200): truncates the `description` field to the specified character count.

### B5: Path and Tool Rewrites

After template rendering and frontmatter processing, two rewrite passes are applied:

**Path rewrites** replace platform-specific directory conventions. Templates are authored with Claude Code paths (`.claude/skills/`). Codex rewrites to `.agents/skills/`; Copilot rewrites to `.github/skills/`.

**Tool rewrites** rename tool references for platforms with different tool names. Codex maps `AskUserQuestion` to `input`. Claude Code and Copilot have no tool rewrites.

Rewrites are simple string replacement across the entire rendered content.

### B6: Routing File

The routing template (`skills/routing/ROUTING.md.tmpl`) renders into the top-level catalog file for each host:

| Host | Output file | Purpose |
|------|------------|---------|
| Claude Code | `skills/claude-code/CLAUDE.md` | Claude Code reads `CLAUDE.md` for project instructions and skill discovery |
| Codex | `skills/codex/AGENTS.md` | Codex reads `AGENTS.md` for agent definitions |
| Copilot | `skills/copilot/COPILOT.md` | Copilot reads `COPILOT.md` for skill catalog |

The routing file lists all 7 available skills with:
- Skill name and slash-command (e.g. `/linkedout`)
- One-line description of when to invoke the skill
- Trigger patterns (natural language phrases that should activate the skill)
- Skill path (platform-specific path to the SKILL.md file)

The Copilot routing file includes an additional beta notice: "GitHub Copilot support is experimental."

### B7: Build Pipeline

Two scripts drive the build:

**`bin/generate-skills`**: Discovers all `.tmpl` files under `skills/`, renders them for every host in `skills/hosts/*.yaml`, and writes output to the per-host directories. Supports `--check` mode for CI (exits 1 if any generated file has drifted from the expected output). The pipeline per file: load template -> merge host + global variables -> resolve conditionals -> resolve variables -> split frontmatter -> process frontmatter per host rules -> rejoin -> apply path rewrites -> apply tool rewrites -> prepend generated-file header -> write.

**`bin/generate-schema-ref`**: Imports `build_schema_context()` from `backend/src/linkedout/intelligence/schema_context.py` and writes the DB schema reference to `skills/linkedout/schema-reference.md`. This file is then included in the `/linkedout` skill via the `{{DB_SCHEMA_SNIPPET}}` variable. If the backend module cannot be imported (e.g. dependencies not installed), the script exits gracefully without overwriting any existing file.

All generated files include a `<!-- Generated by bin/generate-skills -- do not edit -->` header.

### B8: SKILL.md Format

Each skill template contains YAML frontmatter and a markdown body. The frontmatter fields are:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Skill identifier, matches the directory name (e.g. `linkedout`, `linkedout-setup`) |
| `description` | Yes | One-line description of the skill's purpose |
| `tools` | No | List of tools the skill requires (e.g. `Bash`, `Read`, `Write`, `Grep`, `Agent`) |
| `version` | No | Skill version string (e.g. `1.0.0`) |

The markdown body follows a consistent structure across skills:
1. **Title line** -- `# /skill-name -- Subtitle` format
2. **Overview paragraph** -- what the skill does
3. **Preamble** -- credential loading (`source ~/linkedout-data/config/agent-context.env`) and system health checks
4. **Operational sections** -- step-by-step instructions, SQL queries, CLI commands, or interactive flows
5. **Output formatting rules** -- how to present results (tables, stat lines, JSON)
6. **Follow-ups** -- suggested next queries or actions

### B9: Bootstrap Installation (`./setup`)

The `setup` script at the repo root is a pure-bash bootstrap that makes skills available to AI coding assistants immediately after cloning. It runs before any Python dependencies are installed -- no pip, no PyYAML, no backend code required.

**User flow:** `git clone` -> `cd linkedout-oss` -> `./setup` -> `claude` -> `/linkedout-setup` works.

**Host detection:** Checks for platform config directories in `$HOME`: `~/.claude/` (Claude Code), `~/.agents/` (Codex), `~/.github/` (Copilot). Only detected platforms get skills installed.

**Installation method:** Creates symlinks from the generated output directories (`skills/claude-code/<skill>/`) to each platform's skill directory (`~/.claude/skills/<skill>/`). Skills are direct children of the skills directory, matching the convention used by other skill providers (e.g., gstack). Also symlinks the routing file (e.g., `CLAUDE.md`) into the same skills directory.

**Symlink behavior:** If a symlink already points to the correct target, it is skipped (idempotent). If a non-symlink file exists at the target path, it is skipped with a warning. Symlinks mean skills auto-update on `git pull` without re-running `./setup`.

**Check mode:** `./setup --check` verifies all expected symlinks exist without creating any. Exits 0 if all installed, 1 if any are missing. Suitable for CI.

**Interaction with `skill_install.py`:** The setup orchestrator's skill installation step (`skill_install.py`) copies files rather than symlinking. When `./setup` has already created symlinks, `install_skills_for_platform()` detects that destination files resolve to the same source (`dst.resolve() == src_file.resolve()`) and skips the copy to prevent `SameFileError`. It reports "Already installed via symlinks" in this case.

## Skills Catalog

### /linkedout -- Network Query

The primary skill. Handles natural language queries about the user's professional network.

**Tools required:** Bash, Read, Grep, Agent

**Preamble:** Sources `agent-context.env` for `DATABASE_URL` and RLS identity variables. Runs `linkedout status --json` to verify connectivity and profile count.

**Query routing** classifies requests into three strategies:
- **Structured lookups** -- SQL via `psql` for company, role, location, skill, funding, and past-experience queries. Resolves company aliases via `company_alias` table and role aliases via `role_alias` table.
- **Semantic search** -- generates a query embedding via `linkedout embed --query`, then runs pgvector cosine distance search against `embedding_nomic` (768d, nomic-embed-text-v1.5) or `embedding_openai` (1536d, text-embedding-3-small) depending on the configured provider.
- **Complex intelligence** -- combines structured and semantic approaches, cross-references results, ranks by affinity score, and explains reasoning.

**Host-specific behavior:** Claude Code gets a "Parallel Query Execution" section (using the Agent tool for concurrent lookups). This section is excluded from Codex and Copilot via `{{#if HOST_NAME == "claude"}}`.

**Schema reference** is injected via `{{DB_SCHEMA_SNIPPET}}` -- a comprehensive listing of 10 tables (crawled_profile, connection, experience, education, company, company_alias, profile_skill, role_alias, funding_round, startup_tracking) with all columns, types, and business rules.

**Output formatting:** Table format for lists, rich single-person summaries, "Why this person" explanations for semantic results. Always shows total result count and suggests 2-3 follow-up queries.

**Query logging:** After each query execution and result formatting, the skill calls `linkedout log-query "<query_text>" --type <type> --results <count>` to record the query. Logs `query_text`, `query_type` (company_lookup, person_search, semantic_search, network_stats, general), and `result_count` to daily JSONL files at `~/linkedout-data/queries/YYYY-MM-DD.jsonl`. If the CLI command fails (LinkedOut not installed), logging is skipped silently -- logging failure never interrupts the user's query.

**Graceful degradation:** The preamble handles degraded states:
- If `agent-context.env` does not exist but `linkedout status --json` succeeds: warns "Running without agent-context.env" and continues with limited features.
- If 0 profiles: "Your network is empty. Run `/linkedout-setup` to import your connections."
- If profiles > 0 but 0 embeddings: "Semantic search unavailable -- run `linkedout embed` first. Structured queries still work."
- If demo mode active: "Running in demo mode with sample data."

**Config reference:** Uses `linkedout config show --json` to check embedding provider, with fallback to "local" if command unavailable.

### /linkedout-setup -- First-Time Setup

Guides users through initial LinkedOut installation.

**Tools required:** Bash, Read, Write

**Steps:** Install Python dependencies -> create PostgreSQL database with pgvector -> run Alembic migrations -> create `agent-context.env` with DATABASE_URL and RLS identity variables -> import LinkedIn CSV connections -> generate embeddings -> verify with `linkedout status` and `linkedout diagnostics`.

**Note:** Marked as manual steps pending Phase 9 interactive setup flow.

### /linkedout-extension-setup -- Chrome Extension Setup

**Experimental disclaimer:** Displays a prominent note at the top: "The Chrome extension is experimental and not thoroughly tested. Core LinkedOut functionality works without the extension."

Six-step interactive flow for setting up the Chrome extension.

**Tools required:** Bash, Read

**Steps:**
1. **Prerequisites check** -- Chrome >= 114 installed, backend config exists, database connected (3 sub-checks)
2. **Download extension** -- detects version via `linkedout version`, downloads zip from GitHub Releases, extracts to `~/linkedout-data/extension/chrome/`, validates `manifest.json`
3. **Sideloading instructions** -- step-by-step guide for `chrome://extensions` Developer mode + Load unpacked. **Waits for user confirmation.**
4. **Start backend** -- `linkedout start-backend --background`, health check at backend URL, handles port conflicts (LinkedOut vs non-LinkedOut processes) and database connection errors. **Dynamic port detection:** Reads the configured backend port via `linkedout config show --json` instead of hardcoding `localhost:8001`. Falls back to 8001 if the config command is unavailable.
5. **Verify connection** -- guides user to open a LinkedIn profile and check the side panel. **Waits for user confirmation.** Provides troubleshooting for "Backend unreachable", empty side panel, and LinkedIn CAPTCHA scenarios.
6. **Summary** -- reports what was set up and how to use it

**Design:** Idempotent (re-running skips completed steps). Includes detailed error messages with specific remediation commands for every failure mode.

### /linkedout-upgrade -- Upgrade

Guides users through upgrading LinkedOut to the latest version.

**Tools required:** Bash, Read

**Dirty-state check:** Before `git pull`, checks `git status --porcelain` for uncommitted changes. If changes exist, warns the user to stash or commit before proceeding.

**Steps:** `git pull` -> `pip install -e "./backend[dev]"` -> `linkedout migrate` -> `linkedout status` + `linkedout diagnostics` -> version check with changelog reference.

**Post-upgrade changelog:** After `git pull`, shows `git log --oneline HEAD@{1}..HEAD` to display what changed. If no commits were pulled, shows "Already up to date."

**Note:** Marked as manual steps pending Phase 10 interactive upgrade flow.

### /linkedout-history -- Query History

Browses past network queries from JSONL log files.

**Tools required:** Bash, Read

**Data source:** Daily JSONL files at `~/linkedout-data/queries/YYYY-MM-DD.jsonl` (populated by `/linkedout` skill's query logging).

**Behavior:**
- If no JSONL files exist: "No query history yet. Your queries are logged automatically when you use `/linkedout`. Try asking a question first!"
- **Default view** -- last 7 days, grouped by session, most recent first. Shows initial query, turn count, total results.
- **Date range filtering** -- parses natural language ("last month", "this week")
- **Text search** -- case-insensitive substring match on `query_text`

**Note:** Query history depends on the `/linkedout` skill's post-query logging. If users run raw `psql` queries outside of `/linkedout`, those are not logged.

### /linkedout-report -- Usage Report

Generates a usage report with 4 sections. Degrades gracefully when data sources are empty.

**Tools required:** Bash, Read

**Sections:**
1. **Network Overview** -- from `linkedout status --json` + `linkedout diagnostics --json`. Profile count, enrichment coverage, embedding coverage, connection count, affinity coverage, company count, funding rounds. Always works after setup.
2. **Query Activity** -- from `~/linkedout-data/queries/*.jsonl`. If no files: "No query history yet -- start with `/linkedout`." If files exist: total queries, queries this week, most common query types, avg results per query, recent sessions.
3. **Import History** -- from `~/linkedout-data/reports/import-csv-*.json`. If no files: "No imports recorded." If files exist: date, row count, breakdown.
4. **System Health Snapshot** -- from `linkedout diagnostics --json`. Health status badge, severity counts, top issues.

**Removed from v2:** Cost tracking section (no data source exists), profile freshness by `enriched_at` (column doesn't exist on the entity; enrichment coverage from diagnostics is used instead).

### /linkedout-setup-report -- System Health

Runs `linkedout diagnostics --json` and presents a scored health assessment. The skill delegates all scoring and issue detection to the CLI -- it does not compute health scores locally.

**Tools required:** Bash, Read

**Steps:**
1. **Run diagnostics** -- `linkedout diagnostics --json` (primary data source), optionally `linkedout status --json` for backend status
2. **Display health badge** -- from CLI's `health_status.badge`: `[HEALTHY]` (0 critical, 0 warning), `[NEEDS ATTENTION]` (0 critical, ≥1 warning), `[ACTION REQUIRED]` (≥1 critical)
3. **Display network summary** -- profile count, enrichment coverage, embedding coverage, connection count, affinity coverage, company count, funding rounds
4. **Display issues** -- sorted by severity (CRITICAL first), each with message and fix command from CLI's `issues` array
5. **Historical comparison** -- reads previous `diagnostic-*.json` (not `setup-report-*`) from `~/linkedout-data/reports/` and computes deltas
6. **Interactive repair** -- if CRITICAL issues found, offers to run each issue's `action` command

**Key change from v2:** Health scoring, issue detection, and the `issues` data structure are now provided by the `diagnostics` CLI command (not computed in the skill). Report filenames are `diagnostic-*` (matching CLI output), not `setup-report-*`.

### /linkedout-dev -- Engineering Principles

A static reference skill (no template, not compiled per-host) that documents LinkedOut's 8 engineering principles for contributors and AI agents.

**Principles documented:**
1. Zero Silent Failures -- every error includes what/why/what-to-do
2. Quantified Readiness -- precise counts, not booleans
3. Operation Result Pattern -- Progress -> Summary -> Failures -> Next steps -> Report path
4. Idempotency & Auto-Repair -- safe to re-run, upserts, `--dry-run` support
5. Structured Logging -- loguru via `get_logger()`, component/operation/correlation_id binding
6. CLI Design -- flat namespace, verb-first, `--json` for machine output
7. Configuration -- three-layer hierarchy (env vars > config.yaml > secrets.yaml > defaults)
8. Testing -- no API keys required, real PostgreSQL in CI, three test tiers

## Decisions

### D1: Templates authored for Claude Code, adapted to other hosts

Templates use Claude Code conventions as the baseline (`.claude/skills/` paths, Claude Code tool names). Other hosts adapt via path rewrites and tool rewrites defined in their YAML config. This keeps the template authoring mental model simple -- write once for Claude Code, the build system handles the rest.

### D2: Codex frontmatter stripped to name + description only

Codex uses allowlist mode keeping only `name` and `description` (description capped at 200 chars). The `tools` field is stripped because Codex has its own tool discovery. This minimizes token overhead in Codex's agent context.

### D3: Generated files have a do-not-edit header

All generated SKILL.md and routing files include `<!-- Generated by bin/generate-skills -- do not edit -->`. This prevents accidental manual edits that would be overwritten on next generation.

### D4: Schema reference generated separately from skills

`bin/generate-schema-ref` runs independently from `bin/generate-skills`. The schema reference requires importing the backend's SQLAlchemy models (heavy dependency), while skill generation only needs YAML and string processing. Separating them allows skill generation to work without backend dependencies installed.

### D5: /linkedout-dev is static, not templated

The engineering principles skill has no host-specific content and does not reference any template variables. It lives as a plain SKILL.md rather than a .tmpl file and is not included in the per-host generated output.

### D6: CI drift detection via --check mode

`bin/generate-skills --check` compares generated files against expected output without writing. CI can run this to ensure templates and generated output stay in sync after template changes.

### D7: Conditional blocks for host-specific content

Rather than maintaining separate template files per host, host-specific content uses inline `{{#if HOST_NAME == "claude"}}` blocks. Currently used for the parallel query execution section in `/linkedout`, and the Copilot beta notice in the routing file.

### D8: Skills use CLI commands as building blocks

Skills do not access the database or backend APIs directly. They invoke `linkedout` CLI commands (`status`, `diagnostics`, `embed`, `config show`) and `psql` with `$DATABASE_URL`. This keeps skills as thin orchestration layers on top of deterministic, testable CLI commands.

### D9: Interactive skills wait for user confirmation

`/linkedout-extension-setup` explicitly waits for user responses at steps 3 (sideloading) and 5 (verification). The SKILL.md instructions include "Wait for the user to respond before proceeding" directives and provide troubleshooting branches based on possible user responses.

### D10: Bootstrap script uses symlinks, not copies

`./setup` creates symlinks from the generated output to the platform's skill directory rather than copying files. This means skills auto-update on `git pull` without re-running `./setup`. The trade-off is that skills stop working if the repo is moved or deleted, but this matches the gstack pattern and is the expected behavior for a cloned development repo. The setup orchestrator's `skill_install.py` uses copies (not symlinks) for a different use case -- it runs during `/linkedout-setup` which may be invoked from any working directory.

## Not Included

- **Runtime skill invocation framework** -- there is no code that programmatically dispatches skill execution. Skills are markdown instruction files that AI assistants read and follow. The "routing" is a catalog file the AI reads, not a code-level router.
- **Skill authentication / authorization** -- skills inherit the user's database credentials from `agent-context.env`. No per-skill access control.
- **Skill versioning / upgrade detection** -- skills are versioned in frontmatter but there is no mechanism to detect or prompt for skill updates. Users get updated skills by pulling the repo.
- **Skill telemetry** -- `/linkedout-history` and `/linkedout-report` read from local JSONL files but the skills themselves do not write telemetry. Query logging is a backend/CLI concern.
- **Dynamic skill discovery** -- the skill catalog is statically generated. Adding a new skill requires creating a template, regenerating, and redistributing.
- **Nested conditional blocks** -- the template engine handles sequential conditionals but does not support nesting `{{#if}}` inside another `{{#if}}`.
- **Custom user skills** -- users cannot add their own skills to the catalog without modifying the source templates and regenerating.
