# Phase 5b Execution Plan — Manifest

**Goal:** linkedin-ai-production
**Phase:** 5b — Network Dashboard
**Source plan:** `.taskos/phase5b_detailed_plan.ai.md`
**Created:** 2026-03-28
**Estimated total effort:** ~4-6h across 3 sub-phases

## Sub-Phases

| # | Name | Plan Sections | Est. Effort | Depends On |
|---|------|---------------|-------------|------------|
| 1 | Backend: Network Aggregation Endpoints | 1.1–1.5 | 2-3h | — |
| 2 | Backend: Dashboard Tests | 2.1–2.3 | 1h | SP-1 |
| 3 | Frontend: Dashboard Page | 3.1–3.7 | 1-2h | SP-1, Phase 4.5 |

## Execution Flow (DAG)

```
SP-1 (Backend: Aggregation Endpoints)
    │
    ├────► SP-2 (Backend: Tests)
    │
    └────► SP-3 (Frontend: Dashboard Page)
```

## Parallelization Rules

- **SP-1** runs first (no dependencies within this phase)
- **SP-2 and SP-3** can run in parallel after SP-1 completes (no shared files)
- **SP-3** also requires Phase 4.5 (Design System) to be complete — this gate is satisfied per reconciliation item C13

## Critical Path

```
SP-1 → SP-3
```
SP-2 (Tests) is off the critical path and can run in parallel with SP-3.

## Key Artifacts

- **SP-1 output:** `src/linkedout/dashboard/controller.py`, `service.py`, `repository.py`, `schemas.py` — read-only aggregation module with single dashboard endpoint
- **SP-2 output:** `tests/unit/linkedout/dashboard/test_dashboard_service.py`, `test_dashboard_repository.py`, `tests/integration/linkedout/dashboard/test_dashboard_endpoint.py`
- **SP-3 output:** `linkedout-fe/app/dashboard/page.tsx` + component files — dashboard page with 7 widget types + empty state

## Cross-Phase Reconciliation Items

| ID | Item | Affects |
|----|------|---------|
| C5 | `app_user_id` via `X-App-User-Id` header (not URL path) | SP-1 controller endpoint signature |
| C13 | Phase 4.5 Design System complete — gate satisfied | SP-3 can proceed |

## Important Notes

- Dashboard module (`src/linkedout/dashboard/`) is **not CRUD** — it's read-only aggregation. Must be excluded from CRUD compliance checker.
- Frontend code goes to `<linkedout-fe>/` (symlinked at `./linkedout-fe/`).
- Design system at `<linkedout-fe>/docs/design/linkedout-design-system.md`.

## Estimated Total Effort

~4-6 hours across 3 sub-phases. SP-1 is the core backend work (~2-3h). SP-2 and SP-3 can run in parallel after SP-1 (~1-2h each).
