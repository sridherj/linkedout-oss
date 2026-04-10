# Sub-Phase 6 Result: Eval Framework

**Status:** Completed
**Date:** 2026-03-31

## What was done

1. **Created `tests/eval/__init__.py`** — Package init
2. **Created `tests/eval/search_eval_queries.py`** — 30 eval query definitions across 8 categories: name lookup (3), company-specific (4), company-type (4), career transitions (5), skills-based (3), location (3), seniority (3), semantic/concept (3), aggregation (2)
3. **Created `tests/eval/test_search_quality.py`** — Parametrized test runner with assertions for minimum result count, must-include names, and company pattern matching (30% threshold)
4. **Created `tests/eval/conftest.py`** — Fixtures for real DB session and auto-detected app_user_id (picks user with most connections)
5. **Updated `pytest.ini`** — Registered `eval` marker and added `not eval` to default addopts filter

## Verification

- `pytest tests/eval/ -m eval -v --co` — **30 tests collected**
- Default `pytest tests/` — **0 eval tests included** (correctly excluded)
- All files created as specified in the plan

## How to run

```bash
# Run all eval queries
pytest tests/eval/ -m eval -v

# Run a single query
pytest tests/eval/ -m eval -k "Find Agil C" -v

# Run a category
pytest tests/eval/ -m eval -k "name_lookup" -v
```
