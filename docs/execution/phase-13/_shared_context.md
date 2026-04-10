# Shared Context: Phase 13 — Polish & Launch

## Goal

Production-quality v0.1.0 release. Validate that a stranger can discover, install, and use LinkedOut without contacting the maintainer. Comprehensive testing across platforms. Documentation polish. Community readiness.

## Key Artifacts
- **Phase plan (source of truth):** `docs/plan/phase-13-polish-launch.md`
- **CLI surface decision:** `docs/decision/cli-surface.md`
- **Config design decision:** `docs/decision/env-config-design.md`
- **Logging strategy decision:** `docs/decision/logging-observability-strategy.md`
- **Queue strategy decision:** `docs/decision/queue-strategy.md`
- **Data directory convention:** `docs/decision/2026-04-07-data-directory-convention.md`
- **Embedding model decision:** `docs/decision/2026-04-07-embedding-model-selection.md`
- **Skill distribution pattern:** `docs/decision/2026-04-07-skill-distribution-pattern.md`

## Architecture Overview

### LinkedOut System
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

### CLI Commands (13 user-facing)
`import-connections`, `import-contacts`, `compute-affinity`, `embed`, `download-seed`, `import-seed`, `status`, `diagnostics`, `reset-db`, `migrate`, `report-issue`, `version`, `config`

### Test Tiers
| Tier | What | Trigger | Location |
|------|------|---------|----------|
| 1. Static | ruff lint + format + pyright | Every push/PR | `.github/workflows/ci.yml` |
| 2. Integration | pytest with real PostgreSQL | Every push/PR | `.github/workflows/ci.yml` |
| 3. Installation | Full setup flow (Phase 9R suite) | Nightly + release | `.github/workflows/installation-test.yml` |

## Dependencies on Prior Phases

| Phase | What Phase 13 Needs From It |
|---|---|
| Phase 1 (Scaffolding) | CHANGELOG.md, CONTRIBUTING.md, LICENSE, README.md, CI workflows |
| Phase 3 (Logging) | Logging infrastructure, OperationReport, readiness report framework |
| Phase 7 (Seed Data) | Seed pipeline, download/import commands, seed-manifest.json |
| Phase 8 (Skill System) | SKILL.md, skill generation, platform configs |
| Phase 9 (Setup Flow) | /linkedout-setup, installation test suite, readiness reports |
| Phase 10 (Upgrade) | VERSION file, /linkedout-upgrade, migration system |
| Phase 11 (Query History) | Query history tracking, usage reporting |
| Phase 12 (Extension) | Chrome extension, WXT build pipeline |

## Codebase Conventions
- **Build system:** `uv run` for Python commands. Dependencies in `backend/requirements.txt`.
- **ORM:** SQLAlchemy 2.0 with `Mapped[]` type annotations. Alembic for migrations.
- **CLI:** Click commands in `backend/src/dev_tools/`. Flat `linkedout` namespace.
- **Logging:** loguru via `get_logger()`. Bind `component` and `operation` fields.
- **Config:** pydantic-settings. Three-layer hierarchy: env vars > config.yaml > secrets.yaml > defaults.
- **Default data dir:** `~/linkedout-data/` (override via `LINKEDOUT_DATA_DIR`).
- **Embedding model:** nomic-embed-text-v1.5 (768d, ~275MB) for local. OpenAI optional.
- **No Procrastinate.** Enrichment runs synchronously. No worker setup needed.
- **Testing:** pytest (backend), vitest (extension). Three tiers.
- **CI:** GitHub Actions. `uv` for dependency installs.
- **Commit style:** Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)

## Key Decision Constraints

| Decision Doc | Constraint on Phase 13 |
|---|---|
| `docs/decision/cli-surface.md` | All docs use `linkedout <command>` flat namespace. ASCII logo in help text. Operation result pattern verified for every command. |
| `docs/decision/env-config-design.md` | All docs reference `~/linkedout-data/`. Config is YAML-based. `.env.example` shipped for reference. `LINKEDOUT_` env var prefix. |
| `docs/decision/logging-observability-strategy.md` | loguru throughout. Human-readable logs. Per-component log files. 50MB rotation / 30-day retention. JSONL metrics. OperationReport JSON artifacts. |
| `docs/decision/queue-strategy.md` | No Procrastinate references in docs. Enrichment synchronous. No queue tables. |
| `docs/decision/2026-04-07-data-directory-convention.md` | `~/linkedout-data/` default. `LINKEDOUT_DATA_DIR` override. |
| `docs/decision/2026-04-07-embedding-model-selection.md` | Default is `nomic-embed-text-v1.5` (not MiniLM). ~275MB model download. OpenAI optional. |
| `docs/decision/2026-04-07-skill-distribution-pattern.md` | SKILL.md manifest. gstack git-clone + setup script pattern. |

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
| `backend/src/linkedout/cli.py` | CLI commands (Click) |
| `backend/src/shared/config/config.py` | Configuration singleton via pydantic-settings |
| `backend/src/shared/utilities/logger.py` | Logging setup (loguru) |
| `backend/src/dev_tools/cli/` | CLI commands directory |
| `backend/pyproject.toml` | Package config, CLI entry points |
| `.github/workflows/ci.yml` | Tier 1 + 2 CI workflow |
| `tests/installation/` | Phase 9R installation test suite |
| `extension/` | Chrome extension (WXT/TypeScript) |
| `docs/` | User-facing documentation |
| `VERSION` | Version file (from Phase 10) |
| `CHANGELOG.md` | Changelog (from Phase 1) |
| `README.md` | Main project README |
| `CONTRIBUTING.md` | Contributor guide |

## Build Order

```
sp1: Public Roadmap (13G)                          ─── no dependencies
  ↓
sp2: Documentation Polish (13C)                    ─── all user-facing docs
  ↓  (parallel with sp2)
sp3: Test Suite + Observability Validation (13D+13E) ─── validate test infra + logging
  ↓
sp4: Multi-Platform CI + E2E Testing (13A+13B)     ─── CI workflows + e2e tests
  ↓
sp5: Good First Issues (13F)                       ─── after docs are complete
  ↓
sp6: v0.1.0 Release (13H)                         ─── after everything passes
```

## Phase Dependency Summary

| Sub-Phase | Plan Tasks | Depends On | Blocks | Can Parallel With |
|-----------|-----------|-----------|--------|-------------------|
| sp1 | 13G | — | sp5, sp6 | sp2, sp3 |
| sp2 | 13C | — | sp5, sp6 | sp1, sp3 |
| sp3 | 13D, 13E | — | sp4, sp6 | sp1, sp2 |
| sp4 | 13A, 13B | sp3 | sp6 | sp5 |
| sp5 | 13F | sp1, sp2 | sp6 | sp4 |
| sp6 | 13H | sp1-sp5 | — | — |

## Open Questions From Plan

1. **Windows/WSL testing in CI:** Deferred to post-v1. Document WSL instructions but don't gate release on Windows CI.
2. **Seed data hosting:** GitHub Releases for v1. CDN mirror if download speed becomes an issue.
3. **LLM eval tier scope:** Define a small eval set (20-30 queries) but don't gate v0.1.0. Informational quality tracking only.
4. **Announcement channel:** SJ controls timing and messaging. Release workflow does NOT auto-announce.
5. **Extension versioning:** Track repo version. Extension manifest version = repo `VERSION` file.

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When writing CI workflows, release scripts |
| `.claude/skills/pytest-best-practices/SKILL.md` | When configuring test tiers in CI (sp3, sp4) |
| `.claude/skills/docstring-best-practices/SKILL.md` | When polishing documentation (sp2) |

### Agents (sub-phase specific)
| Agent | Sub-Phase | When to Invoke |
|-------|-----------|---------------|
| `.claude/agents/crud-compliance-checker-agent.md` | sp3 (Test Suite Validation) | Run a final compliance check across ALL CRUD stacks to verify the entire codebase is consistent before release |
| `.claude/agents/review-ai-agent.md` | sp3 (Test Suite Validation) | Run a final review of AI agent implementations against their writeups — catch any drift introduced during Phases 2-12 |
| `.claude/agents/integration-test-creator-agent.md` | sp3 (Test Suite Validation) | Verify integration test coverage is complete — all entities have proper test fixtures and seeding |

### Notes
- Phase 13 is the quality gate — the compliance and review agents are most valuable here as a final audit
- sp5 (Good First Issues) and sp6 (v0.1.0 Release) are process tasks — no agent/skill applies
- sp1 (Public Roadmap) is documentation — `docstring-best-practices` style applies to docs as well
