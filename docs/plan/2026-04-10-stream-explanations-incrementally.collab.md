# Stream Explanations Incrementally

## Context
The WhyThisPersonExplainer processes results in batches of 10 (separate LLM calls), but the controller waits for ALL batches to complete before sending a single `explanations` SSE event. With 29 results (3 batches, ~7s each), the user stares at "Generating explanations..." for ~20s before seeing anything. We should stream each batch's explanations as it completes.

## Key Constraint
`asyncio.to_thread` runs a single callable — you can't yield from inside it. So a sync generator on the explainer won't bridge to the async generator in the controller. Instead, we split the work into discrete `to_thread` calls: one for enrichment prep, then one per batch.

## Frontend: No changes needed
The `"explanations"` handler in `useStreamingSearch.ts:289` patches whatever IDs are in the payload onto matching results. Multiple `explanations` events trigger multiple patches — already works.

## Backend Changes

### 1. Extract `prepare_enrichment` from `explain()`
**File:** `src/linkedout/intelligence/explainer/why_this_person.py`

Add a public method that does the upfront DB work:

```python
def prepare_enrichment(self, results: list[SearchResultItem], session: Session) -> dict[str, dict]:
    """Fetch enrichment data for all results upfront. Returns enrichment_map."""
    profile_ids = [r.crawled_profile_id for r in results if r.crawled_profile_id]
    connection_ids = [r.connection_id for r in results if r.connection_id]
    if not profile_ids:
        return {}
    return self._fetch_enrichment_data(session, profile_ids, connection_ids)
```

Refactor `explain()` to call `prepare_enrichment()` internally — no behavior change.

### 2. Stream batches from controller
**File:** `src/linkedout/intelligence/controllers/search_controller.py` (lines 379-399)

Replace the monolithic `_run_explainer` with two phases:

```python
if explain and results:
    yield _sse_line({"type": "thinking", "message": "Generating explanations..."})

    explainer = WhyThisPersonExplainer()

    # Phase 1: Enrichment fetch (needs DB session, one call)
    def _prep():
        with db_session_manager.get_session(app_user_id=app_user_id) as session:
            return explainer.prepare_enrichment(results, session)

    enrichment_map = await asyncio.to_thread(_prep)
    if not enrichment_map:
        logger.warning("Enrichment fetch failed — skipping explanations")
    else:
        # Phase 2: Stream each batch (LLM only, no DB needed)
        for i in range(0, len(results), BATCH_SIZE):
            batch = results[i:i + BATCH_SIZE]
            batch_result = await asyncio.to_thread(
                explainer._explain_batch, request.query, batch, enrichment_map
            )
            if batch_result:
                payload = {cid: exp.model_dump() for cid, exp in batch_result.items()}
                logger.info(f"Streaming {len(payload)} explanations (batch {i // BATCH_SIZE + 1})")
                yield _sse_line({"type": "explanations", "payload": payload})
```

**Why this works:**
- DB session only needed for enrichment (phase 1) — closed before LLM calls start
- Each `to_thread` per batch returns → controller yields SSE → starts next batch
- Heartbeat wrapper handles keepalives between batches automatically
- `_explain_batch` has its own `@observe` decorator — each batch traced independently in Langfuse
- If a batch fails, previous batches' explanations are already sent (partial > none)

**Trade-off:** We lose the parent Langfuse observation that wrapped all batches. Each batch still gets its own span. Acceptable for now.

**Import needed:** `BATCH_SIZE` from the explainer module.

## Tests

### Existing tests — no breakage
All existing tests call `explainer.explain()` which stays unchanged internally (refactored to use `prepare_enrichment` but same behavior):
- `test_explain_returns_structured_explanations` — ✅ calls `explain()`, no session
- `test_explain_empty_results` — ✅ unchanged
- `test_explain_handles_llm_error` — ✅ unchanged
- `test_batching_splits_large_result_sets` — ✅ calls `explain()`, no session
- `TestFormatProfile` — ✅ `_profile_key` returns `connection_id` when present
- `TestParseExplanations` — ✅ pure parsing, no changes

### New tests to add
**File:** `tests/unit/linkedout/intelligence/test_why_this_person.py`

1. **`test_profile_key_falls_back_to_crawled_profile_id`** — when `connection_id=""`, `_format_profile` uses `crawled_profile_id` in the header
2. **`test_prepare_enrichment_delegates_to_fetch`** — mock `_fetch_enrichment_data`, verify `prepare_enrichment` calls it with correct args and returns the result
3. **`test_prepare_enrichment_empty_profiles`** — no `crawled_profile_id` → returns `{}`
4. **`test_explain_uses_prepare_enrichment`** — verify `explain()` with a mock session calls `prepare_enrichment` internally

## Files to modify
1. `src/linkedout/intelligence/explainer/why_this_person.py` — extract `prepare_enrichment()`, import `_profile_key` in tests
2. `src/linkedout/intelligence/controllers/search_controller.py` — stream batches
3. `tests/unit/linkedout/intelligence/test_why_this_person.py` — add new tests

## Review Notes (2026-04-02)

### Architecture: Pass
- Two-phase split is correct for `asyncio.to_thread` constraint.
- Frontend `useStreamingSearch.ts:289` already handles multiple `explanations` events — verified.

### Code Quality: Pass with action item
- **Rename `_explain_batch` → `explain_batch`** — controller shouldn't call a private method. Drop the underscore, update the internal call in `explain()`.
- Ensure `explain()` delegates to `prepare_enrichment()` with no duplicated logic.

### Tests: Needs addition
- **Add controller-level streaming test** — assert that >10 results produces multiple `explanations` SSE events.
- Existing tests won't break.

### Performance: Pass
- Same number of LLM calls, same prompts, just yielded incrementally. First batch visible in ~7s vs ~20s.

## Verification
1. `pytest tests/unit/linkedout/intelligence/test_why_this_person.py` — all pass
2. Run a search with >10 results
3. Browser DevTools Network → SSE stream → multiple `explanations` events appearing incrementally
4. UI: explanation cards populate in waves (first 10, then next 10, etc.)
