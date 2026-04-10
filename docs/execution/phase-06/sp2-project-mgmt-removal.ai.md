# Sub-Phase 2: project_mgmt Domain Removal

**Phase:** 6 — Code Cleanup for OSS
**Plan task:** 6B (project_mgmt Domain Removal)
**Dependencies:** sp1 (auth verification confirms organization/ is load-bearing)
**Blocks:** sp5, sp6, sp7, sp8
**Can run in parallel with:** sp3, sp4

## Objective
Completely remove the `project_mgmt` domain. This was from the original project template and has no place in LinkedOut OSS (Phase 0E decision).

## Context
- Read shared context: `docs/execution/phase-06/_shared_context.md`
- Read plan (6B section): `docs/plan/phase-06-code-cleanup.md`
- Decision Q1: Investigate `common/` before deleting — grep for callers
- Decision Q7: `organization/` is load-bearing — DO NOT REMOVE

## Deliverables

### 1. Pre-Removal Analysis

Before deleting anything, verify scope:

```bash
# Check what imports project_mgmt
grep -rn "from project_mgmt" backend/src/ --include="*.py"
grep -rn "import project_mgmt" backend/src/ --include="*.py"

# Check if common/ has callers outside project_mgmt
grep -rn "from common" backend/src/ --include="*.py" | grep -v project_mgmt
grep -rn "import common" backend/src/ --include="*.py" | grep -v project_mgmt

# Check if agent_run_router is used outside project_mgmt
grep -rn "agent_run" backend/src/ --include="*.py" | grep -v project_mgmt
```

Record findings — they determine what else to clean up.

### 2. Delete `project_mgmt` Source Code

Delete the entire directory:
- `backend/src/project_mgmt/` — all subdirectories and files (~20+ files: label, priority, project, task, project_summary, agents)

### 3. Delete `project_mgmt` Tests

Delete the entire test directory:
- `backend/tests/project_mgmt/` — all test files

### 4. Clean Up `backend/main.py`

Remove all `project_mgmt` imports and router registrations:
- Remove imports: `labels_router`, `priorities_router`, `projects_router`, `tasks_router`, `project_summaries_router`
- Remove `app.include_router(...)` calls for each of the above
- Evaluate `agent_run_router`:
  - If ONLY used by project_mgmt agents → remove it and the import
  - If used by other domains → keep it

### 5. Clean Up `common/` Module

Based on the analysis from step 1:
- If `common/` has NO callers outside `project_mgmt` → delete `backend/src/common/` entirely
- If `common/` HAS callers outside `project_mgmt` → keep it, only remove project_mgmt-specific pieces
- Document what you found and what you decided

### 6. Clean Up Any Remaining References

```bash
# Verify no stale references remain
grep -rn "project_mgmt" backend/src/ --include="*.py"
grep -rn "project_mgmt" backend/tests/ --include="*.py"
```

Fix any remaining import references or type stubs.

### 7. Note: NO Migration in This Sub-Phase

The `project_mgmt` tables will be handled by the fresh baseline migration in sp7. Do NOT create a separate Alembic migration for dropping these tables.

## Verification
1. `backend/src/project_mgmt/` does not exist
2. `backend/tests/project_mgmt/` does not exist
3. `grep -rn "project_mgmt" backend/src/ --include="*.py"` returns zero matches
4. `grep -rn "project_mgmt" backend/tests/ --include="*.py"` returns zero matches
5. `cd backend && uv run python -c "from main import app; print('main.py imports OK')"` succeeds
6. `cd backend && uv run ruff check src/` has no new errors from this change (pre-existing errors OK)
7. If `common/` was kept: document why in a comment at the top of `common/__init__.py`

## Notes
- Do NOT remove `organization/` — it is load-bearing (Decision Q7).
- The `project_mgmt` Alembic migration files in `backend/migrations/versions/` will be deleted as part of sp7 (fresh baseline migration). Don't touch migrations here.
- If `common/controllers/agent_run_controller.py` is the only file in `common/` and it's only used by project_mgmt, delete the entire `common/` directory.
