# Skills v2 — Shared Context

## Problem Summary

LinkedOut has 7 skills across 3 platforms. The flagship `/linkedout` query skill works well,
but 3 skills (`/linkedout-setup-report`, `/linkedout-report`, `/linkedout-history`) are
non-functional due to disconnected backend systems and missing query logging. The remaining
skills work but have rough edges.

Root causes:
1. **Diagnostics/readiness disconnect** — Two backend systems (`diagnostics.py`, `readiness.py`)
   that can't see each other's data. Readiness shells out to diagnostics via subprocess.
2. **Query logging never wired** — `query_logger.py` exists and works but nothing calls it.
   Skills use raw `psql` with no logging middleware.
3. **Skills reference non-existent data** — Cost tracking, profile freshness by `enriched_at`,
   query JSONL files that nothing creates.

## Review Decisions (2026-04-10)

These decisions were made during structured plan review and are applied inline in sub-phases:

1. **Query logging UX** — Add `linkedout log-query` CLI command (not Python one-liner in skill).
2. **Issue detection location** — `compute_issues()` lives in `health_checks.py` (shared utility).
3. **Entity errata** — `BuEntity` not `BusinessUnitEntity`; `CompanyEntity` has no `source` column.
4. **Health score -> badge + count** — No numeric 0-100 score. Use badge (HEALTHY / NEEDS_ATTENTION / ACTION_REQUIRED) + severity counts.
5. **DB session passthrough** — Readiness passes its session to `check_db_connection()` / `get_db_stats()`.
6. **E2E smoke test** — Add diagnostics + config smoke to existing e2e harness.
7. **Active empty-state guidance** — Every empty state includes a specific next-step command.

## Key Constraints

### Entity Names & Columns
- `BuEntity` (NOT `BusinessUnitEntity`), `__tablename__ = 'bu'`
- `TenantEntity`, `AppUserEntity` — in `organization/entities/`
- `CompanyEntity` has NO `source` column — use total count
- `CrawledProfileEntity.has_enriched_data` — Boolean, nullable=False, default=False, indexed
- `CrawledProfileEntity.data_source` — String(50), values: 'extension', 'api', 'apify', 'fixture', 'setup'
- `ConnectionEntity.affinity_score` — Float, nullable=True
- `FundingRoundEntity` — import from `linkedout.funding.entities.funding_round_entity`

### System Record IDs
```
SYSTEM_TENANT['id']    = 'tenant_sys_001'
SYSTEM_BU['id']        = 'bu_sys_001'
SYSTEM_APP_USER['id']  = 'usr_sys_001'
SYSTEM_USER_ID         = 'usr_sys_001'
```
Source: `backend/src/dev_tools/db/fixed_data.py`

### CLI Entry Point
- Use `["linkedout", ...]` not `[sys.executable, "-m", ...]`
- Entry point installed by `pip install -e backend/`

### Skill Templates
- Source: `skills/<skill-name>/SKILL.md.tmpl` (mustache-style vars)
- Generated to: `skills/claude-code/<skill-name>/SKILL.md`, `skills/codex/<skill-name>/SKILL.md`, etc.
- After template edits, run `bin/generate-skills` to regenerate all hosts

### health_checks.py Patterns
- Lazy imports inside try/except at function body level
- `get_db_stats()` accepts optional `session` param, creates its own via `cli_db_manager()` if None
- `check_db_connection()` currently has no `session` param — needs one added

## Plan Source
`./docs/plan/2026-04-10-skills-v2.collab.md`

## DAG (Dependency Graph)

```
SP01 (Foundation) ──┬──> SP03 (Setup Report skill)
                    ├──> SP04 (Report skill) ←── SP02a (Query logging)
                    ├──> SP05 (History skill) ←── SP02a (Query logging)
                    └──> SP06 (Flagship polish) ←── SP02b (Config show)
SP02a (Query logging) ──> SP04, SP05
SP02b (Config show) ──> SP06
SP07 (Extension polish) ──> independent
SP08 (Upgrade polish) ──> independent
SP-specs (Spec updates) ──> can run with any phase
All template phases (SP02a, SP03-SP08) ──> SP09 (Regenerate)
```

## Files Modified (Full List)

| File | Sub-phase |
|------|-----------|
| `backend/src/shared/utilities/health_checks.py` | SP01 |
| `backend/src/linkedout/commands/diagnostics.py` | SP01 |
| `backend/src/linkedout/setup/readiness.py` | SP01 |
| `backend/src/linkedout/commands/query_log.py` | SP02a (new) |
| `backend/src/linkedout/commands/config.py` | SP02b |
| `skills/linkedout-setup-report/SKILL.md.tmpl` | SP03 |
| `skills/linkedout-report/SKILL.md.tmpl` | SP04 |
| `skills/linkedout-history/SKILL.md.tmpl` | SP05 |
| `skills/linkedout/SKILL.md.tmpl` | SP06 |
| `skills/linkedout-extension-setup/SKILL.md.tmpl` | SP07 |
| `skills/linkedout-upgrade/SKILL.md.tmpl` | SP08 |
| `docs/specs/cli_commands.collab.md` | SP-specs |
| `docs/specs/skills_system.collab.md` | SP-specs |
| `backend/tests/unit/shared/utilities/test_health_checks.py` | SP01 |
| `backend/tests/unit/linkedout/commands/test_diagnostics.py` | SP01 (new) |
| `backend/tests/linkedout/setup/test_readiness.py` | SP01 |
| `backend/tests/unit/linkedout/commands/test_config.py` | SP02b (new) |
| `backend/tests/unit/linkedout/commands/test_query_log.py` | SP02a (new) |
