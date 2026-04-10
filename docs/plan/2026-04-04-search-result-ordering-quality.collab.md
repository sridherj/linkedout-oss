# Search Result Quality: Analysis & Fix Plan

## Context

Session `ss_NwzWYWc4QtBqScxAh-Ymc` — query: "Find folks with evals experience." Results were way off across 5 turns. Root cause is structural: the LLM has no mechanism to control final result ordering.

## What Actually Happened

### Turn 1: Vector results (positions 1-10) + SQL results by affinity (positions 11-30)
- Vector search returned generic AI/ML acquaintances (affinity 12-16)
- SQL used `ORDER BY affinity_score DESC` with broad `ILIKE '%eval%' OR '%llm%'`
- Result: Waymo director (no evals, affinity 47.8) ranked above Google DeepMind "LLM Evals | Post-Training" person (affinity 38.7)

### Turn 4-5: Got worse
- LLM tried a CTE with relevance scoring → **timed out at 5s**
- Fallback queries returned completely irrelevant people at top ("Growth Recruiter", "Manager at Daimler")

### Backend: One SQL timeout, otherwise data returned fine. Not a data availability issue.

## Root Causes

### 1. `_collect_results()` uses first-seen dedup — LLM cannot re-order
`search_agent.py:609-658` appends results from each tool call in message order. First occurrence wins dedup. Even if the LLM writes a perfect final ordering query, earlier vector search results still occupy positions 1-N.

### 2. `run_streaming()` emits results as they arrive — no ordering at all
`search_agent.py:916-932` streams each `SearchResultItem` to the frontend the moment a tool returns. No dedup, no reordering. This is the primary FE path.

### 3. No ordering guidance in system prompt
The LLM defaults to `ORDER BY affinity_score DESC` for SQL, which returns strongest connections regardless of topical relevance.

### 4. Vector search has no quality threshold
Returns top-20 by cosine distance regardless of similarity score. Generic AI/ML profiles match "evals" tangentially.

### 5. Experience table underused
Strongest signal for "actually worked on evals" lives in `experience.position/description`, but LLM only queries `headline/about`.

### 6. No match_context evidence
Extra SQL columns already flow into `match_context` (search_agent.py:416-422), but the LLM never includes them. Users can't see why someone matched.

## Design Decisions

Resolved during design review (2026-04-04):

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Explicit tool call vs implicit ordering? | **Explicit `set_result_order` tool** | Cleanest contract. Extra tool call (~500ms) is negligible vs 3-6 already made. Fallback if LLM forgets = current behavior (no regression). |
| 2 | Streaming: full objects vs ordered IDs + fetch? | **Full `SearchResultItem` objects in single `results` event** | We're solving ranking, not data freshness. Objects are already built during agent loop. No extra round-trip. |
| 3 | FE loading UX during agent work? | **Progress messages + candidate count preview** | `thinking` events show step-by-step progress. Result-producing tools emit candidate count ("Found 18 candidates..."). Final "Ranking N candidates..." before results arrive. |
| 4 | `set_result_order` only, or also `sort_by`? | **`set_result_order` only** | One mechanism. For simple sort queries (e.g., affinity), SQL already returns correct order. If LLM doesn't call the tool, fallback = tool-call order, which is correct for those cases. |
| 5 | Cap number of IDs in `set_result_order`? | **No cap** | LLM has full control. No silent truncation. |
| 6 | Unknown IDs in `set_result_order`? | **Silently ignore for ordering, return full accounting** | `{"status": "ok", "ordered_count": 13, "requested_count": 15, "unknown_ids": ["cp_abc132"]}`. Partial ordering always works. Mismatch visible in Langfuse traces. |
| 7 | Dedup: first-seen vs merge? | **Merge** | Same person from vector + SQL: merge `match_context` dicts, fill null fields from later occurrence. Preserves both similarity score and evidence columns. |

## Design Principles

1. **Quality > speed.** Correct results in the right order trump streaming partial results.
2. **LLM decides ranking.** No hardcoded ranking logic. The LLM knows the user's intent.
3. **`crawled_profile_id` is the canonical ID.** It's the entity-level identity (one person = one ID), present in every result path (vector, SQL, intro, career). FE and BE align on this.
4. **Streaming is a progress channel, not a result channel.** Results arrive once, ranked, final.

## Fix Plan

### Fix 1: `set_result_order` tool (HIGH IMPACT — solves the ordering problem)

A new tool the LLM calls as its final action before writing its summary to declare the ranked order of results.

**Tool definition** (add to `_TOOL_DEFINITIONS` in search_agent.py):
```python
{
    "type": "function",
    "function": {
        "name": "set_result_order",
        "description": (
            "Set the final display order of search results. Call this AFTER you've gathered "
            "and evaluated candidates, BEFORE writing your final summary. Pass the `id` or "
            "`crawled_profile_id` values from tool results in the order you want them "
            "displayed (most relevant first). Any gathered profiles not in this list will "
            "appear after the ordered ones."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "profile_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of crawled_profile_id values, best match first.",
                },
            },
            "required": ["profile_ids"],
        },
    },
}
```

**Handler in `_execute_tool()`**:
- Store ordered IDs on `self._declared_order: list[str]`
- Return accounting: `{"status": "ok", "ordered_count": N, "requested_count": M, "unknown_ids": [...]}`
- Unknown IDs (not in collected results) are silently skipped for ordering but reported in response

**Change `_collect_results()` — merge dedup + apply ordering**:
- Dedup with merge: when a duplicate is found, merge `match_context` dicts and fill null fields from the later occurrence (preserves vector similarity + SQL evidence)
- If `self._declared_order` is set, reorder the merged list to match
- Unmentioned profiles append at the end (fallback = current behavior)

### Fix 2: Streaming architecture — buffer-then-emit with progress

**Current (broken):** `run_streaming()` emits `result` events as each tool returns. No dedup, no reordering. User sees wrong-ordered results immediately.

**New:** Streaming is a progress-only channel. Results are emitted once, in final order, after the agent loop completes.

```
FE sees:
  {"type": "thinking", "message": "Searching your network..."}
  {"type": "thinking", "message": "Found 15 candidates from database..."}
  {"type": "thinking", "message": "Found 8 candidates from semantic search..."}
  {"type": "thinking", "message": "Ranking 19 candidates..."}
  {"type": "results", "payload": [ordered SearchResultItem list]}
  {"type": "done", "payload": {"answer": "...", "query_type": "..."}}
```

**Candidate count via instance state (C4 pattern):**
`_execute_tool()` sets `self._last_candidate_count` in result-producing branches (`search_profiles`, `execute_sql`, `find_intro_paths`). Streaming reads it after each tool call — no return type change, consistent with existing patterns (`_web_search_count`, `_declared_order`).

**Changes:**
- `run_streaming()`: Remove per-tool-call result emission (lines 916-932). After each result-producing tool call, emit thinking event with `self._last_candidate_count`. After loop completes, call `_collect_results()` (which applies merge dedup + `set_result_order`), emit single `results` event.
- `run_turn()`: Already uses `_collect_results()` — just needs `self._declared_order` wired in.
- FE: Update `useStreamingSearch` to handle batch `results` event instead of individual `result` events. Show loading state with progress messages during `thinking` events.

### Fix 3: System prompt — ordering workflow + evidence + experience guidance

**File:** `src/linkedout/intelligence/prompts/search_system.md`

Add after the "Rules" section:

```markdown
## Result Ordering

Results appear to the user in the order you declare. Your workflow:
1. Gather candidates using `search_profiles` and/or `execute_sql`
2. Evaluate relevance to the user's query
3. Call `set_result_order` with profile IDs ranked best-first
4. Write your summary

Call `set_result_order` BEFORE your final summary. Without it, results appear in tool-call order (usually wrong).

## Evidence Columns

When writing SQL, include extra columns that explain WHY a person matched. Any column beyond the standard fields automatically appears as evidence in the UI:
```sql
SELECT cp.full_name, ...,
       e.position AS matched_role,
       e.company_name AS evidence_company
FROM ...
```

## Experience Table

For expertise/skill queries, the `experience` table has the strongest signal — position titles and descriptions reveal what someone actually worked on:
```sql
SELECT cp.*, e.position, e.description AS role_description
FROM crawled_profile cp
JOIN connection c ON c.crawled_profile_id = cp.id
JOIN experience e ON e.crawled_profile_id = cp.id
WHERE e.position ILIKE '%evals%' OR e.description ILIKE '%evals%'
```

This is stronger than filtering on `headline` alone, especially for enriched profiles (`has_enriched_data = TRUE`).
```

### Fix 4: Vector search — low DB-side floor (noise removal)

**File:** `src/linkedout/intelligence/tools/vector_tool.py`

Add `WHERE` clause with a conservative 0.25 cosine similarity floor. This is garbage collection — removes truly unrelated profiles in sparse embedding space — not a quality filter. The LLM + `set_result_order` handle the real filtering.

```sql
WHERE cp.embedding IS NOT NULL
  AND 1 - (cp.embedding <=> CAST(:query_embedding AS vector)) > 0.25
ORDER BY cp.embedding <=> CAST(:query_embedding AS vector)
LIMIT :limit
```

Why 0.25 (not 0.20 or 0.30):
- Model is `text-embedding-3-small` (1536d). Relevant matches typically score 0.35+.
- 0.25 only removes true garbage (completely unrelated profiles). Safe for any query type.
- The LLM sees similarity scores in the results and `set_result_order` is the real quality gate.

## Files to Modify

| File | Change | Size |
|------|--------|------|
| `src/linkedout/intelligence/agents/search_agent.py` | Add `set_result_order` tool def + handler, `_last_candidate_count` instance state, merge dedup in `_collect_results()`, refactor `run_streaming()` to buffer-then-emit with progress | ~80 lines |
| `src/linkedout/intelligence/prompts/search_system.md` | Add ordering workflow, evidence, experience sections | ~30 lines |
| `src/linkedout/intelligence/tools/vector_tool.py` | Add 0.25 similarity floor | ~2 lines |
| FE: `useStreamingSearch` hook | Handle batch `results` event, remove individual `result` handling, show progress messages | ~20 lines |

## What We're NOT Doing
- No separate re-ranking system or post-hoc scorer
- No prescriptive ranking logic in prompts (LLM decides what "best" means per query)
- No changes to affinity scoring or Dunbar tiers
- No backward compatibility with old streaming protocol — clean cut

## Observability

Existing `@observe(name="tool_call")` on `_execute_tool` already captures every `set_result_order` call in Langfuse traces with full args — including the accounting response (ordered_count, requested_count, unknown_ids). No extra instrumentation needed now. Graduate to `langfuse.score()` if we need adoption metrics at scale.

## Verification
1. Re-run "find folks with evals experience"
2. Check that LLM calls `set_result_order` and explicit evals people (Pranavaraj, Ajay, Bijay) rank top
3. Check `match_context` has evidence columns from SQL (e.g., `matched_role`, `evidence_company`)
4. Test an intro-path query ("who can intro me to Anthropic") to confirm no regression
5. Check Langfuse traces for `set_result_order` tool call pattern + accounting response
6. Verify FE shows progress messages during thinking, then renders ranked results in one shot
7. Verify merge dedup: same person from vector + SQL shows both similarity score and match_context
