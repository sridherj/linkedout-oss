# Phase 2b Execution Plan — Manifest

**Goal:** linkedin-ai-production
**Phase:** 2b — Startup Pipeline Compatibility
**Source plan:** `.taskos/phase2b_detailed_plan.ai.md`
**Created:** 2026-03-27
**Estimated total effort:** ~23-30h across 8 sub-phases

## Sub-Phases

| # | Name | Steps Covered | Est. Effort | Depends On |
|---|------|---------------|-------------|------------|
| 1 | Pipeline Code Audit | Step 1 | 30 min | — |
| 2 | CRUD Entities | Steps 2a, 2b, 2c | 6-8h | SP-1 |
| 3 | Alembic Migration + Nanoid Utility | Steps 3, 4 | 2.5-3.5h | SP-2 |
| 4 | DB Layer Updates + Integration Tests | Steps 5, 5.5 | 4-6h | SP-3 |
| 5 | Pipeline Discovery Path (Stages 1-4) | Step 6 | 2h | SP-4 |
| 6 | Pipeline News Path + CLI (Stages 5-7) | Steps 7, 8 | 3h | SP-4 |
| 7 | Agent Definition Updates | Steps 9, 10, 11 | 6.5h | SP-4 |
| 8 | Environment Config + E2E Validation | Steps 12, 13 | 1.5-2.5h | SP-5, SP-6, SP-7 |

## Execution Flow (DAG)

```
SP-1 (Audit)
  ↓
SP-2 (CRUD Entities)
  ↓
SP-3 (Alembic + Nanoid)
  ↓
SP-4 (DB Layer + Tests)
  ↓
  ├── SP-5 (Discovery Path)  ──┐
  ├── SP-6 (News Path + CLI) ──┼── SP-8 (Env + E2E)
  └── SP-7 (Agent Updates)  ───┘
```

## Parallelization Rules

- **SP-5, SP-6, SP-7** can run in parallel after SP-4 completes
- **SP-8** requires SP-5, SP-6, and SP-7 to all complete
- Within SP-2, the three CRUD entities (FundingRound, GrowthSignal, StartupTracking) can run in parallel via crud-orchestrator

## Key Artifacts

- **SP-1 output:** SQL audit table (every query → file, line, tables, columns)
- **SP-2 output:** 3 new entity CRUD stacks in `src/linkedout/funding/`
- **SP-3 output:** Alembic migration (7 infra tables) + nanoid utility in pipeline code
- **SP-4 output:** Updated `db.py` + `company_ops.py` + integration tests
- **SP-5 output:** Updated `collect.py`, `extract.py`, `dedup.py`, `promote.py`, `company_matcher.py`
- **SP-6 output:** Updated `news/*.py` + `enrichment/helpers.py`
- **SP-7 output:** Updated agent definitions for `startup-discover`, `startup-enrich`, `startup-pipeline`
- **SP-8 output:** `.env` updates + E2E validation results
