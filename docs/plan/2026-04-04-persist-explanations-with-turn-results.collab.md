# Plan: Persist Explanations with Search Turn Results

## Context

When a user does a live search, profile cards show LLM-generated "Why This Person" text, highlighted attribute chips, and match strength badges. These come from `WhyThisPersonExplainer`, streamed as separate `explanations` SSE events that the frontend merges into results in memory.

**The bug**: When a user restores a session (`?session=ss_xxx`), profile cards are bare — no "Why This Person", no attribute chips, no match strength. `_save_session_state()` persists raw `SearchResultItem` results to `search_turn.results` JSONB, and explanations are generated *after* but never merged back before persist.

## Approach

Accumulate explanations during the streaming loop, merge them into result dicts at persistence time. **No model changes, no schema changes, no frontend changes** — JSONB accepts extra keys, frontend already handles these optional fields.

## Changes (single file: `src/linkedout/intelligence/controllers/search_controller.py`)

### 1. Add merge helper (before `_save_session_state`, ~line 287)

```python
def _merge_results_with_explanations(
    results: list[SearchResultItem],
    explanations: dict[str, dict] | None,
) -> list[dict]:
    """Serialize results, merging in explanation data for DB persistence."""
    merged = []
    for r in results:
        d = r.model_dump(mode="json")
        if explanations:
            # Key lookup mirrors _profile_key() in why_this_person.py
            exp = explanations.get(r.connection_id) or explanations.get(r.crawled_profile_id)
            if exp:
                d["why_this_person"] = exp.get("explanation")
                d["highlighted_attributes"] = exp.get("highlighted_attributes", [])
                d["match_strength"] = exp.get("match_strength")
        merged.append(d)
    return merged
```

### 2. Update `_save_session_state` signature (line 288)

Add parameter: `explanations: dict[str, dict] | None = None`

### 3. Use merge helper in `_save_session_state` (line 314)

Replace:
```python
results=[r.model_dump(mode="json") for r in turn_response.results] if turn_response.results else None,
```
With:
```python
results=_merge_results_with_explanations(turn_response.results, explanations) if turn_response.results else None,
```

### 4. Accumulate explanations in `_stream_search` (after line 372)

Add `all_explanations: dict[str, dict] = {}` right after `results = turn_response.results` (line 371). Then inside the batch loop (line 402), accumulate before streaming:

```python
if batch_result:
    payload = {cid: exp.model_dump() for cid, exp in batch_result.items()}
    all_explanations.update(payload)  # accumulate across batches
    logger.info(...)
    yield _sse_line({"type": "explanations", "payload": payload})
```

### 5. Pass explanations to `_save_session_state` (line 431)

```python
await asyncio.to_thread(
    _save_session_state,
    search_session_id,
    request.query,
    turn_response,
    all_explanations,
)
```

**Edge cases handled:**
- `explain=False` → `all_explanations` is `{}`, merge helper skips (empty dict is falsy)
- Enrichment fails → `all_explanations` stays `{}`, gracefully skips
- Partial batch failures → partial accumulation, partial merge (better than nothing)

## What does NOT change

- `SearchResultItem` model — no optional explanation fields added
- SSE streaming — results and explanations still stream as separate events
- `SearchTurnEntity` / `SearchTurnSchema` — JSONB accepts any dict shape
- Frontend — already renders `why_this_person` and `highlighted_attributes` when present
- Backward compat — old turns without explanation fields render fine (optional fields on `ProfileResult`)

## Testing

### Unit test: add to `tests/unit/linkedout/intelligence/test_search_controller_streaming.py`

1. **Test `_merge_results_with_explanations`** directly:
   - Results with matching explanations → fields merged
   - Results without matching explanations → no extra fields
   - `None` explanations → plain `model_dump()` output

2. **Extend existing streaming test**: assert that `_save_session_state` is called with `all_explanations` containing 25 entries after all batches complete. (Mock `_save_session_state` and inspect args.)

### Manual verification

1. Run a fresh search → profile cards show "Why This Person" + chips (live stream, unchanged)
2. Reload `?session=ss_xxx` → same cards now show explanations (restored from DB)
3. SQL check: `SELECT results->0 FROM search_turn ORDER BY created_at DESC LIMIT 1` — should contain `why_this_person`, `highlighted_attributes`, `match_strength`
4. Run: `pytest tests/unit/linkedout/intelligence/ -x`
