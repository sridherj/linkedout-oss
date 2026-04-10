# Sub-Phase 4: Deduplication + Fix Retry Loop (Phase 3a + 3b)

**Working directory:** `./`
**Depends on:** Sub-phase 3 (match_context must exist on SearchResultItem)
**Modifies:** `src/linkedout/intelligence/agents/search_agent.py`

## Context

Two bugs in `search_agent.py`:
1. `_collect_results()` (line 242) combines results from SQL + vector tools without dedup. Hybrid queries return the same person twice.
2. `_execute_tool_with_retry()` (lines 205-224) never actually retries — it returns on the first iteration regardless of error.

## Review Decisions

- **Code-3:** Dedup key is `crawled_profile_id` primary, `connection_id` fallback. Keep first occurrence.
- **Code-4:** Fix the hand-rolled retry loop to properly send the error+hint back to the LLM for self-correction. This is NOT a tenacity case (LLM-in-the-loop retry, not infrastructure retry).
- **Tests-3:** Unit test `_collect_results` with duplicates.

## Tasks

### 3a. Dedup in `_collect_results()`

**File:** `src/linkedout/intelligence/agents/search_agent.py` — `_collect_results()` method (line 242)

Add deduplication after collecting all items. Dedup by `crawled_profile_id`, falling back to `connection_id` if profile ID is empty. Keep the first occurrence (higher relevance from the tool that found it first).

```python
def _collect_results(self, messages: list) -> list[SearchResultItem]:
    """Collect SearchResultItems from all tool responses, deduplicated."""
    items: list[SearchResultItem] = []
    # ... existing collection logic ...

    # Deduplicate: prefer first occurrence (from higher-priority tool)
    seen: set[str] = set()
    deduped: list[SearchResultItem] = []
    for item in items:
        key = item.crawled_profile_id or item.connection_id
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped
```

### 3b. Fix `_execute_tool_with_retry`

**File:** `src/linkedout/intelligence/agents/search_agent.py` — `_execute_tool_with_retry()` (lines 205-224)

Current broken code:
```python
def _execute_tool_with_retry(self, tool_name: str, tool_args: dict) -> str:
    for attempt in range(_MAX_TOOL_RETRIES + 1):
        result_str = self._execute_tool(tool_name, tool_args)
        result = json.loads(result_str)
        if (
            tool_name == "execute_sql"
            and isinstance(result, dict)
            and result.get("error")
            and result.get("hint")
            and attempt < _MAX_TOOL_RETRIES
        ):
            logger.info(f"SQL error with hint, retrying (attempt {attempt + 1}): {result['hint']}")
            return result_str  # BUG: returns immediately instead of retrying
        return result_str  # BUG: also returns immediately on success
    return result_str
```

The intent is that when an SQL error with a hint is returned, the error+hint should be sent back to the LLM so it can self-correct its SQL. The current code returns on the first iteration regardless.

**Fix:** When an error with hint is detected, return the error string (which includes the hint) so the LLM can see it and generate corrected SQL. Remove the unconditional `return result_str` that prevents the loop from continuing. The key insight is that this is an LLM-in-the-loop retry — the calling code (which invokes tool calls from the LLM) already handles the retry loop. This function just needs to NOT swallow the error:

```python
def _execute_tool_with_retry(self, tool_name: str, tool_args: dict) -> str:
    """Execute tool, returning error+hint on SQL failures so the LLM can self-correct."""
    result_str = self._execute_tool(tool_name, tool_args)
    # Always return the result — errors with hints are intentionally passed back
    # to the LLM so it can see the hint and generate corrected SQL.
    return result_str
```

Wait — re-read the code. The function is called per tool call from the LLM. The LLM's own retry loop (the agent loop) handles re-invocation. So the retry logic in this function is redundant AND broken. Simplify to just execute and return. The error+hint in the result string is what the LLM needs to self-correct.

**Actually**, look more carefully at the calling context to understand how `_execute_tool_with_retry` is used. If the caller is the LangChain agent loop, then the function should just return the result (including errors) and the agent loop handles retries. Simplify accordingly.

## Verification

1. **Dedup unit test (required by Tests-3):** Feed `_collect_results` two `ToolMessage`s that contain the same person (same `crawled_profile_id`) from SQL + vector tools. Assert only the first occurrence survives and ordering is preserved.
2. **Retry test:** Verify that when `_execute_tool` returns an error with a hint, the hint is returned (not swallowed).
3. Run existing tests: `cd . && pytest tests/ -x -q --timeout=30`
