# Sub-Phase 5: Small Cleanups — Hardcoded Paths & SSE Router

**Phase:** 6 — Code Cleanup for OSS
**Plan task:** 6F (Strip Hardcoded Paths) + Decision Q4 (Remove SSE Router)
**Dependencies:** sp2, sp3, sp4 (removals complete — import tree is cleaner)
**Blocks:** sp6
**Can run in parallel with:** None

## Objective
Remove all hardcoded dev-environment paths from the codebase and delete the SSE router spike artifact. Small, focused cleanup before the CLI refactor.

## Context
- Read shared context: `docs/execution/phase-06/_shared_context.md`
- Read plan (6F section): `docs/plan/phase-06-code-cleanup.md`

## Deliverables

### 1. Strip Hardcoded Paths

Search for all hardcoded dev paths:

```bash
grep -rn "~/workspace" backend/src/ --include="*.py"
grep -rn "<home>" backend/src/ --include="*.py"
grep -rn "linkedout-fe" backend/src/ --include="*.py"
grep -rn "~/workspace" backend/ --include="*.toml"
grep -rn "~/workspace" backend/ --include="*.cfg"
```

Known locations:
- `backend/src/dev_tools/benchmark/runner.py:214` — hardcoded DB config path → replace with `DATABASE_URL` from config/env
- `backend/src/dev_tools/cli.py:374` — hardcoded `<linkedout-fe>` for `fe_dir` → the `fe` command is being retired in sp6 (CLI refactor). If this code will be deleted in sp6, leave it for now. If you want to clean it up proactively, just delete the `fe_command` function since the entry point is being removed.

For each match:
- If the file is being deleted in sp6 (CLI refactor): skip — sp6 handles it
- If the file persists: replace hardcoded path with config value or relative path

### 2. Remove SSE Router (Decision Q4)

Delete the spike artifact:
- `backend/src/shared/test_endpoints/sse_router.py`

Check `backend/main.py` for any `include_router` call referencing the SSE router and remove it.

Check if `shared/test_endpoints/` has other files:
- If `sse_router.py` is the only file → delete the entire `test_endpoints/` directory
- If other files exist → only delete `sse_router.py`

### 3. Scan for Other Private-Repo Artifacts

```bash
# Look for any remaining private-repo references
grep -rn "sk-" backend/src/ --include="*.py"  # API key fragments
grep -rn "PRIVATE" backend/src/ --include="*.py"  # private markers
grep -rn "TODO.*private" backend/src/ --include="*.py" -i
```

Remove or replace any findings.

## Verification
1. `grep -rn "~/workspace" backend/src/ --include="*.py"` returns zero matches
2. `grep -rn "<home>" backend/src/ --include="*.py"` returns zero matches
3. `grep -rn "linkedout-fe" backend/src/ --include="*.py"` returns zero matches
4. `backend/src/shared/test_endpoints/sse_router.py` does not exist
5. `cd backend && uv run python -c "from main import app; print('main.py imports OK')"` succeeds
6. `cd backend && uv run ruff check src/` no new errors from these changes

## Notes
- This is a small, fast sub-phase. Most of the dev_tools cleanup happens in sp6 (CLI refactor).
- If `dev_tools/benchmark/runner.py` is slated for deletion or major refactor in sp6, coordinate — don't fix something that's about to be rewritten.
- The `~/workspace` paths may also appear in shell scripts, Dockerfiles, or config files outside `backend/src/`. Check `backend/` broadly but don't go outside the backend directory.
