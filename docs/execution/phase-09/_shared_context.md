# Shared Context: Phase 09 — AI-Native Setup Flow

## Goal
A user clones the repo, runs `/linkedout-setup`, and has a fully working system — with a quantified readiness report proving it. This phase delivers the `/linkedout-setup` skill, the `scripts/system-setup.sh` sudo script, the complete onboarding flow, an installation test suite, and a quantified readiness report framework.

## Key Artifacts
- **Phase plan (source of truth):** `docs/plan/phase-09-setup-flow.md`
- **CLI surface decision:** `docs/decision/cli-surface.md`
- **Config design decision:** `docs/decision/env-config-design.md`
- **Logging strategy decision:** `docs/decision/logging-observability-strategy.md`
- **Queue strategy decision:** `docs/decision/queue-strategy.md`
- **Data directory convention:** `docs/decision/2026-04-07-data-directory-convention.md`
- **Embedding model decision:** `docs/decision/2026-04-07-embedding-model-selection.md`
- **Skill distribution pattern:** `docs/decision/2026-04-07-skill-distribution-pattern.md`

## Architecture Overview

### Setup Flow (Target State)
```
User runs /linkedout-setup
  │
  ├── 1. Prerequisites Detection (OS, PostgreSQL, Python, disk)
  │     └── Returns: PlatformInfo, PostgresStatus, PythonStatus
  │
  ├── 2. System Setup (sudo, if needed)
  │     └── scripts/system-setup.sh — installs PostgreSQL, pgvector, pg_trgm
  │
  ├── 3. Database Setup (user-space)
  │     └── Password generation → config.yaml → Alembic migrations → agent-context.env
  │
  ├── 4. Python Environment
  │     └── .venv creation → pip/uv install → CLI entry point verification
  │
  ├── 5. API Key Collection
  │     └── Embedding provider choice → OpenAI key (optional) → Apify key (optional)
  │
  ├── 6. User Profile
  │     └── LinkedIn URL → crawled_profile record → affinity anchor
  │
  ├── 7. LinkedIn CSV Import
  │     └── Guide export → auto-detect CSV → linkedout import-connections
  │
  ├── 8. Contacts Import (optional)
  │     └── Google CSV or iCloud vCard → linkedout import-contacts
  │
  ├── 9. Seed Data
  │     └── linkedout download-seed → linkedout import-seed
  │
  ├── 10. Embedding Generation
  │      └── linkedout embed --provider <choice>
  │
  ├── 11. Affinity Computation
  │      └── linkedout compute-affinity
  │
  ├── 12. Skill Installation
  │      └── Detect platforms → generate-skills → install to platform dirs
  │
  ├── 13. Readiness Check
  │      └── Quantified report: counts, coverage %, gaps, next steps
  │
  └── 14. Gap Detection & Auto-Repair
        └── Offer to fix: missing embeddings, missing affinity, stale data
```

### File Map
```
backend/src/linkedout/setup/
├── __init__.py                # Package init
├── prerequisites.py           # OS/dependency detection (9B)
├── database.py                # DB setup: password, config, migrations (9D)
├── python_env.py              # Venv creation, package install (9E)
├── api_keys.py                # API key collection & validation (9F)
├── user_profile.py            # LinkedIn URL → profile record (9G)
├── csv_import.py              # Guided CSV import flow (9H)
├── contacts_import.py         # Optional contacts import (9I)
├── seed_data.py               # Seed download & import (9J)
├── embeddings.py              # Embedding generation orchestration (9K)
├── affinity.py                # Affinity computation orchestration (9L)
├── readiness.py               # Quantified readiness report (9M)
├── auto_repair.py             # Gap detection & repair (9N)
├── skill_install.py           # Skill detection & installation (9O)
├── logging_integration.py     # Setup-specific logging config (9P)
└── orchestrator.py            # Main orchestrator with step tracking (9Q)

scripts/
└── system-setup.sh            # Minimal sudo script (9C)

docs/design/
└── setup-flow-ux.md           # UX design doc (9A — DESIGN GATE)

tests/installation/
├── conftest.py                # Shared fixtures
├── test_fresh_install.py      # End-to-end smoke test
├── test_prerequisites.py      # Detection tests
├── test_idempotency.py        # Re-run safety tests
├── test_partial_recovery.py   # Interrupted install recovery
├── test_permissions.py        # Security & permission tests
├── test_degraded.py           # Degraded environment tests
└── README.md                  # How to run installation tests
```

## Dependencies on Prior Phases

| Phase | What Phase 9 Needs From It |
|---|---|
| Phase 2 (Env & Config) | `LinkedOutSettings` pydantic-settings class, `~/linkedout-data/` directory layout, config.yaml/secrets.yaml generation, `agent-context.env` generation |
| Phase 3 (Logging & Observability) | `get_logger()` with component binding, `OperationReport` dataclass, readiness report framework, metrics module, setup-specific log file routing |
| Phase 4 (Constants) | All hardcoded values externalized to config. Setup can reference config defaults. |
| Phase 5 (Embedding) | `EmbeddingProvider` ABC, `OpenAIEmbeddingProvider`, `LocalEmbeddingProvider`, `linkedout embed` CLI command, progress tracking & resumability |
| Phase 6 (Code Cleanup) | CLI surface refactored to `linkedout` namespace. Procrastinate removed. `project_mgmt` stripped. Tests green. |
| Phase 7 (Seed Data) | `linkedout download-seed` and `linkedout import-seed` working. Seed manifest on GitHub Releases. |
| Phase 8 (Skill System) | SKILL.md template system, host configs for Claude Code/Codex/Copilot, `bin/generate-skills`, skill installation paths defined |

## Codebase Conventions
- **Build system:** `uv run` for Python commands. Dependencies in `backend/requirements.txt`.
- **ORM:** SQLAlchemy 2.0 with `Mapped[]` type annotations. Alembic for migrations.
- **Entities:** Domain entities in `backend/src/linkedout/<domain>/entities/`. Base class: `BaseEntity`.
- **Services:** Business logic in `backend/src/linkedout/<domain>/services/`.
- **CLI:** Click commands in `backend/src/dev_tools/`. Rewired to `linkedout` namespace.
- **Logging:** loguru via `get_logger()`. Bind `component` and `operation` fields.
- **Config:** pydantic-settings via `backend/src/shared/config/config.py`. Env vars override YAML. Prefix: `LINKEDOUT_`.
- **DB sessions:** `db_session_manager.get_session(DbSessionType.READ|WRITE, app_user_id=...)` context manager.
- **Tests:** pytest in `backend/tests/`. Unit tests mock external APIs. Integration tests use real DB.
- **pgvector:** `pgvector.sqlalchemy.Vector` type for embedding columns. HNSW indexes for search.
- **System user:** `SYSTEM_USER_ID` from `dev_tools.db.fixed_data` for CLI operations.
- **Default data dir:** `~/linkedout-data/` (override via `LINKEDOUT_DATA_DIR`).
- **Embedding model:** nomic-embed-text-v1.5 (768d, ~275MB) for local. OpenAI optional.
- **No Procrastinate.** Enrichment runs synchronously. No worker setup needed.

## Key Decision Constraints

| Decision Doc | Constraint on Phase 9 |
|---|---|
| `docs/decision/cli-surface.md` | Setup invokes flat `linkedout` namespace commands: `import-connections`, `import-contacts`, `embed`, `compute-affinity`, `download-seed`, `import-seed`, `diagnostics`, `status`. No subgroups. |
| `docs/decision/env-config-design.md` | All config under `~/linkedout-data/config/`. Three-layer hierarchy: env vars > config.yaml > secrets.yaml > defaults. `agent-context.env` generated for Claude skills. `DATABASE_URL` in config.yaml (not secrets). `LINKEDOUT_DATA_DIR` overridable. |
| `docs/decision/logging-observability-strategy.md` | Setup logs to `~/linkedout-data/logs/setup.log`. Each step follows operation result pattern: Progress -> Summary -> Gaps -> Next steps -> Report path. loguru with human-readable format. Failed setup produces `setup-diagnostic-*.txt`. |
| `docs/decision/queue-strategy.md` | No Procrastinate. Enrichment runs synchronously. No worker setup needed. |
| `docs/decision/2026-04-07-data-directory-convention.md` | Default `~/linkedout-data/`. Env var override via `LINKEDOUT_DATA_DIR`. |
| `docs/decision/2026-04-07-embedding-model-selection.md` | Default local model is nomic-embed-text-v1.5 (768d, ~275MB). Not MiniLM. OpenAI is the fast alternative (Batch API). |
| `docs/decision/2026-04-07-skill-distribution-pattern.md` | SKILL.md manifest, git-clone + setup script pattern. Skills installed to platform-specific directories. |

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

## Key File Paths

| File | Purpose |
|------|---------|
| `backend/src/shared/config/config.py` | Configuration singleton via pydantic-settings |
| `backend/src/dev_tools/cli/` | CLI commands directory |
| `backend/src/linkedout/import_pipeline/` | Import pipeline (CSV, contacts) |
| `backend/src/linkedout/import_pipeline/converters/linkedin_csv.py` | LinkedIn CSV converter |
| `backend/src/linkedout/intelligence/scoring/` | Affinity scoring logic |
| `backend/pyproject.toml` | Package config, CLI entry points |
| `skills/lib/` | Skill template engine (Phase 8) |
| `skills/hosts/` | Host configs (Phase 8) |
| `bin/generate-skills` | Skill generation script (Phase 8) |
| `docs/decision/cli-surface.md` | CLI command names |
| `docs/decision/env-config-design.md` | Config layout, agent-context.env |
| `docs/decision/logging-observability-strategy.md` | Logging conventions |

## Build Order

```
sp1: UX Design Doc (DESIGN GATE — 9A)
  ↓
sp2: Setup Infrastructure (9P + 9B)           ─── logging + prerequisites
  ↓
sp3: System & Env Setup (9C + 9D + 9E)        ─── sudo script + DB + venv
  ↓
sp4: Configuration Collection (9F + 9G)        ─── API keys + user profile
  ↓
sp5: Data Import Pipeline (9H + 9I + 9J)      ─── CSV + contacts + seed
  ↓
sp6: Computation Steps (9K + 9L)               ─── embeddings + affinity
  ↓
sp7: Readiness, Repair & Skills (9M + 9N + 9O) ── reporting + installation
  ↓
sp8: Setup Orchestrator (9Q)                   ─── ties everything together
  ↓
sp9: Installation Test Suite (9R)              ─── integration tests
```

## Phase Dependency Summary

| Sub-Phase | Plan Tasks | Depends On | Blocks | Can Parallel With |
|-----------|-----------|-----------|--------|-------------------|
| sp1 | 9A | — | sp2-sp9 (DESIGN GATE) | — |
| sp2 | 9P, 9B | sp1 | sp3 | — |
| sp3 | 9C, 9D, 9E | sp2 | sp4 | — |
| sp4 | 9F, 9G | sp3 | sp5 | — |
| sp5 | 9H, 9I, 9J | sp4 | sp6 | — |
| sp6 | 9K, 9L | sp5 | sp7 | — |
| sp7 | 9M, 9N, 9O | sp6 | sp8 | — |
| sp8 | 9Q | sp2-sp7 | sp9 | — |
| sp9 | 9R | sp8 | — | — |

## Open Questions From Plan

1. **WSL detection reliability:** `/proc/version` heuristics may be ambiguous. May need to ask user if detection is unclear.
2. **macOS Homebrew pgvector version matching:** Verify `brew install pgvector` compatibility with `postgresql@16`.
3. **Venv location:** `.venv` in repo root. No `LINKEDOUT_VENV_DIR` override planned — assume repo root is writable.
4. **Skill installation on first clone:** Setup should run `bin/generate-skills` automatically if Phase 8 artifacts exist but generated output doesn't.

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When writing setup modules (`prerequisites.py`, `database.py`, `orchestrator.py`, etc.) |
| `.claude/skills/pytest-best-practices/SKILL.md` | When writing installation tests (sp9) — naming, fixtures, marks |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating the `backend/src/linkedout/setup/` module tree |

### Agents (sub-phase specific)
| Agent | Sub-Phase | When to Invoke |
|-------|-----------|---------------|
| `.claude/agents/integration-test-creator-agent.md` | sp9 (Installation Tests) | Reference for test fixture patterns — session-scoped DB, seeded data, `test_client`, cleanup |

### Notes
- Phase 9 is primarily orchestration code calling existing CLI commands — CRUD agents don't apply
- The installation test suite (sp9) is extensive — use `integration-test-creator-agent` patterns for DB-backed fixtures and `pytest-best-practices` for test organization
- The UX design gate (sp1) is a document, not code — no agent/skill applies
