# Sub-Phase 2: Schema Context — Data Availability Notes (Phase 4)

**Working directory:** `./`
**Depends on:** Nothing
**Modifies:** `src/linkedout/intelligence/schema_context.py`

## Context

The `schema_context.py` file builds a schema reference string for the LLM's system prompt. It has a `_BUSINESS_RULES` string (lines 26-67) that describes tables, rules, and query patterns. The LLM sees this in every search request.

Currently there are no warnings about NULL columns or partial data coverage. The LLM may generate queries filtering on columns that are entirely NULL (e.g., `co.industry`).

## Task

Append data availability notes to the end of the `_BUSINESS_RULES` string (before the `.strip()` on line 67) so the LLM sees NULL column warnings even if it ignores the system prompt's business rules section.

Add this block at the end of `_BUSINESS_RULES`, before the closing `"""`:

```python
## Data Availability

- `company.industry`, `company.size_tier`, `company.estimated_employee_count`, `company.hq_city`, `company.hq_country`, `company.website`, `company.founded_year` are being populated by an enrichment pipeline. Until complete, these columns may be NULL for many companies. Prefer `co.canonical_name ILIKE` patterns for company filtering.
- `company_alias` table is currently empty. Do not use it in queries.
- ~79% of experience records have `seniority_level` populated; ~63% have `function_area`. Add ILIKE fallback on `cp.current_position` when filtering by these fields.
- `experience.start_date` is populated for ~98% of records. `experience.is_current` is TRUE for ~18% of records.
```

### Implementation

Edit `_BUSINESS_RULES` in `src/linkedout/intelligence/schema_context.py`. The string currently ends with:

```python
```
""".strip()
```

Add the data availability section before the closing `"""`.

## Verification

1. Run: `cd . && python -c "from linkedout.intelligence.schema_context import build_schema_context; ctx = build_schema_context(); assert 'Data Availability' in ctx; print('OK')" `
2. Confirm `_BUSINESS_RULES` still has the `.strip()` call
3. Run existing tests: `cd . && pytest tests/ -x -q --timeout=30 2>&1 | tail -5`
