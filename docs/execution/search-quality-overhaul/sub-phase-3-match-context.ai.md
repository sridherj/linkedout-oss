# Sub-Phase 3: Add match_context to Contract + Capture Extra SQL Columns (Phase 2a + 2b)

**Working directory:** `./`
**Depends on:** Sub-phases 1 and 2 (prompt and schema fixes should land first)
**Modifies:**
- `src/linkedout/intelligence/contracts.py`
- `src/linkedout/intelligence/agents/search_agent.py`

## Context

When the SQL agent selects extra columns (e.g., `previous_company`, `old_company_name`, `skill_names`), the `_sql_rows_to_result_items()` function in `search_agent.py` silently drops them because they don't map to `SearchResultItem` fields. This means match evidence is lost before it reaches the explainer.

## Review Decisions

- **Code-1:** Use an explicit exclude set (`_KNOWN_FIELDS`). Any SQL columns NOT in this set get collected into `match_context` dict. This prevents internal columns like `app_user_id` from leaking into the payload.

## Tasks

### 2a. Add `match_context` to SearchResultItem

**File:** `src/linkedout/intelligence/contracts.py`

Add a new field to `SearchResultItem` (after `has_enriched_data` on line 45):

```python
match_context: Optional[dict] = None  # Extra SQL columns explaining why this person matched
```

This is backwards-compatible (Optional, default None). Frontend ignores unknown fields.

### 2b. Capture extra SQL columns in match_context

**File:** `src/linkedout/intelligence/agents/search_agent.py`

**Step 1:** Add a module-level constant near the top of the file (after imports):

```python
# Fields that map directly to SearchResultItem — everything else goes into match_context.
# Internal fields (app_user_id, etc.) are excluded to prevent leaking into the API payload.
_KNOWN_FIELDS = frozenset({
    "connection_id", "crawled_profile_id", "id",
    "full_name", "headline", "current_position", "current_company_name",
    "location_city", "location_country", "linkedin_url", "public_identifier",
    "affinity_score", "dunbar_tier", "similarity", "connected_at", "has_enriched_data",
})

_EXCLUDE_FIELDS = frozenset({
    "app_user_id", "embedding", "profile_embedding",
})
```

**Step 2:** Modify `_sql_rows_to_result_items()` (currently lines 123-154) to collect extra columns:

After building the `SearchResultItem` (line 137-153), before appending to `items`, add:

```python
        # Collect extra columns into match_context
        extra = {}
        for col_name, col_idx in col_map.items():
            if col_name not in _KNOWN_FIELDS and col_name not in _EXCLUDE_FIELDS:
                val = row[col_idx]
                if val is not None:
                    extra[col_name] = val

        item = SearchResultItem(
            # ... existing fields ...
            match_context=extra if extra else None,
        )
        items.append(item)
```

Refactor the existing append to use the `item` variable pattern shown above.

## Verification

1. Unit test: Create a test that calls `_sql_rows_to_result_items()` with columns including an extra column like `previous_company`. Assert the extra column appears in `match_context` and `app_user_id` does NOT.
2. Run existing tests: `cd . && pytest tests/ -x -q --timeout=30`
3. Verify import: `python -c "from linkedout.intelligence.contracts import SearchResultItem; s = SearchResultItem(connection_id='a', crawled_profile_id='b', full_name='c', match_context={'foo': 'bar'}); print(s.match_context)"`
