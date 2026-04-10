# SP2: Documentation Polish

**Phase:** 13 — Polish & Launch
**Sub-phase:** 2 of 6
**Dependencies:** None (can run in parallel with SP1 and SP3)
**Estimated effort:** ~2-3 hours
**Shared context:** `_shared_context.md`

---

## Scope

Create comprehensive user-facing documentation in `docs/` that covers the full user journey. A user who reads these guides can solve their own problems without filing an issue. Update `README.md` to link to all guides.

**Tasks from phase plan:** 13C

---

## Task 13C: Documentation Polish

### Overview

Create 6 new documentation files and update README.md. Each document must:
- Render correctly in GitHub markdown
- Use `linkedout` flat CLI namespace (not `rcv2` or subgroups)
- Reference `~/linkedout-data/` as the data directory
- Reference `nomic-embed-text-v1.5` as the default embedding model (not MiniLM)
- Reference `/linkedout-setup` as the primary setup path
- Contain no references to Docker, web frontend, Procrastinate, or internal tools

### Required reading before writing docs

Read these files to ensure docs are accurate:
- `docs/decision/cli-surface.md` — CLI command names and patterns
- `docs/decision/env-config-design.md` — Config layout, env vars, rate limits
- `docs/decision/logging-observability-strategy.md` — Logging conventions, report format
- `docs/decision/2026-04-07-embedding-model-selection.md` — Embedding model details
- `docs/decision/2026-04-07-data-directory-convention.md` — Data directory layout
- `docs/decision/2026-04-07-skill-distribution-pattern.md` — Skill installation
- `README.md` — Current state of README

---

### File 1: docs/getting-started.md

**Sections:**
1. **Prerequisites** — OS (macOS, Ubuntu/Debian), Python 3.11+, PostgreSQL 16+, ~1GB disk, Claude Code / Codex / Copilot
2. **Clone & Setup** — `git clone` -> invoke `/linkedout-setup` skill. What each setup step does. Time estimates.
3. **Your First Query** — Example: "Who do I know at Stripe?" via the `/linkedout` skill. Show expected output format.
4. **What's in your data** — Explain what gets stored in `~/linkedout-data/` and what each directory contains:
   - `config/` — `config.yaml`, `secrets.yaml`, `agent-context.env`
   - `logs/` — Per-component log files
   - `metrics/` — JSONL daily metrics
   - `reports/` — Operation reports (JSON)
5. **Next steps** — Links to querying guide, extension guide, configuration guide.

**Constraints:**
- `/linkedout-setup` is the primary path (not manual CLI steps)
- Show the readiness report output so users know what "done" looks like
- Include cost note: OpenAI embeddings cost ~$0.02/1K connections vs free local nomic (slower, ~275MB download)
- Reference `~/linkedout-data/` (per env-config-design.md)

---

### File 2: docs/querying.md

**Sections:**
1. **How it works** — Skill queries PostgreSQL directly via SQL. Explain queryable data: connections, companies, experience, education, skills, affinity scores.
2. **Example queries** — 10-15 natural language examples with expected result types:
   - "Who do I know at Series B AI startups?"
   - "Find people who went to Stanford and work in ML"
   - "Who are my strongest connections at Google?"
   - "Show me people who changed jobs in the last 6 months"
   - "What companies do my connections work at most?"
   - "Find connections in San Francisco working at startups"
   - "Who has skills in machine learning or data science?"
   - "Show my top Dunbar tier 1 connections"
   - "Companies with the most connections in my network"
   - "Recent profile updates from my network"
3. **Understanding results** — Explain affinity scores, Dunbar tiers, embedding similarity
4. **Tips** — How to get better results (import more connections, compute affinity, generate embeddings)

---

### File 3: docs/extension.md

**Sections:**
1. **What it does** — LinkedIn profile crawling via the Chrome extension (optional enrichment source)
2. **Setup** — Link to `/linkedout-extension-setup` skill, Chrome sideloading instructions:
   - Navigate to `chrome://extensions`
   - Enable "Developer mode"
   - Click "Load unpacked" and select the built extension directory
3. **Usage** — Side panel, profile cards, how data flows back to PostgreSQL
4. **Rate limiting** — 30 requests/hour, 150 requests/day (from env-config-design.md). Explain why: LinkedIn TOS compliance, account safety
5. **Troubleshooting** — Common extension issues:
   - Extension not loading (developer mode, manifest errors)
   - Backend not running (start with `linkedout serve` or however it starts)
   - Voyager API changes (extension logs, fallback behavior)
   - Side panel not appearing

---

### File 4: docs/upgrading.md

**Sections:**
1. **Check for updates** — How update notifications work (1h throttle, non-blocking)
2. **Upgrade** — `/linkedout-upgrade` skill, step-by-step:
   - `git pull` latest
   - `uv pip install` updated dependencies
   - `linkedout migrate` for database schema changes
   - Verify with `linkedout status`
3. **What's New** — Where to find CHANGELOG.md, how version info displays
4. **Rollback** — What to do if an upgrade breaks something:
   - `git checkout <previous-tag>`
   - `linkedout migrate` handles forward/backward
   - Check `~/linkedout-data/logs/` for errors

---

### File 5: docs/troubleshooting.md

**Sections:**
1. **Setup problems**
   - PostgreSQL won't install / not running / wrong version
   - pgvector extension missing
   - Python version too old
   - Permission errors on `~/linkedout-data/`
   - `secrets.yaml` permission issues (should be `chmod 600`)
2. **Import problems**
   - CSV format not recognized (must be LinkedIn export format)
   - Duplicate profiles on re-import (idempotent by design)
   - Missing company data (run seed import)
3. **Embedding problems**
   - nomic model download fails (check disk space, ~275MB needed)
   - OpenAI key invalid or rate limited
   - Embeddings taking too long (local nomic is CPU-intensive)
4. **Query problems**
   - Zero results (check: data imported? embeddings generated? affinity computed?)
   - Slow queries (check: HNSW indexes present? run `linkedout diagnostics`)
5. **Extension problems**
   - Backend not running
   - Extension not connecting (check port 8001, CORS settings)
   - Voyager API errors (LinkedIn may have changed their internal API)
6. **Getting help**
   - `linkedout diagnostics` for automated health checks
   - `linkedout report-issue` or manually file issue with readiness report attached
   - Link to GitHub issues

---

### File 6: docs/configuration.md

**Sections:**
1. **Overview** — Three-layer config precedence: env vars > config.yaml > secrets.yaml > defaults
2. **File locations**
   - `~/linkedout-data/config/config.yaml` — Main config
   - `~/linkedout-data/config/secrets.yaml` — API keys (chmod 600)
   - `~/linkedout-data/config/agent-context.env` — Auto-generated for AI skills
3. **Complete reference** — Table of every config variable from `docs/decision/env-config-design.md`:
   - Name, default, type, description
   - Read the decision doc carefully to populate this table accurately
4. **Examples** — Common config changes:
   - Switch embedding provider (local nomic vs OpenAI)
   - Change log level
   - Adjust rate limits (extension crawling)
   - Override data directory via `LINKEDOUT_DATA_DIR`
5. **For CI/automation** — Using env vars (with `LINKEDOUT_` prefix) instead of YAML files

---

### README.md Updates

**File to modify:** `README.md`

Add a "Documentation" or "Guides" section linking to all 6 docs:
- [Getting Started](docs/getting-started.md)
- [Querying Your Network](docs/querying.md)
- [Chrome Extension](docs/extension.md)
- [Upgrading](docs/upgrading.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Configuration Reference](docs/configuration.md)

Verify the quickstart section in README is still accurate.

---

## Verification

- [ ] All 6 doc files exist in `docs/`
- [ ] Every doc renders correctly in GitHub markdown
- [ ] No broken links between docs
- [ ] README links to all 6 guides
- [ ] No references to Docker, web frontend, Procrastinate, or deprecated config patterns
- [ ] All CLI command examples use `linkedout` flat namespace
- [ ] Data directory is `~/linkedout-data/` everywhere (not `~/.linkedout/`)
- [ ] Embedding model is `nomic-embed-text-v1.5` (not MiniLM)
- [ ] No email addresses, internal tools, or private repo references
- [ ] Config reference table matches `docs/decision/env-config-design.md`

---

## Output Artifacts

- `docs/getting-started.md` (new)
- `docs/querying.md` (new)
- `docs/extension.md` (new)
- `docs/upgrading.md` (new)
- `docs/troubleshooting.md` (new)
- `docs/configuration.md` (new)
- `README.md` (modified)

---

## Post-Completion Check

1. Cross-link audit: every doc that references another doc uses a working relative link
2. No references to private repos, Docker, internal tools, or email addresses
3. CLI examples all use `linkedout <command>` format (never `rcv2` or subgroup syntax)
4. Readiness report and diagnostics output examples are realistic
