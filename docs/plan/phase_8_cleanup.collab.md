# Phase 8: Packhouse/Terrantic Cleanup — Detailed Execution Plan

## Goal
Remove all rcm/linkedout domain code, tests, and references now that the new project-management domain is fully in place and verified.

## Pre-Conditions
- Phases 2-7 DONE: All new domain code, auth, tests, agent infra, and ops are in place
- `precommit-tests` passes with project_mgmt domain
- Zero dependency on rcm code from any new code

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- Zero rcm/linkedout references anywhere in the codebase
- `src/rcm/` directory deleted
- All rcm test files deleted
- All imports updated (migrations/env.py, conftest.py, validate_orm.py, verify_seed.py, db_session_manager.py)
- `PackhouseTableName` enum file deleted
- Agent reference files updated (agents that still reference rcm examples point to project_mgmt)
- Clean git history with a single deletion commit

---

## Step 1: Verify No Dependencies on Packhouse

### Check for imports
```bash
grep -rn "from rcm\|import rcm" src/ tests/ --include="*.py" | grep -v "__pycache__" | grep -v "src/rcm/"
```

Any results here are files that still depend on rcm and must be updated first.

### Check for string references
```bash
grep -rn "rcm\|linkedout" src/ tests/ --include="*.py" | grep -v "__pycache__" | grep -v "src/rcm/" | grep -v "tests/rcm/"
```

### Verify
All grep results should be zero (or only in files about to be deleted).

---

## Step 2: Delete Packhouse Source Code

### Directories to delete
- `src/rcm/` (entire directory tree)

### Files to delete
- `src/rcm/common/table_names.py` (created in Phase 2)

---

## Step 3: Delete Packhouse Tests

### Directories to delete
- `tests/rcm/` (entire directory tree)
- `tests/integration/rcm/` (entire directory tree)

---

## Step 4: Update Import Files

### Files that import rcm entities (must be updated):

1. **`migrations/env.py`** — Remove all `import rcm.*` lines
2. **`conftest.py`** (root) — Remove all rcm entity imports (noqa lines)
3. **`src/shared/infra/db/db_session_manager.py`** — Remove `import rcm.entities` lines
4. **`src/dev_tools/db/validate_orm.py`** — Remove rcm entity imports and ALL_ENTITIES entries
5. **`src/dev_tools/db/verify_seed.py`** — Remove rcm entity count checks
6. **`src/dev_tools/db/fixed_data.py`** — Should already be project_mgmt only (Phase 5)
7. **`src/dev_tools/db/seed.py`** — Remove rcm seeder references
8. **`src/shared/test_utils/entity_factories.py`** — Remove rcm factory methods
9. **`src/shared/test_utils/seeders/base_seeder.py`** — Remove rcm ENTITY_ORDER entries and seed methods

---

## Step 5: Update Claude Agents and Skills

### Agents to update (reference paths)
After Phase 8, update these agents to point to project_mgmt examples instead of rcm:

1. **`repository-agent.md`** — `src/rcm/common/repositories/customer_master_repository.py` → `src/project_mgmt/label/repositories/label_repository.py`
2. **`service-agent.md`** — `src/rcm/common/services/customer_master_service.py` → `src/project_mgmt/label/services/label_service.py`
3. **`service-test-agent.md`** — `tests/rcm/` → `tests/project_mgmt/`
4. **`controller-test-agent.md`** — `tests/rcm/` → `tests/project_mgmt/`
5. **`repository-test-agent.md`** — `tests/rcm/` → `tests/project_mgmt/`
6. **`crud-compliance-checker-agent.md`** — All rcm reference paths → project_mgmt paths
7. **`entity-creation-agent.md`** — Packhouse reference entities → project_mgmt entities
8. **`integration-test-creator-agent.md`** — `tests/integration/rcm/` → `tests/integration/project_mgmt/`

---

## Step 6: Clean Up Dev Tools

### Remove rcm-specific CLI commands
- Any remaining rcm planner agent subcommands in `cli.py` (should already be gone after Phase 7)

### Remove rcm planner iterations
- `src/dev_tools/planner_agent_iterations/` — All rcm-specific scenario runners, fixtures, validators, outcomes, and visualizer components

### Remove rcm prompts
- `prompts/planner/` — All rcm planner agent prompts (lot_planner, scheduler, etc.)

---

## Step 7: Generate Fresh Migration

```bash
# Delete all existing migration versions
rm migrations/versions/*.py

# Generate fresh initial migration with only project_mgmt + organization entities
alembic revision --autogenerate -m "Initial schema: organization + project_mgmt"
```

---

## Step 8: Final Verification

```bash
# 1. No rcm/linkedout references anywhere
grep -rn "rcm\|linkedout" src/ tests/ migrations/ --include="*.py" | grep -v "__pycache__"
# Should return 0 results

# 2. All tests pass
pytest tests/ -k "not integration and not live_llm" -x --tb=short

# 3. Integration tests pass
pytest tests/integration/ -x --tb=short

# 4. Full precommit suite
precommit-tests
```

---

## Risks and Mitigations

### Risk 1: Hidden dependencies
**Issue**: Some file may still import from rcm indirectly.
**Mitigation**: The grep checks in Step 1 catch all direct references. Python will fail fast on import errors if anything is missed.

### Risk 2: Test count changes
**Issue**: Deleting rcm tests reduces test count significantly.
**Mitigation**: Phase 5 should have created equivalent project_mgmt tests. Verify test count before and after.

### Risk 3: Migration history
**Issue**: Existing migration files reference rcm tables.
**Mitigation**: Generate a fresh initial migration (Step 7). This is a reference repo, not production — clean migration history is better.

---

## Total Estimated Changes

| Type | Count |
|------|-------|
| Files deleted | ~100+ (all of src/rcm/, tests/rcm/, planner iterations, prompts) |
| Files modified | ~15 (imports, agents, skills) |
| Files created | 1 (fresh initial migration) |
