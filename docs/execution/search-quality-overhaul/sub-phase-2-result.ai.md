# Sub-Phase 2 Result: Schema Context — Data Availability Notes

**Status:** Completed
**Date:** 2026-03-31

## Changes Made

Added a `## Data Availability` section to `_BUSINESS_RULES` in `src/linkedout/intelligence/schema_context.py` (before the closing `""".strip()`). The section warns the LLM about:

1. NULL company columns (`industry`, `size_tier`, `estimated_employee_count`, `hq_city`, `hq_country`, `website`, `founded_year`) — recommends `canonical_name ILIKE` patterns instead
2. Empty `company_alias` table — instructs LLM not to use it
3. Partial `seniority_level` (~79%) and `function_area` (~63%) coverage — recommends ILIKE fallback on `current_position`
4. `start_date` (~98%) and `is_current` (~18%) coverage stats

## Verification

- `build_schema_context()` returns string containing "Data Availability" — OK
- `.strip()` call preserved on `_BUSINESS_RULES`
- All 914 existing tests pass
