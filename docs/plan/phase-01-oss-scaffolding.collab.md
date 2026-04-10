# Phase 1: OSS Repository Scaffolding — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Ready for implementation
**Phase goal:** Make the repo look and feel like a credible open-source project. No application code changes — only repo-level files, CI, and OSS hygiene.
**Dependencies:** Phase 0 (all 8 spikes resolved and approved)
**Delivers:** A repo that passes the "30-second OSS credibility check" — license, README, contributing guide, CI, issue templates, code of conduct, security policy.

---

## Phase 0 Decisions That Constrain This Phase

| Decision Doc | Constraint on Phase 1 |
|---|---|
| `docs/decision/cli-surface.md` | README quickstart references `linkedout` CLI namespace (flat, no subgroups). Help text format with ASCII logo. 13 user-facing commands. |
| `docs/decision/env-config-design.md` | README and CONTRIBUTING.md reference `~/linkedout-data/` as the data directory. Config is YAML-based, not `.env`-first. `LINKEDOUT_` prefix for env vars. |
| `docs/decision/logging-observability-strategy.md` | `/linkedout-dev` skill must codify the operation result pattern (Progress -> Summary -> Gaps -> Next steps -> Report path), loguru usage, and per-component log files. |
| `docs/decision/queue-strategy.md` | No Procrastinate references anywhere — if queue is mentioned, note it was removed. |
| `docs/decision/2026-04-07-data-directory-convention.md` | `~/linkedout-data/` is the default. `LINKEDOUT_DATA_DIR` for overrides. |
| `docs/decision/2026-04-07-embedding-model-selection.md` | nomic-embed-text-v1.5 is the default local model (not MiniLM). |
| `docs/decision/2026-04-07-skill-distribution-pattern.md` | Agent Skills standard (SKILL.md manifest). gstack git-clone + setup script pattern. |

---

## Task Breakdown

### 1A. LICENSE + NOTICE

**Goal:** Apache 2.0 license with proper NOTICE file as required by Section 4d.

**Files to create:**
- `LICENSE` — Standard Apache 2.0 license text (from apache.org/licenses/LICENSE-2.0.txt)
- `NOTICE` — Required by Apache 2.0 Section 4d

**NOTICE content:**
```
LinkedOut OSS
Copyright 2026 Sridher Jeyachandran

Licensed under the Apache License, Version 2.0.
```

**Acceptance criteria:**
- [ ] `LICENSE` contains the full Apache 2.0 text
- [ ] `NOTICE` contains project name, copyright year, author name
- [ ] `gh repo view` shows "Apache License 2.0" (after push)

**Complexity:** S

---

### 1B. README.md

**Goal:** A README that communicates what LinkedOut is, who it's for, and how to get started — without overwhelming detail. Points to the `/linkedout-setup` skill for actual installation.

**File to create:** `README.md` (repo root)

**Sections:**
1. **Header** — Project name + one-line description + badges (CI status, license, Python version)
2. **What is LinkedOut?** — 2-3 sentences: AI-native professional network intelligence tool. Query your LinkedIn network using natural language via Claude Code / Codex / Copilot skills. Local-first, privacy-respecting.
3. **Architecture diagram** — Text/Mermaid showing: User -> Claude Code Skill -> CLI commands -> PostgreSQL. Optional: Chrome Extension -> Backend API -> PostgreSQL.
4. **Quickstart** — Point to `/linkedout-setup` skill as the primary installation mechanism. Show: `git clone`, then invoke the setup skill. Brief mention of what setup does (prereqs, DB, import, embeddings).
5. **What you get** — Bullet list of capabilities: natural language network queries, affinity scoring, company intelligence, LinkedIn import, optional Chrome extension for crawling.
6. **CLI Commands** — Brief table of the 13 user-facing commands from `docs/decision/cli-surface.md` with one-line descriptions. Link to detailed docs.
7. **Project structure** — Brief tree showing `backend/`, `extension/`, `skills/`, `seed-data/`, `docs/`.
8. **Contributing** — Link to `CONTRIBUTING.md`.
9. **License** — Apache 2.0, link to `LICENSE`.
10. **Acknowledgements** — Credit key dependencies (FastAPI, pgvector, loguru, nomic, WXT).

**Constraints:**
- Do NOT include full installation steps in README (that's the skill's job)
- Reference `~/linkedout-data/` as the data directory (per env-config-design.md)
- Reference `linkedout` CLI namespace (per cli-surface.md)
- Do NOT mention Docker (no Docker in OSS)
- Do NOT mention frontend/dashboard (deferred)

**Acceptance criteria:**
- [ ] README renders correctly on GitHub
- [ ] Architecture diagram is visible (text-based or Mermaid)
- [ ] All links resolve (LICENSE, CONTRIBUTING, etc.)
- [ ] No references to private repos, internal tools, or Docker

**Complexity:** M

---

### 1C. CONTRIBUTING.md

**Goal:** Everything a contributor needs to know: dev setup, code style, PR process, testing.

**File to create:** `CONTRIBUTING.md` (repo root)

**Sections:**
1. **Development setup** — Clone, install `uv` (`pip install uv`), `uv pip install -r backend/requirements.txt`, `uv pip install -e backend/`, `uv pip install -r backend/requirements-dev.txt` (once it exists). PostgreSQL setup reference. Note: project uses `uv` for dependency management with `requirements.txt` files.
2. **Code style** — ruff for formatting and linting, pyright for type checking. Pre-commit hooks. Settings in `pyproject.toml`.
3. **Branch naming** — `feat/`, `fix/`, `docs/`, `refactor/` prefixes.
4. **PR process** — Fork -> branch -> PR against `main`. PR template checklist. Review requirements.
5. **Testing** — `pytest` for backend, `vitest` for extension. Tests must pass without external API keys (mock LLM/API calls). Three tiers: static (ruff, pyright), integration (real DB), installation (nightly).
6. **Commit messages** — Conventional commits style (feat:, fix:, docs:, refactor:, test:, chore:).
7. **Project structure** — Brief overview of `backend/src/` domain-driven structure (linkedout/, shared/, dev_tools/, etc.).
8. **Decision documents** — How architectural decisions are recorded in `docs/decision/`. Link to existing decisions.
9. **Engineering principles** — Link to `/linkedout-dev` skill (task 1K).
10. **Getting help** — Link to GitHub Discussions or Issues.

**Constraints:**
- Reference `linkedout` CLI for any example commands (not `rcv2`)
- Reference `~/linkedout-data/` for data directory
- Don't reference internal tools (TaskOS, Langfuse by default, etc.)

**Acceptance criteria:**
- [ ] A new contributor can follow the setup steps and run tests
- [ ] Code style tools and settings are clearly specified
- [ ] PR process is unambiguous

**Complexity:** M

---

### 1D. CODE_OF_CONDUCT.md

**Goal:** Standard Contributor Covenant for community behavior expectations.

**File to create:** `CODE_OF_CONDUCT.md` (repo root)

**Content:** Contributor Covenant v2.1 (https://www.contributor-covenant.org/version/2/1/code_of_conduct/). Fill in:
- Contact method: GitHub Security Advisories (no email — resolved decision Q2)
- Enforcement: Project maintainers

**Acceptance criteria:**
- [ ] Full Contributor Covenant v2.1 text
- [ ] Contact information filled in
- [ ] Linked from README and CONTRIBUTING

**Complexity:** S

---

### 1E. SECURITY.md

**Goal:** Clear vulnerability reporting process for responsible disclosure.

**File to create:** `SECURITY.md` (repo root)

**Content:**
1. **Supported versions** — Table showing which versions receive security updates (initially just v0.1.x)
2. **Reporting a vulnerability** — Use GitHub Security Advisories (private by default). Do NOT file public issues for security bugs.
3. **Response SLA** — Acknowledge within 72 hours, patch within 30 days for critical.
4. **Scope** — What counts as a security issue (DB credential exposure, data leaks, injection) vs. what doesn't (local-only tool where the user is the only operator).
5. **Security considerations** — Note that LinkedOut is a local-first tool; the threat model assumes the user trusts their own machine. API keys stored in `~/linkedout-data/config/secrets.yaml` with `chmod 600`.

**Acceptance criteria:**
- [ ] Vulnerability reporting process is clear
- [ ] GitHub Security Advisories referenced as the reporting channel
- [ ] Threat model acknowledges local-first architecture

**Complexity:** S

---

### 1F. CHANGELOG.md

**Goal:** Foundation for tracking changes across releases. Initial entry for v0.1.0-dev.

**File to create:** `CHANGELOG.md` (repo root)

**Format:** Keep a Changelog (https://keepachangelog.com/) format.

**Initial content:**
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial open-source repository scaffolding
- Apache 2.0 license
- Contributing guide, code of conduct, security policy
- GitHub Actions CI (lint, type check, test)
- GitHub issue templates
```

**Acceptance criteria:**
- [ ] Follows Keep a Changelog format
- [ ] Has `[Unreleased]` section with initial entries

**Complexity:** S

---

### 1G. .gitignore Overhaul

**Goal:** Comprehensive .gitignore for an OSS Python + TypeScript monorepo. Currently only contains `.taskos`.

**File to modify:** `.gitignore` (repo root)

**Categories to cover:**

1. **Environment & secrets:**
   ```
   .env
   .env.*
   !.env.example
   secrets.yaml
   *.secret
   *.key
   ```

2. **Python:**
   ```
   __pycache__/
   *.py[cod]
   *$py.class
   *.egg-info/
   dist/
   build/
   .eggs/
   *.egg
   .venv/
   venv/
   ```

3. **Node/TypeScript (extension):**
   ```
   node_modules/
   .output/
   .wxt/
   ```

4. **Data files:**
   ```
   *.sqlite
   *.sqlite3
   *.db
   ```

5. **IDE configs:**
   ```
   .idea/
   .vscode/
   *.swp
   *.swo
   *~
   .DS_Store
   ```

6. **Logs & reports (local):**
   ```
   *.log
   logs/
   ```

7. **Testing:**
   ```
   .pytest_cache/
   .coverage
   htmlcov/
   .mypy_cache/
   ```

8. **LinkedOut specific:**
   ```
   .taskos
   ~/linkedout-data/
   ```

**Note:** The `backend/.gitignore` already exists and has its own patterns. The root `.gitignore` should handle repo-wide patterns. Do NOT duplicate what `backend/.gitignore` already covers — verify no conflicts.

**Acceptance criteria:**
- [ ] No `.env*` files can be committed (except `.env.example`)
- [ ] No `__pycache__`, `node_modules`, IDE configs, sqlite files
- [ ] `.taskos` symlink still ignored
- [ ] No conflicts with `backend/.gitignore`

**Complexity:** S

---

### 1H. GitHub Issue Templates

**Goal:** Structured issue templates that guide reporters to provide useful information.

**Files to create:**
- `.github/ISSUE_TEMPLATE/bug-report.yml` — YAML form for bug reports
- `.github/ISSUE_TEMPLATE/feature-request.yml` — YAML form for feature requests
- `.github/ISSUE_TEMPLATE/config.yml` — Disable blank issues, link to discussions

**Bug report template fields:**
1. Description (textarea, required)
2. Steps to reproduce (textarea, required)
3. Expected behavior (textarea, required)
4. Actual behavior (textarea, required)
5. Diagnostic report (textarea, optional) — "Paste output of `linkedout diagnostics`"
6. Environment (dropdown: Linux/macOS/Windows WSL)
7. LinkedOut version (input, required) — "Output of `linkedout version`"
8. Additional context (textarea, optional)

**Feature request template fields:**
1. Problem description (textarea, required) — "What problem does this solve?"
2. Proposed solution (textarea, required)
3. Alternatives considered (textarea, optional)
4. Additional context (textarea, optional)

**config.yml:**
```yaml
blank_issues_enabled: false
contact_links:
  - name: Questions & Discussion
    url: https://github.com/sridherj/linkedout-oss/discussions
    about: Ask questions and discuss LinkedOut
```

**Acceptance criteria:**
- [ ] Bug report form renders on GitHub with all fields
- [ ] Feature request form renders on GitHub with all fields
- [ ] Blank issues are disabled
- [ ] `linkedout diagnostics` output is prompted in bug reports

**Complexity:** S

---

### 1H-b. Pull Request Template (resolved decision Q6)

**Goal:** Standard PR template to guide contributors.

**File to create:** `.github/PULL_REQUEST_TEMPLATE.md`

**Content:**
```markdown
## Summary
<!-- What does this PR do and why? -->

## Test Plan
<!-- How did you verify the changes? -->
- [ ] Tests pass (`cd backend && pytest tests/ -x`)
- [ ] Lint passes (`cd backend && ruff check src/`)
- [ ] Types pass (`cd backend && pyright src/`)

## Checklist
- [ ] SPDX headers on new files
- [ ] No secrets or hardcoded paths
- [ ] CHANGELOG.md updated (if user-facing)
```

**Acceptance criteria:**
- [ ] PR template renders on GitHub when opening a new PR
- [ ] Includes summary, test plan, and checklist sections

**Complexity:** S

---

### 1I. GitHub Actions CI

**Goal:** Automated CI that runs on every PR and push to main. Validates code quality without requiring external API keys.

**File to create:** `.github/workflows/ci.yml`

**Workflow structure:**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install uv
          cd backend
          uv pip install -r requirements.txt
          uv pip install -e .
      - name: Ruff lint
        run: cd backend && ruff check src/
      - name: Ruff format check
        run: cd backend && ruff format --check src/

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install uv
          cd backend
          uv pip install -r requirements.txt
          uv pip install -e .
      - name: Pyright
        run: cd backend && pyright src/

  # NOTE (resolved decision): test-backend (pytest) deferred to Phase 6.
  # Phase 1 CI runs lint + typecheck only. Pytest depends on Procrastinate
  # table removal (Phase 6) — adding it now means fixing tests twice.

  # NOTE (resolved decision): test-extension (vitest) deferred to Phase 12.
  # Extension isn't touched until then — no value in running broken tests
  # for 11 phases.

  # These jobs will be added in their respective phases:
  # test-backend: Phase 6 (task 6H: Test suite green)
  # test-extension: Phase 12

  # Placeholder for future expansion:
  # test-extension:
  #   runs-on: ubuntu-latest
  #   steps:
  #     - uses: actions/checkout@v4
  #     - uses: actions/setup-node@v4
  #       with:
  #         node-version: '20'
  #     - name: Install dependencies
        run: cd extension && npm ci
      - name: Run tests
        run: cd extension && npm test
```

**Key decisions:**
- Uses `pgvector/pgvector:pg16` Docker image for CI PostgreSQL (provides pgvector extension)
- Backend tests run against real PostgreSQL (not mocked) per testing strategy
- No external API keys required — LLM/API calls are mocked in tests
- Extension tests use vitest (already configured in `extension/vitest.config.ts`)
- Separate jobs for lint, typecheck (Phase 1); backend tests added in Phase 6; extension tests added in Phase 12
- Uses `uv` for dependency installation

**Resolved:** Backend pytest and extension vitest are deferred. Phase 1 CI is lint + typecheck only. See resolved decisions Q4 and Q5.

**Acceptance criteria:**
- [ ] CI runs on every PR and push to main
- [ ] All 4 jobs (lint, typecheck, backend tests, extension tests) pass
- [ ] No external API keys needed
- [ ] PostgreSQL with pgvector available for backend tests

**Complexity:** M

---

### 1J. SPDX Headers

**Goal:** Add SPDX license identifiers to all source files, as required for proper Apache 2.0 compliance.

**Files to modify:** All `.py` files in `backend/src/`, all `.ts`/`.tsx` files in `extension/`

**Python format:**
```python
# SPDX-License-Identifier: Apache-2.0
```
Added as the first line of every `.py` file (before existing imports/docstrings).

**TypeScript format:**
```typescript
// SPDX-License-Identifier: Apache-2.0
```
Added as the first line of every `.ts`/`.tsx` file.

**Scope:**
- `backend/src/**/*.py` — all Python source files
- `extension/**/*.ts` and `extension/**/*.tsx` — all TypeScript source files
- Exclude: `__init__.py` files that are empty (0 bytes) — these don't need headers
- Exclude: Generated files (`.egg-info/`, `node_modules/`, `.output/`, `.wxt/`)
- Exclude: Config files (`pyproject.toml`, `package.json`, `tsconfig.json`, etc.)
- Exclude: Test files — add headers but with lower priority

**Implementation approach:**
- Write a script `scripts/add-spdx-headers.py` that:
  1. Finds all `.py`, `.ts`, `.tsx` files in scope
  2. Checks if SPDX header already exists (idempotent)
  3. Prepends the appropriate header
  4. Reports count of files modified
- This script can be reused for future files

**Acceptance criteria:**
- [ ] Every `.py` file in `backend/src/` has SPDX header
- [ ] Every `.ts`/`.tsx` file in `extension/` has SPDX header
- [ ] Script is idempotent (running twice doesn't add duplicate headers)
- [ ] No non-source files modified

**Complexity:** M (many files, but mechanical)

---

### 1K. `/linkedout-dev` Skill (Coding Principles)

**Goal:** A living skill document that codifies LinkedOut's engineering principles for contributors and AI agents. This is the "how we build things here" reference.

**File to create:** `skills/linkedout-dev/SKILL.md`

**Content sections:**

1. **Overview** — This skill defines LinkedOut's engineering standards. Reference it when writing code, reviewing PRs, or building new features.

2. **Zero Silent Failures**
   - Every operation must succeed completely or fail loudly with actionable diagnostics
   - No step in any flow should fail silently
   - Errors must include: what failed, why, what the user can do about it
   - Example pattern from logging-observability-strategy.md

3. **Quantified Readiness (Not Boolean)**
   - "Done" is never a yes/no — it's precise counts
   - Pattern: "3,847/4,012 profiles have embeddings, 156 companies missing aliases"
   - Every major operation produces a readiness report with exact numbers
   - Reports persisted to `~/linkedout-data/reports/`

4. **Operation Result Pattern**
   - Every CLI command output follows: Progress -> Summary -> Failures (with reasons) -> Report path
   - Use the `OperationResult` class (to be built in Phase 3)
   - Commands never exit silently with just "Done"
   - Reference: `docs/decision/cli-surface.md` "Operation Result Pattern" section

5. **Idempotency & Auto-Repair**
   - Every operation must be safe to re-run
   - Re-running a step should fix incomplete state, not corrupt it
   - Pattern: detect gap -> report gap -> offer to fix -> repair -> report results

6. **Structured Logging**
   - Use `get_logger(__name__)` from `shared/utilities/logger.py` (loguru-based)
   - Every log entry binds: `component`, `operation`, `correlation_id`
   - Human-readable log format (no JSON logs — structured data goes to reports/metrics)
   - Per-component log files in `~/linkedout-data/logs/`
   - Reference: `docs/decision/logging-observability-strategy.md`

7. **CLI Design**
   - Flat `linkedout` namespace (no subgroups)
   - `--dry-run` on every write command
   - `--json` where skills need machine-readable output
   - Auto-detection over explicit flags where possible
   - Reference: `docs/decision/cli-surface.md`

8. **Configuration**
   - Three-layer hierarchy: env vars > config.yaml > secrets.yaml > defaults
   - `LINKEDOUT_` prefix for LinkedOut-specific vars
   - Industry-standard names kept as-is (`DATABASE_URL`, `OPENAI_API_KEY`)
   - All config under `~/linkedout-data/` (unified directory)
   - Reference: `docs/decision/env-config-design.md`

9. **Testing**
   - Tests must pass without external API keys
   - Mock LLM/API calls in unit tests
   - Integration tests use real PostgreSQL (pgvector Docker image in CI)
   - Three tiers: static (ruff, pyright), integration (real DB), installation (nightly)

**Constraints:**
- This is a SKILL.md file — it will be consumed by AI agents (Claude Code, Codex, Copilot)
- Keep it actionable and specific (not vague principles)
- Reference decision docs by path for traceability
- Will be linked from CONTRIBUTING.md

**Acceptance criteria:**
- [ ] Skill file exists at `skills/linkedout-dev/SKILL.md`
- [ ] All 8 guiding principles from the high-level plan are covered
- [ ] References specific decision docs
- [ ] Actionable patterns with examples, not just platitudes
- [ ] Linked from CONTRIBUTING.md

**Complexity:** M

---

## Integration Points with Phase 0 Decisions

| Task | Decision Docs Referenced |
|---|---|
| 1B (README) | cli-surface.md (command list), env-config-design.md (data dir), embedding-model-selection.md (nomic default), skill-distribution-pattern.md (SKILL.md manifest) |
| 1C (CONTRIBUTING) | cli-surface.md (CLI namespace), env-config-design.md (config system), logging-observability-strategy.md (testing tiers) |
| 1G (.gitignore) | env-config-design.md (secrets.yaml, .env patterns) |
| 1H (Issue templates) | cli-surface.md (`linkedout diagnostics` for bug reports) |
| 1I (CI) | logging-observability-strategy.md (loguru, not structlog), queue-strategy.md (no Procrastinate deps) |
| 1K (/linkedout-dev) | ALL decision docs (synthesizes engineering principles from all of them) |

---

## Testing Strategy for Phase 1

Phase 1 produces no application code — testing is about verifying OSS hygiene:

1. **CI workflow validation:** Submit a test PR and verify all 4 CI jobs pass
2. **Render check:** Verify README, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT render correctly on GitHub
3. **Issue template check:** Verify templates appear on "New Issue" page
4. **License detection:** `gh repo view` shows Apache License 2.0
5. **SPDX header check:** Script to verify all source files have headers (can be a CI check)
6. **Gitignore check:** Verify `.env`, `secrets.yaml`, `*.sqlite`, `__pycache__` patterns work

---

## Exit Criteria Verification Checklist

- [ ] `gh repo view` shows license as Apache 2.0
- [ ] README renders with architecture diagram, badges, quickstart
- [ ] CONTRIBUTING.md has dev setup, PR process, code style
- [ ] CODE_OF_CONDUCT.md is Contributor Covenant v2.1
- [ ] SECURITY.md has vulnerability reporting process
- [ ] CHANGELOG.md has initial [Unreleased] entry
- [ ] `.gitignore` covers all OSS patterns (env, Python, Node, IDE, data files)
- [ ] GitHub issue templates (bug report + feature request) render as YAML forms
- [ ] Blank issues are disabled
- [ ] CI workflow passes on an empty PR (lint, typecheck, test-backend, test-extension)
- [ ] All `.py` files have `# SPDX-License-Identifier: Apache-2.0`
- [ ] All `.ts`/`.tsx` files have `// SPDX-License-Identifier: Apache-2.0`
- [ ] `/linkedout-dev` skill exists at `skills/linkedout-dev/SKILL.md`
- [ ] CONTRIBUTING.md links to `/linkedout-dev` skill
- [ ] No references to private repos, Docker, or internal tools in any public-facing doc

---

## Task Execution Order

```
1A (LICENSE + NOTICE)  ──┐
1D (CODE_OF_CONDUCT)   ──┤
1E (SECURITY.md)       ──┤── Independent, can all run in parallel
1F (CHANGELOG.md)      ──┤
1G (.gitignore)        ──┘
         ↓
1B (README.md)         ──┐── Depend on LICENSE existing, but can draft in parallel
1C (CONTRIBUTING.md)   ──┘
         ↓
1K (/linkedout-dev)    ──── Depends on CONTRIBUTING (linked from it)
         ↓
1H (Issue templates)   ──┐── Independent of each other
1I (CI workflow)       ──┘
         ↓
1J (SPDX headers)      ──── Last, because CI should be green before mass-modifying files
```

---

## Estimated Effort

| Task | Complexity | Estimate |
|---|---|---|
| 1A. LICENSE + NOTICE | S | ~15 min |
| 1B. README.md | M | ~45 min |
| 1C. CONTRIBUTING.md | M | ~45 min |
| 1D. CODE_OF_CONDUCT.md | S | ~10 min |
| 1E. SECURITY.md | S | ~20 min |
| 1F. CHANGELOG.md | S | ~10 min |
| 1G. .gitignore overhaul | S | ~15 min |
| 1H. GitHub Issue Templates | S | ~30 min |
| 1I. GitHub Actions CI | M | ~60 min (includes debugging CI) |
| 1J. SPDX Headers | M | ~30 min (script + run) |
| 1K. /linkedout-dev skill | M | ~45 min |

**Total estimated effort:** ~5-6 hours

---

## Resolved Decisions (2026-04-07, SJ)

1. **GitHub org/owner:** `sridherj/linkedout-oss` (personal account). Can transfer to org later — GitHub redirects. Replace all `OWNER` placeholders.

2. **CoC enforcement contact:** GitHub Security Advisories only. No email address. Revisit if contributor volume grows.

3. **CI Python versions:** Python 3.12 only in Phase 1. Expand to 3.11/3.12/3.13 matrix in Phase 13.

4. **Backend test suite in CI:** Ruff + pyright only in Phase 1. Pytest deferred to Phase 6 (depends on Procrastinate removal — task 6H).

5. **Extension test suite in CI:** Skip until Phase 12. Extension isn't touched until then.

6. **PR template:** Yes — add `.github/PULL_REQUEST_TEMPLATE.md` in this phase. Standard Summary / Test plan / Checklist template.

7. **Pre-commit hooks:** Defer `.pre-commit-config.yaml` to Phase 6. Document in CONTRIBUTING.md, ship config when codebase is clean.

### Cross-Phase Decisions Affecting This Phase

- **Tooling:** Project uses `uv` and `requirements.txt`. Make this explicit in README, CONTRIBUTING.md, and CI workflows.
- **Repo URL:** Use `sridherj/linkedout-oss` in all issue templates, README badges, CI configs, and SECURITY.md.
