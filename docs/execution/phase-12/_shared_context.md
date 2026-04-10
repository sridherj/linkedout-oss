# Phase 12: Chrome Extension Add-on — Shared Context

**Project:** LinkedOut OSS
**Phase:** 12 — Chrome Extension Add-on
**Phase Plan:** `docs/plan/phase-12-extension.md`
**Date:** 2026-04-07

---

## Project Overview

LinkedOut is an AI-native professional network intelligence tool. Users query their LinkedIn network using natural language via Claude Code / Codex / Copilot skills. The primary interface is a skill — no web frontend, no Docker. The backend is a Python/FastAPI app with PostgreSQL + pgvector. An optional Chrome extension enables LinkedIn profile crawling.

**Repo:** `sridherj/linkedout-oss` (GitHub, personal account)
**License:** Apache 2.0
**Monorepo structure:** `backend/` (Python), `extension/` (Chrome/WXT), `skills/`, `seed-data/`, `docs/`

---

## Phase 12 Goal

Make the Chrome extension an optional add-on that users can install after core setup. The extension enables LinkedIn profile crawling via the Voyager API and communicates with the backend API on localhost.

**What this phase delivers:**
1. A pre-built extension zip published as a GitHub Release asset (no Node.js needed for users)
2. A GitHub Actions pipeline that builds and zips the extension on every release
3. An options page for user-configurable settings (backend URL, rate limits, tenant IDs)
4. A `/linkedout-extension-setup` skill that guides users through download, sideloading, and backend startup
5. Backend server lifecycle management (`linkedout start-backend` with daemon mode and health checks)
6. Extension logging integrated with the Phase 3 observability strategy
7. Documentation on Voyager API fragility, rate limits, and troubleshooting

**What this phase does NOT deliver:**
- Chrome Web Store listing (deferred — requires review process)
- Multi-browser support (Firefox, Edge — deferred)
- Extension auto-update mechanism (users re-download zip via `/linkedout-upgrade`)

---

## Key Decision Documents

These decisions constrain all work in this phase. Sub-phase runners MUST read and reference the specific docs listed in their instructions.

| Decision Doc | Key Constraint |
|---|---|
| `docs/decision/cli-surface.md` | `linkedout start-backend` command spec (port, host, --background flags) |
| `docs/decision/env-config-design.md` | Extension config via `browser.storage.local` with `getConfig()` pattern. Backend URL from `VITE_BACKEND_URL` at build time, overridable at runtime. Config YAML for `backend_port`, `backend_host`. Tenant/BU/User IDs from config. |
| `docs/decision/logging-observability-strategy.md` | `devLog()` utility, backend call logging, error badge, no cross-boundary correlation IDs in v1 |
| `docs/decision/queue-strategy.md` | Extension enrichment endpoint blocks synchronously (3-5s per profile). Extension waits for response. Error logged to `~/linkedout-data/logs/`. |
| `docs/decision/2026-04-07-data-directory-convention.md` | Extension zip stored at `~/linkedout-data/extension/`. Backend PID file at `~/linkedout-data/state/backend.pid`. Backend logs at `~/linkedout-data/logs/backend.log`. |

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

**Extension architecture:**
```
LinkedIn Tab                Extension                    Backend (localhost:8001)
┌────────────┐         ┌──────────────┐              ┌───────────────┐
│ Voyager    │◄────────│ content.ts   │              │ FastAPI       │
│ API        │────────►│ (MAIN world) │              │               │
└────────────┘         │              │              │ /crawled-     │
                       │ background.ts│─── fetch ───►│  profiles     │
                       │              │◄── JSON ─────│               │
                       │ side-panel/  │              │ /enrich       │
                       │ (React UI)   │              │               │
                       └──────────────┘              │ /health       │
                                                     └───────────────┘
                                                           │
                                                     ┌─────▼─────┐
                                                     │ PostgreSQL │
                                                     │ (local)    │
                                                     └───────────┘
```

---

## Naming & Conventions

- **CLI namespace:** `linkedout` (flat, verb-first, hyphen-separated). Example: `linkedout start-backend`, NOT `linkedout server start`.
- **Data directory:** `~/linkedout-data/` (NOT `~/.linkedout/`)
- **Config:** YAML-based (`~/linkedout-data/config/config.yaml` + `secrets.yaml`)
- **Env var prefix:** `LINKEDOUT_` for LinkedOut-specific vars. Industry-standard names kept as-is (`DATABASE_URL`, `OPENAI_API_KEY`).
- **Logging:** loguru (NOT structlog)
- **Dependency management:** `uv` with `requirements.txt` files (NOT poetry, NOT pip-tools)
- **Testing:** pytest (backend), vitest (extension)
- **Commit style:** Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- **Extension framework:** WXT (TypeScript, React for UI pages)
- **Minimum Chrome version:** Chrome 114+ (Manifest V3 + sidePanel API)

---

## Absolute Prohibitions (All Sub-Phases)

These MUST NOT appear in any public-facing document or code:

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

1. **Minimum Chrome version:** Chrome 114+, with version check on install. Add a 5-line check that detects Chrome version and shows a clear error ("LinkedOut requires Chrome 114 or later").
2. **Extension distribution:** Ship zip. Skill unzips to `~/linkedout-data/extension/chrome/`, user does "Load unpacked" from there.
3. **Backend auto-start:** Manual `linkedout start-backend` for v1. Extension MUST detect "backend unreachable" and show actionable error messages referencing specific CLI commands or skills.
4. **Extension update flow:** Overwrite fixed path + instruct user to click refresh on `chrome://extensions`. Upgrade skill unzips new version to same path.
5. **`stop-backend` visibility:** User-facing in `--help` as a convenience command. Not part of the 13-command contract.
6. **`start-backend` idempotency:** Detects existing process on port, kills it, then starts fresh. No "address already in use" errors.
7. **Correlation IDs:** Deferred to v2. Not implemented in Phase 12.
8. **ALL error states** must include actionable fix instructions referencing specific CLI commands or skills.

---

## Project File Structure (Current State)

```
linkedout-oss/
├── .github/                 # GitHub config
├── backend/                 # Python/FastAPI backend
│   ├── src/linkedout/       # Source code
│   │   ├── cli/             # CLI commands
│   │   │   ├── cli.py       # Main CLI entry point
│   │   │   └── commands/    # Individual command modules
│   │   ├── api/             # FastAPI routes
│   │   └── ...
│   ├── tests/               # pytest tests
│   ├── pyproject.toml       # CLI entry points
│   └── requirements.txt     # Python dependencies
├── extension/               # Chrome extension (WXT/TypeScript)
│   ├── entrypoints/         # WXT entry points (background, side-panel, content)
│   ├── lib/                 # Shared libraries (backend client, rate-limiter, constants)
│   ├── package.json         # Node dependencies
│   └── wxt.config.ts        # WXT configuration
├── docs/                    # Documentation
│   ├── plan/                # Phase plans
│   ├── decision/            # Architecture decision records
│   └── designs/             # UX design documents
├── skills/                  # Cross-platform skill definitions
│   ├── templates/           # Skill templates
│   ├── claude-code/         # Claude Code specific
│   ├── codex/               # Codex specific
│   └── copilot/             # Copilot specific
└── seed-data/               # Seed data scripts
```

---

## Sub-Phase Dependency Graph

```
SP1: UX Design Doc (12A)                    ← DESIGN GATE: SJ approval required
         │
         ▼
SP2: Extension Build Pipeline (12B)  ───┐
SP3: Options Page + Config (12C)     ───┤── can run in parallel (no deps between them)
SP4: Backend Server Management (12E) ───┤
SP5: Extension Logging (12F)         ───┘
         │
         ▼ (all of SP2-SP5 must complete)
SP6: Extension Setup Skill (12D)
         │
         ▼
SP7: Extension Documentation (12G)
```

Each sub-phase is independently executable with the inputs from its predecessors.

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to backend sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When writing `start-backend` command (SP4), backend server management |
| `.claude/skills/pytest-best-practices/SKILL.md` | When writing backend tests for server lifecycle, extension API integration |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating new backend modules |
| `.claude/skills/mvcs-compliance/SKILL.md` | When modifying backend API endpoints or adding health check routes — layer responsibility rules |

### Agents (sub-phase specific)
| Agent | Sub-Phase | When to Invoke |
|-------|-----------|---------------|
| `.claude/agents/integration-test-creator-agent.md` | SP4 (Backend Server Management) | Reference for integration test patterns when testing `start-backend` lifecycle |

### Notes
- Phase 12 is primarily extension (TypeScript) work — Python agents mostly apply to SP4 (backend server management) and backend-side integration tests
- The extension TypeScript code doesn't have dedicated agents — use standard WXT/React conventions
- The design gate (SP1) is a UX document — no agent/skill applies
