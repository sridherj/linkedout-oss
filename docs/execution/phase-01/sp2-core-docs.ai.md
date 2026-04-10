# SP2: Core Documentation (README + CONTRIBUTING)

**Phase:** 01 — OSS Repository Scaffolding
**Sub-phase:** 2 of 5
**Dependencies:** SP1 (LICENSE must exist for cross-references)
**Estimated effort:** ~90 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Create the two most important OSS documentation files: README.md and CONTRIBUTING.md. These are the primary entry points for users and contributors.

**Tasks from phase plan:** 1B, 1C

---

## Required Reading Before Starting

You MUST read these decision docs before writing — they contain specific content requirements:

1. `docs/decision/cli-surface.md` — Full CLI command list (13 user-facing commands), help text format, ASCII logo
2. `docs/decision/env-config-design.md` — Data directory (`~/linkedout-data/`), config system (YAML-based), `LINKEDOUT_` prefix
3. `docs/decision/2026-04-07-embedding-model-selection.md` — Default embedding model is `nomic-embed-text-v1.5`
4. `docs/decision/2026-04-07-skill-distribution-pattern.md` — SKILL.md manifest pattern, gstack reference

---

## Task 1B: README.md

**File to create:** `README.md` (repo root)

### Sections (in order)

1. **Header** — Project name + one-line description + badges
   - Badges: CI status (`sridherj/linkedout-oss`), license (Apache 2.0), Python version (3.12+)
   - Badge URLs reference `sridherj/linkedout-oss` GitHub repo

2. **What is LinkedOut?** — 2-3 sentences
   - AI-native professional network intelligence tool
   - Query your LinkedIn network using natural language via Claude Code / Codex / Copilot skills
   - Local-first, privacy-respecting

3. **Architecture diagram** — Text-based or Mermaid
   - Show: User -> Claude Code Skill -> CLI commands -> PostgreSQL
   - Optional path: Chrome Extension -> Backend API -> PostgreSQL
   - Match the diagram from `_shared_context.md`

4. **Quickstart**
   - Point to `/linkedout-setup` skill as the primary installation mechanism
   - Show: `git clone https://github.com/sridherj/linkedout-oss.git`, then invoke the setup skill
   - Brief mention of what setup does (prereqs, DB, import, embeddings)
   - Do NOT include full installation steps (that's the skill's job)

5. **What you get** — Bullet list of capabilities
   - Natural language network queries
   - Affinity scoring and Dunbar tier classification
   - Company intelligence
   - LinkedIn connections import
   - Optional Chrome extension for LinkedIn crawling

6. **CLI Commands** — Brief table of 13 user-facing commands
   - Source: `docs/decision/cli-surface.md` "Command Inventory" and "New Commands" sections
   - One-line description per command
   - Commands: `import-connections`, `import-contacts`, `compute-affinity`, `embed`, `download-seed`, `import-seed`, `diagnostics`, `status`, `version`, `config`, `report-issue`, `start-backend`, `reset-db`

7. **Project structure** — Brief tree
   - `backend/` — Python/FastAPI backend + CLI
   - `extension/` — Chrome extension (WXT/TypeScript)
   - `skills/` — Cross-platform skill definitions
   - `seed-data/` — Seed data download scripts
   - `docs/` — Documentation and decision records

8. **Contributing** — Link to `CONTRIBUTING.md`

9. **License** — Apache 2.0, link to `LICENSE`

10. **Acknowledgements** — Credit key dependencies
    - FastAPI, pgvector, loguru, nomic-embed-text, WXT, Click, pydantic

### Hard Constraints
- Do NOT include full installation steps (skill handles that)
- Reference `~/linkedout-data/` as the data directory
- Reference `linkedout` CLI namespace (not `rcv2`)
- Do NOT mention Docker
- Do NOT mention web frontend/dashboard
- Do NOT mention Procrastinate or task queues
- Do NOT mention private repos or internal tools

### Verification
- [ ] README renders correctly (valid Markdown)
- [ ] Architecture diagram present (text or Mermaid)
- [ ] All 13 CLI commands listed
- [ ] All internal links resolve (LICENSE, CONTRIBUTING, etc.)
- [ ] No prohibited references (Docker, private repos, internal tools, Procrastinate, dashboard)
- [ ] Badges reference `sridherj/linkedout-oss`

---

## Task 1C: CONTRIBUTING.md

**File to create:** `CONTRIBUTING.md` (repo root)

### Sections (in order)

1. **Development setup**
   - Clone repo
   - Install `uv`: `pip install uv`
   - Install backend deps: `cd backend && uv pip install -r requirements.txt && uv pip install -e .`
   - Dev deps: `uv pip install -r backend/requirements-dev.txt` (once it exists)
   - PostgreSQL setup: Local install, create database (brief — detailed setup is the skill's job)
   - Note: Project uses `uv` for dependency management with `requirements.txt` files

2. **Code style**
   - `ruff` for formatting and linting
   - `pyright` for type checking
   - Settings in `pyproject.toml`
   - Pre-commit hooks deferred to Phase 6 (document that they're coming)

3. **Branch naming**
   - `feat/`, `fix/`, `docs/`, `refactor/` prefixes
   - Example: `feat/import-contacts-icloud`

4. **PR process**
   - Fork -> branch -> PR against `main`
   - PR template checklist (reference `.github/PULL_REQUEST_TEMPLATE.md`)
   - All CI checks must pass
   - One approving review required

5. **Testing**
   - `pytest` for backend, `vitest` for extension
   - Tests must pass without external API keys (mock LLM/API calls)
   - Three tiers: static (ruff, pyright), integration (real DB), installation (nightly)
   - Running tests: `cd backend && pytest tests/ -x`
   - Running lints: `cd backend && ruff check src/ && ruff format --check src/`
   - Running type checks: `cd backend && pyright src/`

6. **Commit messages**
   - Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
   - Scope optional: `feat(import): add iCloud contacts support`

7. **Project structure**
   - `backend/src/linkedout/` — Core domain logic
   - `backend/src/shared/` — Shared utilities (logger, config, models)
   - `backend/src/dev_tools/` — Development tooling
   - `extension/` — Chrome extension (WXT framework)
   - `skills/` — Cross-platform AI skill definitions

8. **Decision documents**
   - How architectural decisions are recorded in `docs/decision/`
   - Link to existing decisions
   - New decisions follow the same pattern

9. **Engineering principles**
   - Link to `/linkedout-dev` skill at `skills/linkedout-dev/SKILL.md` (created in SP3)
   - Brief note: "See the /linkedout-dev skill for detailed engineering standards."

10. **Getting help**
    - GitHub Issues for bug reports
    - GitHub Discussions for questions (link: `https://github.com/sridherj/linkedout-oss/discussions`)

### Hard Constraints
- Reference `linkedout` CLI for example commands (not `rcv2`)
- Reference `~/linkedout-data/` for data directory
- Don't reference internal tools (TaskOS, Langfuse as required, etc.)
- Use `uv` in all dependency install examples
- Link to `skills/linkedout-dev/SKILL.md` (even though it's created in SP3 — the link will resolve after SP3 completes)

### Verification
- [ ] Development setup steps are clear and complete
- [ ] Code style tools (ruff, pyright) specified with commands
- [ ] PR process is unambiguous
- [ ] Testing commands provided
- [ ] Commit message format documented
- [ ] No prohibited references (Docker, private repos, internal tools, `rcv2`)
- [ ] All links use `sridherj/linkedout-oss`

---

## Output Artifacts

Files created in the repo root:
- `README.md`
- `CONTRIBUTING.md`

---

## Post-Completion Check

1. All links in README resolve (LICENSE, CONTRIBUTING.md, etc.)
2. All links in CONTRIBUTING resolve (or will resolve after later sub-phases)
3. No prohibited references in either file
4. README CLI command table matches the 13 commands from `docs/decision/cli-surface.md`
5. Both files use consistent terminology (`~/linkedout-data/`, `linkedout` CLI, `uv`)
