# Sub-Phase 8: Dependency Cleanup

**Phase:** 6 — Code Cleanup for OSS
**Plan task:** 6G (Dependency Cleanup)
**Dependencies:** sp2 (project_mgmt gone), sp3 (Procrastinate gone), sp4 (Langfuse guarded)
**Blocks:** sp9
**Can run in parallel with:** sp6, sp7

## Objective
Remove unused dependencies from `requirements.txt`. Create a separate `requirements-dev.txt` for dev/test tools. Ensure clean installs in fresh virtual environments.

## Context
- Read shared context: `docs/execution/phase-06/_shared_context.md`
- Read plan (6G section): `docs/plan/phase-06-code-cleanup.md`
- Read current: `backend/requirements.txt`

## Deliverables

### 1. Identify Dependencies to Remove

From sp2-sp4 removals:
- `procrastinate` — removed in sp3
- `psycopg` (async driver) — verify if only used by Procrastinate. `psycopg2-binary` (sync driver for SQLAlchemy) STAYS.
- `psycopg_pool` — verify if only used by Procrastinate

Verify each removal:
```bash
# Check if psycopg (not psycopg2) is imported anywhere
grep -rn "import psycopg[^2]" backend/src/ --include="*.py"
grep -rn "from psycopg[^2]" backend/src/ --include="*.py"

# Check if psycopg_pool is imported anywhere
grep -rn "psycopg_pool" backend/src/ --include="*.py"
```

### 2. Audit All Dependencies

For each package in `requirements.txt`:
```bash
# For each dep, check if it's imported
grep -rn "import <package>" backend/src/ --include="*.py"
grep -rn "from <package>" backend/src/ --include="*.py"
```

Evaluate edge cases:
- `firebase-admin` — keep (auth provider code is kept per sp1, disabled by default)
- `langfuse` — keep (guarded by `LANGFUSE_ENABLED`, conditional import in guard module)
- `tenacity` — keep if added in sp3 for retry logic
- `httpx` — check if only used in tests. If so, move to dev deps.

### 3. Create `backend/requirements-dev.txt` (NEW)

```
-r requirements.txt

# Testing
pytest
pytest-asyncio
pytest-cov

# Linting & type checking
ruff
pyright

# Test utilities
httpx  # if only used in tests
```

Move dev-only packages from `requirements.txt` to this file.

### 4. Clean Up `backend/requirements.txt`

- Remove packages identified in step 1
- Remove packages moved to `requirements-dev.txt`
- Keep all production dependencies
- Sort alphabetically for readability
- Pin versions if they were pinned before (maintain existing pinning strategy)

### 5. Verify Clean Install

```bash
cd backend

# Test production deps
uv venv /tmp/linkedout-prod-test
source /tmp/linkedout-prod-test/bin/activate
uv pip install -r requirements.txt
python -c "from main import app; print('Production deps OK')"
deactivate
rm -rf /tmp/linkedout-prod-test

# Test dev deps
uv venv /tmp/linkedout-dev-test
source /tmp/linkedout-dev-test/bin/activate
uv pip install -r requirements-dev.txt
python -c "import pytest; print('Dev deps OK')"
deactivate
rm -rf /tmp/linkedout-dev-test
```

## Verification
1. `backend/requirements-dev.txt` exists with `-r requirements.txt` at the top
2. `grep -i "procrastinate" backend/requirements.txt` returns zero matches
3. `grep -i "psycopg_pool" backend/requirements.txt` returns zero matches (if confirmed unused)
4. No dev-only packages in `requirements.txt` (pytest, ruff, pyright should be in dev file only)
5. `cd backend && uv pip install -r requirements.txt` succeeds
6. `cd backend && uv pip install -r requirements-dev.txt` succeeds
7. Backend starts with only production deps installed
8. `pytest` runs with dev deps installed

## Notes
- Keep `psycopg2-binary` — it's the sync PostgreSQL driver used by SQLAlchemy.
- The distinction between `psycopg` (async, used by Procrastinate) and `psycopg2-binary` (sync, used by SQLAlchemy) is critical. Do not confuse them.
- If any package is ambiguous (might be used indirectly), err on the side of keeping it. Better to have a slightly fat `requirements.txt` than a broken install.
- Use `uv` for all pip operations per project convention.
