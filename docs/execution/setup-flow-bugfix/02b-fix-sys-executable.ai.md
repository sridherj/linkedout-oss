# Sub-phase 02b: Replace sys.executable with linkedout CLI

## Metadata
- **Depends on:** nothing
- **Blocks:** 04-spec-updates, 05-tests
- **Estimated scope:** 7 files modified
- **Plan section:** Phase 2b (Issue 11)

## Context

Read `_shared_context.md` for CLI entry point conventions.

## Task

11 occurrences across 7 files. Each `[sys.executable, "-m", "linkedout.commands", ...]`
becomes `["linkedout", ...]`. Remove `import sys` where it was the only usage.

| File | Lines | Remove `import sys`? |
|------|-------|---------------------|
| `backend/src/linkedout/setup/csv_import.py` | 189 | Yes — only usage |
| `backend/src/linkedout/setup/contacts_import.py` | 156 | Yes — only usage |
| `backend/src/linkedout/setup/auto_repair.py` | 160 | Yes — only usage |
| `backend/src/linkedout/setup/readiness.py` | 409, 481 | Yes — only usage |
| `backend/src/linkedout/setup/seed_data.py` | 67, 118 | Yes — only usage |
| `backend/src/linkedout/setup/affinity.py` | 47, 86 | Yes — only usage |
| `backend/src/linkedout/setup/embeddings.py` | 59, 171 | Yes — only usage |

**DO NOT change:**
- `skill_install.py` — uses `sys.executable` to run a Python script (different pattern)
- `logging_integration.py` — reads `sys.executable` for diagnostics

## Verification

After changes:
```bash
grep -r "sys.executable" backend/src/linkedout/setup/
```
Should return only `skill_install.py` and `logging_integration.py`.

Run existing tests:
```bash
cd backend && python -m pytest tests/linkedout/setup/test_csv_import.py tests/linkedout/setup/test_contacts_import.py -v
```

## Completion Criteria
- [ ] All 11 occurrences replaced with `["linkedout", ...]`
- [ ] `import sys` removed from 7 files where it was only usage
- [ ] `skill_install.py` and `logging_integration.py` unchanged
- [ ] Existing tests pass
