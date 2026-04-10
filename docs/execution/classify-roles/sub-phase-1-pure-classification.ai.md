# Sub-Phase 1: Pure Classification Functions and Tests

**Goal:** linkedin-ai-production
**Source plan:** 2026-03-28-classify-roles-port-and-wiring.md
**Type:** Pure functions + tests — zero DB dependency
**Estimated effort:** ~2 hours
**Dependencies:** None
**Can parallelize with:** Nothing (first wave)

---

## Overview

Create `classify_seniority()` and `classify_function()` as pure functions in `src/dev_tools/classify_roles.py`, importable and tested. Port regex patterns verbatim from the old script. 75 parametrized test cases must pass.

---

## Step 1: Create Classification Module

**What:** Create `src/dev_tools/classify_roles.py` with the two rule lists and two pure functions.

**Actions:**
1. Create `src/dev_tools/classify_roles.py`
2. Copy `SENIORITY_RULES` and `FUNCTION_RULES` regex pattern lists verbatim from `<prior-project>/linkedin-intel/scripts/classify_roles.py` (lines 17-86)
3. Implement `classify_seniority(title: str) -> str | None` — first-match-wins against SENIORITY_RULES
4. Implement `classify_function(title: str) -> str | None` — first-match-wins against FUNCTION_RULES
5. Adapt type hints from `str | None` to `Optional[str]` if the project targets Python <3.10, otherwise keep as-is

**Key constraint:** Functions must be pure — no DB imports at module level in the classification section.

**Verification:**
- [ ] `from dev_tools.classify_roles import classify_seniority, classify_function` succeeds
- [ ] Functions are pure (no DB imports at module level)

---

## Step 2: Create Test Suite

**What:** Port all 75 parametrized test cases from the old test file.

**Actions:**
1. Create `tests/dev_tools/test_classify_roles.py`
2. Port all parametrized test cases from `<prior-project>/linkedin-intel/scripts/test_classify_roles.py`
3. Adjust import path from `from classify_roles import ...` to `from dev_tools.classify_roles import ...`
4. Ensure `tests/dev_tools/__init__.py` exists (create if missing)

**Verification:**
- [ ] `pytest tests/dev_tools/test_classify_roles.py -v` — all 75 cases pass

---

## Step 3: Run Full Test Suite

**What:** Ensure the new module doesn't break anything.

**Actions:**
1. Run `pytest tests/dev_tools/test_classify_roles.py -v` — all 75 cases pass
2. Run `precommit-tests` to verify no regressions

**Verification:**
- [ ] All 75 test cases pass
- [ ] No regressions in existing tests

---

## Completion Criteria

- [ ] `classify_seniority()` and `classify_function()` exist as pure functions in `src/dev_tools/classify_roles.py`
- [ ] 75 parametrized test cases pass
- [ ] Functions are importable: `from dev_tools.classify_roles import classify_seniority, classify_function`
- [ ] No DB dependency in this sub-phase
- [ ] `precommit-tests` passes
