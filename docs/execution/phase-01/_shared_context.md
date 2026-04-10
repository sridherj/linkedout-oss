# Phase 01: OSS Repository Scaffolding — Shared Context

**Project:** LinkedOut OSS
**Phase:** 01 — OSS Repository Scaffolding
**Phase Plan:** `docs/plan/phase-01-oss-scaffolding.md`
**Date:** 2026-04-07

---

## Project Overview

LinkedOut is an AI-native professional network intelligence tool. Users query their LinkedIn network using natural language via Claude Code / Codex / Copilot skills. The primary interface is a skill — no web frontend, no Docker. The backend is a Python/FastAPI app with PostgreSQL + pgvector. An optional Chrome extension enables LinkedIn profile crawling.

**Repo:** `sridherj/linkedout-oss` (GitHub, personal account)
**License:** Apache 2.0
**Monorepo structure:** `backend/` (Python), `extension/` (Chrome/WXT), `skills/`, `seed-data/`, `docs/`

---

## Phase 01 Goal

Make the repo look and feel like a credible open-source project. **No application code changes** — only repo-level files, CI, and OSS hygiene. The repo should pass the "30-second OSS credibility check": license, README, contributing guide, CI, issue templates, code of conduct, security policy.

---

## Key Decision Documents

These decisions constrain all work in this phase. Sub-phase runners MUST read and reference the specific docs listed in their instructions.

| Decision Doc | Key Constraint |
|---|---|
| `docs/decision/cli-surface.md` | `linkedout` CLI namespace (flat, no subgroups). 13 user-facing commands. ASCII logo in help text. |
| `docs/decision/env-config-design.md` | `~/linkedout-data/` as unified data directory. YAML-based config, not `.env`-first. `LINKEDOUT_` prefix for env vars. |
| `docs/decision/logging-observability-strategy.md` | loguru for logging (not structlog). Per-component log files. Operation Result Pattern: Progress -> Summary -> Gaps -> Next steps -> Report path. |
| `docs/decision/queue-strategy.md` | Procrastinate removed. Enrichment runs synchronously. No queue references in any docs. |
| `docs/decision/2026-04-07-data-directory-convention.md` | `~/linkedout-data/` is the default. `LINKEDOUT_DATA_DIR` for overrides. |
| `docs/decision/2026-04-07-embedding-model-selection.md` | `nomic-embed-text-v1.5` is the default local embedding model (not MiniLM). OpenAI optional. |
| `docs/decision/2026-04-07-skill-distribution-pattern.md` | Agent Skills standard (SKILL.md manifest). gstack git-clone + setup script pattern. |

---

## Architecture Summary

```
User
  ├─ Claude Code / Codex / Copilot
  │    └─ /linkedout skill
  │         ├─ Direct psql queries (structured lookups)
  │         └─ CLI commands (import, enrichment, affinity, etc.)
  │              └─ PostgreSQL (local, ~/linkedout-data/db/)
  │
  └─ [Optional] Chrome Extension
       └─ Backend API (localhost:8001, only when extension active)
            └─ PostgreSQL (same DB)
```

---

## Naming & Conventions

- **CLI namespace:** `linkedout` (flat, verb-first, hyphen-separated). Example: `linkedout import-connections`, NOT `linkedout db import-connections`.
- **Data directory:** `~/linkedout-data/` (NOT `~/.linkedout/`)
- **Config:** YAML-based (`~/linkedout-data/config/config.yaml` + `secrets.yaml`)
- **Env var prefix:** `LINKEDOUT_` for LinkedOut-specific vars. Industry-standard names kept as-is (`DATABASE_URL`, `OPENAI_API_KEY`).
- **Logging:** loguru (NOT structlog)
- **Embedding model:** `nomic-embed-text-v1.5` for local, OpenAI optional
- **Dependency management:** `uv` with `requirements.txt` files (NOT poetry, NOT pip-tools)
- **Testing:** pytest (backend), vitest (extension). Three tiers: static (ruff, pyright), integration (real DB), installation (nightly).
- **Branch naming:** `feat/`, `fix/`, `docs/`, `refactor/` prefixes
- **Commit style:** Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)

---

## Absolute Prohibitions (All Sub-Phases)

These MUST NOT appear in any public-facing document:

- No references to private repos (`.`, `<linkedout-fe>`)
- No references to Docker or containerization
- No references to web frontend/dashboard (deferred)
- No references to Procrastinate or task queues
- No references to TaskOS, agent dispatchers, or run tracking
- No references to Langfuse (disabled by default; mention only as optional if relevant)
- No references to internal tools, email addresses, or private infrastructure
- No references to `rcv2` CLI namespace (legacy)
- No references to multi-tenant features, Firebase auth, or service accounts

---

## Resolved Decisions for This Phase

1. **GitHub owner:** `sridherj/linkedout-oss` — replace all `OWNER` placeholders
2. **CoC enforcement contact:** GitHub Security Advisories only (no email)
3. **CI Python versions:** Python 3.12 only in Phase 1 (matrix expansion in Phase 13)
4. **Backend tests in CI:** Ruff + pyright only. Pytest deferred to Phase 6.
5. **Extension tests in CI:** Skipped until Phase 12
6. **PR template:** Yes — `.github/PULL_REQUEST_TEMPLATE.md`
7. **Pre-commit hooks:** Deferred to Phase 6 (document in CONTRIBUTING.md, ship config when codebase is clean)
8. **Tooling:** Project uses `uv` and `requirements.txt` — explicit in README, CONTRIBUTING.md, and CI

---

## Project File Structure (Current State)

```
linkedout-oss/
├── .claude/                 # Claude Code config
├── .github/                 # GitHub config (currently empty templates)
├── .gitignore               # Minimal (just `.taskos`)
├── .taskos -> ...           # Symlink to TaskOS goal dir
├── backend/                 # Python/FastAPI backend
│   ├── src/                 # Source code (linkedout/, shared/, dev_tools/)
│   ├── migrations/          # Alembic migrations
│   ├── tests/               # pytest tests
│   ├── pyproject.toml       # CLI entry points
│   ├── requirements.txt     # Python dependencies
│   └── .gitignore           # Backend-specific ignores
├── extension/               # Chrome extension (WXT/TypeScript)
│   ├── entrypoints/         # WXT entry points
│   ├── lib/                 # Shared libraries
│   ├── package.json         # Node dependencies
│   └── wxt.config.ts        # WXT configuration
├── docs/                    # Documentation
│   ├── plan/                # Phase plans
│   └── decision/            # Architecture decision records
├── skills/                  # Cross-platform skill definitions
├── seed-data/               # Seed data scripts
└── plan_and_progress/       # Planning artifacts
```

---

## Sub-Phase Dependency Graph

```
SP1: Foundation Docs (LICENSE, CoC, SECURITY, CHANGELOG, .gitignore)
         │
         ▼
SP2: Core Docs (README.md, CONTRIBUTING.md)
         │
         ▼
SP3: Engineering Principles (/linkedout-dev skill)
         │
         ▼
SP4: GitHub Infrastructure (issue templates, PR template, CI workflow)
         │
         ▼
SP5: SPDX Headers (license headers on all source files)
```

Each sub-phase is independently executable with the inputs from its predecessors.
