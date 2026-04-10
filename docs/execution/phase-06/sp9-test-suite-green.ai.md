# Sub-Phase 9: Test Suite Green

**Phase:** 6 — Code Cleanup for OSS
**Plan task:** 6H (Test Suite Green)
**Dependencies:** sp6, sp7, sp8 (all code changes complete)
**Blocks:** None (final sub-phase)
**Can run in parallel with:** None

## Objective
Make all tests pass with mocked external services. No real API keys needed. Validate linting, type checking, and the full exit criteria checklist for Phase 6.

## Context
- Read shared context: `docs/execution/phase-06/_shared_context.md`
- Read plan (6H section + Exit Criteria): `docs/plan/phase-06-code-cleanup.md`
- **Agent references:**
  - `.claude/agents/crud-compliance-checker-agent.md` — Run compliance checks on surviving CRUD stacks (organization, crawled_profile, company, etc.) to verify nothing was broken by project_mgmt removal, Procrastinate removal, and CLI refactor
  - `.claude/agents/review-ai-agent.md` — Verify AI agent implementations still work after Langfuse guard changes and import path updates
  - `.claude/agents/integration-test-creator-agent.md` — Reference for test fixture patterns when fixing broken integration tests

## Deliverables

### 1. Collect All Tests

```bash
cd backend && uv run pytest --collect-only 2>&1 | head -100
```

Identify:
- Tests that import from deleted modules (`project_mgmt`, `shared.queue`)
- Tests that unconditionally import `langfuse`
- Tests for enrichment pipeline (need sync flow update)
- Tests for CLI commands (may need updating)

### 2. Fix Import Errors

For each test file that imports from deleted modules:

| Deleted Module | Action |
|---------------|--------|
| `project_mgmt.*` | Delete the test file (already done in sp2, verify) |
| `shared.queue.*` | Delete or update the test |
| `from langfuse import observe` | Change to `from shared.utilities.langfuse_guard import observe` |
| `from dev_tools.*` | Update to `from linkedout.commands.*` or delete if testing retired functionality |

### 3. Update Enrichment Tests

`backend/tests/unit/enrichment_pipeline/test_enrich_task.py`:
- Remove any Procrastinate/queue mocking
- Test the synchronous enrichment function directly
- Test retry logic (mock Apify failure, verify 3 attempts with exponential backoff)
- Test successful enrichment path

### 4. Update or Guard Langfuse Tests

Any test that unconditionally imports or uses `langfuse`:
- Switch import to `shared.utilities.langfuse_guard`
- Or set `LANGFUSE_ENABLED=false` in test env and verify no crash

### 5. Run Full Test Suite

```bash
cd backend && LANGFUSE_ENABLED=false uv run pytest -x -v --timeout=60
```

Triage failures:
- **Import errors** → fix imports (steps 2-4)
- **Missing fixtures** → remove or replace
- **Assertion errors** → investigate and fix
- **Timeout** → mock external calls

Iterate until all tests pass.

### 6. Run Linting

```bash
cd backend && uv run ruff check src/
```

Fix any lint errors introduced by Phase 6 changes. Common issues:
- Unused imports from deleted modules
- Missing imports for moved modules
- Line length violations in new code

### 7. Run Type Checking

```bash
cd backend && uv run pyright src/
```

Address new type errors introduced by Phase 6. Pre-existing errors are acceptable (document baseline).

### 8. Full Exit Criteria Verification

Run every check from the Phase 6 exit criteria:

```bash
# 1. Lint clean
cd backend && uv run ruff check src/

# 2. Type check
cd backend && uv run pyright src/

# 3. Tests pass
cd backend && LANGFUSE_ENABLED=false uv run pytest --timeout=60

# 4. No hardcoded secrets or private paths
grep -rn "sk-\|~/workspace\|<home>" backend/src/

# 5. No project_mgmt references
grep -rn "project_mgmt" backend/src/ --include="*.py"

# 6. No Procrastinate references
grep -rn "procrastinate" backend/src/ --include="*.py"

# 7. Langfuse disabled by default — backend starts with zero Langfuse config
cd backend && LANGFUSE_ENABLED=false uv run python -c "from main import app; print('Backend OK without Langfuse')"

# 8. Auth unchanged — verify imports
cd backend && uv run python -c "from shared.auth.config import AuthConfig; print('Auth OK')"

# 9. CLI surface
cd backend && uv pip install -e . && linkedout --help
linkedout version
linkedout import-connections --help

# 10. No legacy entry points in pyproject.toml
grep -n "rcv2\|pm\|\"dev\"\|\"be\"\|\"fe\"\|fe-setup\|run-all-agents" backend/pyproject.toml
```

### 9. Document Any Remaining Issues

If any checks fail and cannot be fixed in this sub-phase:
- Document the issue, its root cause, and suggested fix
- Categorize as: blocker (must fix before Phase 7) vs. acceptable baseline (pre-existing)

## Verification
1. `cd backend && uv run pytest --timeout=60` exit code 0
2. `cd backend && uv run ruff check src/` exit code 0
3. `cd backend && uv run pyright src/` — zero NEW errors (pre-existing baseline OK)
4. All 12 exit criteria checks from Phase 6 plan pass
5. No test requires real API keys (OpenAI, Apify, Langfuse)

## Notes
- This sub-phase is primarily about validation, not new code. The goal is to verify everything from sp1-sp8 works together.
- If a test failure reveals a bug introduced in sp2-sp8, fix it here. The fix should be minimal and targeted.
- `pyright` may have a pre-existing error baseline. Don't spend time fixing old type errors — only fix new ones introduced by Phase 6.
- Run tests with `LANGFUSE_ENABLED=false` to ensure no Langfuse dependency leaks.
- The CLI verification (`linkedout --help`, etc.) requires `uv pip install -e .` to register the entry point.
