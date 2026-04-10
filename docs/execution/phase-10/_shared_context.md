# Phase 10: Upgrade & Version Management — Shared Context

## Project Overview

LinkedOut OSS is being open-sourced as a self-installable, AI-native professional network intelligence tool. The primary interface is a Claude Code / Codex / Copilot skill — no web frontend, no Docker.

## Phase 10 Goal

Users can stay current with one command. The upgrade flow handles code updates, database migrations, extension updates, config changes, and version migration scripts — all through `/linkedout-upgrade` or the `auto_upgrade` config flag.

## Phase Dependencies

- **Phase 9 (Setup Flow)** must be complete before this phase
- **Phase 8 (Skill System)** provides skill infrastructure used here
- **Phase 3 (Logging & Observability)** provides logging patterns and `OperationReport` format
- **Can run in parallel with:** Phase 11 (Query History), Phase 12 (Chrome Extension)

## Key Phase 0 Decisions

These decisions constrain all sub-phases. Read the full docs for details.

| Decision | Key Constraint | Document |
|----------|---------------|----------|
| CLI Surface | Flat `linkedout` namespace. `linkedout version` and `linkedout migrate` are relevant commands. `migrate` is internal-only (not in `--help`). | `docs/decision/cli-surface.md` |
| Config & Env | Everything under `~/linkedout-data/`. Config: `~/linkedout-data/config/config.yaml`. State: `~/linkedout-data/state/`. Reports: `~/linkedout-data/reports/`. Logs: `~/linkedout-data/logs/`. | `docs/decision/env-config-design.md` |
| Logging | Loguru with human-readable format. Operation result pattern: Progress → Summary → Gaps → Next steps → Report path. Per-component log files. JSONL metrics in `~/linkedout-data/metrics/`. | `docs/decision/logging-observability-strategy.md` |
| Queue Strategy | No Procrastinate queue. Upgrades run synchronously. | `docs/decision/queue-strategy.md` |

## Design Gate

**GATE: Before ANY implementation begins, `docs/design/upgrade-flow-ux.md` must be produced and approved by SJ.**

This is handled in sub-phase 01. All implementation sub-phases (02+) are blocked until the design gate is cleared.

## Open Questions (Resolved as Recommendations)

These were listed as open in the plan; treat the recommendations as decided unless SJ overrides:

1. **Vendored copy upgrade:** Support only git clone in v1
2. **Version migration scripts:** Python with `migrate(config)` signature
3. **GitHub API auth:** Unauthenticated for v1, document `GITHUB_TOKEN` env var as optional
4. **Extension version coupling:** Same version for v1 (released together)
5. **Rollback mechanism:** Manual rollback instructions in v1 (no automated `linkedout rollback`)
6. **Dirty working tree:** Refuse to upgrade with clear message

## Directory Layout

```
linkedout-oss/
├── VERSION                                    # Semver string (e.g., 0.1.0)
├── CHANGELOG.md                               # Keep a Changelog format
├── backend/
│   ├── src/linkedout/
│   │   ├── version.py                         # Version reading utility
│   │   └── upgrade/
│   │       ├── __init__.py
│   │       ├── update_checker.py              # GitHub Release check, caching, snooze
│   │       ├── upgrader.py                    # Core upgrade orchestration
│   │       ├── changelog_parser.py            # Parse CHANGELOG.md
│   │       ├── version_migrator.py            # Version migration scripts
│   │       └── extension_updater.py           # Extension zip download
│   └── dev_tools/cli.py                       # CLI commands (modified)
├── migrations/version/                        # Version migration scripts
├── skills/claude-code/linkedout-upgrade/
│   └── SKILL.md                               # /linkedout-upgrade skill
└── docs/design/
    └── upgrade-flow-ux.md                     # UX design doc (Design Gate)
```

## Runtime Files (not in repo)

```
~/linkedout-data/
├── state/
│   ├── update-check.json          # Cached update check result
│   ├── update-snooze.json         # Snooze state
│   └── .last-upgrade-version      # Last successfully upgraded version
├── reports/
│   └── upgrade-*.json             # Upgrade reports
├── metrics/daily/                 # JSONL metrics
├── extension/                     # Downloaded extension zips
└── logs/cli.log                   # CLI log file
```

## Testing Conventions

- Unit tests: `backend/tests/unit/upgrade/test_*.py`
- Integration tests: `backend/tests/integration/upgrade/test_*.py`
- All unit tests run without network access — mock HTTP responses
- Integration tests may use real local PostgreSQL but no external services

## Sub-Phase Execution Order

| Sub-Phase | Task(s) | Description | Blocking Dependencies |
|-----------|---------|-------------|-----------------------|
| 01 | 10A | UX Design Doc (Design Gate) | None — must be first |
| 02 | 10B | VERSION File & Version Utilities | Design Gate approved |
| 03 | 10C | Update Check Mechanism | 02 (needs version utilities) |
| 04 | 10G | Upgrade Logging & Reporting | 02 (needs version info) |
| 05 | 10D | Core `/linkedout-upgrade` Implementation | 02, 03, 04 |
| 06 | 10E | Snooze Support | 03 (extends update checker) |
| 07 | 10F | Extension Upgrade | 05 (integrated into upgrader) |

Note: Sub-phases 03, 04, and 06 can run in parallel where their dependencies are met. Sub-phase 03 and 04 can run in parallel after 02 completes.

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When writing upgrade modules (`update_checker.py`, `upgrader.py`, `version_migrator.py`) |
| `.claude/skills/pytest-best-practices/SKILL.md` | When writing upgrade tests — naming, mocking HTTP responses, fixtures |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating the `backend/src/linkedout/upgrade/` module tree |

### Notes
- Phase 10 is upgrade infrastructure — no new entities, schemas, or CRUD operations
- CRUD agents don't apply
- The design gate (sp1) is a UX document — no agent/skill applies
