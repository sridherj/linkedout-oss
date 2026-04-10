# Sub-Phase 3 Result: match_context Contract + Extra SQL Column Capture

**Status:** Completed
**Date:** 2026-03-31

## Changes Made

### 2a. Added `match_context` to SearchResultItem
- **File:** `src/linkedout/intelligence/contracts.py`
- Added `match_context: Optional[dict] = None` field after `has_enriched_data`
- Backwards-compatible (Optional, default None)

### 2b. Capture extra SQL columns in match_context
- **File:** `src/linkedout/intelligence/agents/search_agent.py`
- Added `_KNOWN_FIELDS` frozenset (fields that map to SearchResultItem)
- Added `_EXCLUDE_FIELDS` frozenset (internal fields like `app_user_id`, `embedding`, `profile_embedding`)
- Modified `_sql_rows_to_result_items()` to collect any SQL columns not in `_KNOWN_FIELDS` or `_EXCLUDE_FIELDS` into `match_context` dict
- When no extra columns exist, `match_context` remains `None`

## Verification

1. Import check: `SearchResultItem` accepts `match_context` parameter correctly
2. Unit test: Extra columns (e.g., `previous_company`) appear in `match_context`, `app_user_id` is excluded
3. No extra columns -> `match_context` is `None`
4. All 914 existing tests pass
