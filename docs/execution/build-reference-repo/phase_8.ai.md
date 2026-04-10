# Phase 8: Packhouse/Linkedout Cleanup

## Execution Context
**Depends on**: Phase 7 (all new code in place and verified)
**Blocks**: Nothing — final phase
**Parallel with**: Nothing

## Goal
Remove all rcm/linkedout domain code, tests, and references. The new project-management domain is fully in place and verified — rcm is no longer needed as reference.

## Pre-Conditions
- Phases 2-7 DONE: All new domain code, auth, tests, agent infra, ops in place
- `precommit-tests` passes with project_mgmt domain
- Zero dependency on rcm code from any new code

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- Zero rcm/linkedout references anywhere: `grep -rn "rcm\|linkedout" src/ tests/ migrations/ --include="*.py"` returns 0
- `src/rcm/` directory deleted
- All rcm test files deleted
- All imports updated
- `PackhouseTableName` enum file deleted
- Claude agents/skills updated to point to project_mgmt examples
- Fresh Alembic migration (no rcm tables)

---

## Step 1: Verify No Dependencies on Rcm

```bash
# Check for imports from rcm (excluding rcm itself)
grep -rn "from rcm\|import rcm" src/ tests/ --include="*.py" | grep -v "__pycache__" | grep -v "src/rcm/" | grep -v "tests/rcm/"

# Check for string references
grep -rn "rcm\|linkedout" src/ tests/ --include="*.py" | grep -v "__pycache__" | grep -v "src/rcm/" | grep -v "tests/rcm/"
```

Any results here must be fixed before deletion.

---

## Step 2: Delete Rcm Source Code

```bash
rm -rf src/rcm/
```

This removes:
- All rcm domain entities, repositories, services, controllers, schemas
- `src/rcm/common/table_names.py` (created in Phase 2)
- All rcm planner code (agent implementations)

---

## Step 3: Delete Rcm Tests

```bash
rm -rf tests/rcm/
rm -rf tests/integration/rcm/
```

---

## Step 4: Update Import Files

Files that import rcm entities must be updated:

| File | Action |
|------|--------|
| `migrations/env.py` | Remove all rcm entity imports |
| `conftest.py` (root) | Remove all rcm entity noqa imports |
| `src/shared/infra/db/db_session_manager.py` | Remove rcm entity imports (if any) |
| `src/dev_tools/db/validate_orm.py` | Remove rcm from ALL_ENTITIES |
| `src/dev_tools/db/verify_seed.py` | Remove rcm entity count checks |
| `src/dev_tools/db/fixed_data.py` | Remove rcm fixed data (FIXED_COMMODITIES, etc.) |
| `src/dev_tools/db/seed.py` | Remove rcm seeder references |
| `src/shared/test_utils/entity_factories.py` | Remove rcm create_* methods |
| `src/shared/test_utils/seeders/base_seeder.py` | Remove rcm ENTITY_ORDER entries + seed methods |
| `tests/seed_db.py` | Remove rcm TableName entries + SeedConfig counts |
| `main.py` | Remove rcm router imports |

---

## Step 5: Update Claude Agents and Skills

Update reference paths in `.claude/agents/`:

| Agent | Old Path | New Path |
|-------|----------|----------|
| `repository-agent.md` | `src/rcm/.../customer_master_repository.py` | `src/project_mgmt/label/repositories/label_repository.py` |
| `service-agent.md` | `src/rcm/.../customer_master_service.py` | `src/project_mgmt/label/services/label_service.py` |
| `service-test-agent.md` | `tests/rcm/` | `tests/project_mgmt/` |
| `controller-test-agent.md` | `tests/rcm/` | `tests/project_mgmt/` |
| `repository-test-agent.md` | `tests/rcm/` | `tests/project_mgmt/` |
| `crud-compliance-checker-agent.md` | All rcm refs | project_mgmt refs |
| `entity-creation-agent.md` | Rcm entities | project_mgmt entities |
| `integration-test-creator-agent.md` | `tests/integration/rcm/` | `tests/integration/project_mgmt/` |

---

## Step 6: Clean Up Dev Tools

| Item | Action |
|------|--------|
| `src/dev_tools/planner_agent_iterations/` | Delete entirely (rcm-specific scenarios, fixtures, validators, outcomes, visualizer) |
| `prompts/planner/` | Delete (rcm planner agent prompts) |
| Any remaining rcm CLI commands | Should already be gone after Phase 7 |

---

## Step 7: Generate Fresh Migration

```bash
rm migrations/versions/*.py
alembic revision --autogenerate -m "Initial schema: organization + project_mgmt + agent_run"
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

---

## Step 8: Final Verification

```bash
# 1. No rcm/linkedout references
grep -rn "rcm\|linkedout" src/ tests/ migrations/ --include="*.py" | grep -v "__pycache__"
# Must return 0 results

# 2. Unit tests
pytest tests/ -k "not integration and not live_llm" -x --tb=short

# 3. Integration tests
pytest tests/integration/ -x --tb=short

# 4. Full suite
precommit-tests

# 5. Test count sanity check
# Compare before/after — project_mgmt tests should cover equivalent patterns
```

---

## Files Summary

### Delete (~100+ files)
| Directory/File | Reason |
|----------------|--------|
| `src/rcm/` | Entire rcm domain |
| `tests/rcm/` | Rcm unit tests |
| `tests/integration/rcm/` | Rcm integration tests |
| `src/dev_tools/planner_agent_iterations/` | Rcm-specific eval infra |
| `prompts/planner/` | Rcm agent prompts |
| Old migration files | Reference rcm tables |

### Modify (~15 files)
| File | Change |
|------|--------|
| `migrations/env.py` | Remove rcm imports |
| `conftest.py` | Remove rcm imports |
| `main.py` | Remove rcm router imports |
| `src/dev_tools/db/validate_orm.py` | Remove rcm entities |
| `src/dev_tools/db/verify_seed.py` | Remove rcm checks |
| `src/dev_tools/db/fixed_data.py` | Remove rcm data |
| `src/dev_tools/db/seed.py` | Remove rcm seeders |
| `src/shared/test_utils/entity_factories.py` | Remove rcm factories |
| `src/shared/test_utils/seeders/base_seeder.py` | Remove rcm order + methods |
| `tests/seed_db.py` | Remove rcm entries |
| `.claude/agents/*.md` | Update reference paths |

### Create (1 file)
| File | Description |
|------|-------------|
| `migrations/versions/xxx_initial_schema.py` | Fresh migration |

## Risks
1. **Hidden dependencies**: Some file may still import from rcm indirectly. The grep checks in Step 1 catch direct refs; Python fails fast on import errors for anything missed.
2. **Test count drop**: Deleting rcm tests reduces count significantly. Phase 5 should have created equivalent project_mgmt tests.
3. **Migration history**: Existing migration files reference rcm tables. Fresh initial migration is the right approach for a reference repo.
