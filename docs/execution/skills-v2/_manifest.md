# Execution Manifest: Skills v2 — Make Every Interaction Feel Effortless

## How to Execute

Each sub-phase runs in a **separate Claude context**. For each sub-phase:
1. Start a new Claude session
2. Tell Claude: "Read `./docs/execution/skills-v2/_shared_context.md` then execute `./docs/execution/skills-v2/<sub-phase-file>`"
3. After completion, update the Status column below

## Sub-Phase Overview

| # | Sub-phase | File | Depends On | Status | Notes |
|---|-----------|------|-----------|--------|-------|
| 01 | Foundation — Diagnostics + Readiness | `sp01-foundation.ai.md` | -- | Not Started | Backend: health_checks.py, diagnostics.py, readiness.py |
| 02a | Query Logging CLI | `sp02a-query-logging.ai.md` | -- | Not Started | New CLI command + skill template section |
| 02b | Config Show | `sp02b-config-show.ai.md` | -- | Not Started | Replace stub with real implementation |
| 03 | Setup Report Skill Rewrite | `sp03-setup-report-skill.ai.md` | 01 | Not Started | Full skill template rewrite |
| 04 | Report Skill Rewrite | `sp04-report-skill.ai.md` | 01, 02a | Not Started | Full skill template rewrite |
| 05 | History Skill Rewrite | `sp05-history-skill.ai.md` | 02a | Not Started | Simplify to <100 lines |
| 06 | Flagship `/linkedout` Polish | `sp06-flagship-polish.ai.md` | 01, 02b | Not Started | Graceful degradation, config ref, health gate |
| 07 | Extension Setup Polish | `sp07-extension-polish.ai.md` | -- | Not Started | Experimental disclaimer, dynamic port |
| 08 | Upgrade Polish | `sp08-upgrade-polish.ai.md` | -- | Not Started | Dirty-state check, changelog |
| 09 | Regenerate + Validate | `sp09-regenerate-validate.ai.md` | 02a,03-08 | Not Started | `bin/generate-skills` + spot-check |
| specs | Spec Updates | `sp-specs.ai.md` | -- | Not Started | cli_commands v3->v4, skills_system v2->v3 |

Status: Not Started -> In Progress -> Done -> Verified -> Skipped

## Dependency Graph

```
SP01 (Foundation) ──────┬──> SP03 (Setup Report)
                        ├──> SP04 (Report) ←──── SP02a (Query Logging)
                        ├──> SP05 (History) ←─── SP02a
                        └──> SP06 (Flagship) ←── SP02b (Config Show)

SP02a (Query Logging) ──┬──> SP04 (Report)
                        └──> SP05 (History)

SP02b (Config Show) ────────> SP06 (Flagship)

SP07 (Extension) ──────────── independent
SP08 (Upgrade) ────────────── independent
SP-specs ──────────────────── independent (can run with any phase)

All template phases ────────> SP09 (Regenerate + Validate)
```

## Execution Order

**Wave 1 (parallel — no dependencies):**
- SP01: Foundation
- SP02a: Query Logging CLI
- SP02b: Config Show
- SP07: Extension Polish
- SP08: Upgrade Polish
- SP-specs: Spec Updates

**Wave 2 (after SP01 + SP02a complete):**
- SP03: Setup Report Skill (needs SP01)
- SP04: Report Skill (needs SP01 + SP02a)
- SP05: History Skill (needs SP02a)
- SP06: Flagship Polish (needs SP01 + SP02b)

**Wave 3 (after all template changes):**
- SP09: Regenerate + Validate

## Key Files Modified Per Sub-Phase

| File | SP01 | SP02a | SP02b | SP03 | SP04 | SP05 | SP06 | SP07 | SP08 | specs |
|------|------|-------|-------|------|------|------|------|------|------|-------|
| `backend/src/shared/utilities/health_checks.py` | M | | | | | | | | | |
| `backend/src/linkedout/commands/diagnostics.py` | M | | | | | | | | | |
| `backend/src/linkedout/setup/readiness.py` | M | | | | | | | | | |
| `backend/src/linkedout/commands/query_log.py` | | C | | | | | | | | |
| `backend/src/linkedout/commands/config.py` | | | M | | | | | | | |
| `skills/linkedout-setup-report/SKILL.md.tmpl` | | | | M | | | | | | |
| `skills/linkedout-report/SKILL.md.tmpl` | | | | | M | | | | | |
| `skills/linkedout-history/SKILL.md.tmpl` | | | | | | M | | | | |
| `skills/linkedout/SKILL.md.tmpl` | | M | | | | | M | | | |
| `skills/linkedout-extension-setup/SKILL.md.tmpl` | | | | | | | | M | | |
| `skills/linkedout-upgrade/SKILL.md.tmpl` | | | | | | | | | M | |
| `docs/specs/cli_commands.collab.md` | | | | | | | | | | M |
| `docs/specs/skills_system.collab.md` | | | | | | | | | | M |

C = Create, M = Modify

**Test files:**

| Test File | SP01 | SP02a | SP02b |
|-----------|------|-------|-------|
| `backend/tests/unit/shared/utilities/test_health_checks.py` | M | | |
| `backend/tests/unit/linkedout/commands/test_diagnostics.py` | C | | |
| `backend/tests/linkedout/setup/test_readiness.py` | M | | |
| `backend/tests/unit/linkedout/commands/test_query_log.py` | | C | |
| `backend/tests/unit/linkedout/commands/test_config.py` | | | C |

## Progress Log

(Update after each sub-phase)
