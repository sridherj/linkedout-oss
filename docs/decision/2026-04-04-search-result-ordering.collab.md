# Decision: Search Result Ordering via Explicit LLM Tool Call

**Date:** 2026-04-04
**Status:** Accepted
**Context:** LinkedOut search quality -- result ordering and streaming delivery

## Question
How should the search agent produce ranked results, and how should streaming deliver them without degrading quality?

## Key Findings
- `run_streaming()` bypassed `_collect_results()` entirely -- results streamed as-they-arrive with no dedup or ordering
- Multiple tools (SQL, vector, web) can return the same candidate with different match_context
- The LLM has the best judgment for ranking after seeing all evidence
- Vector similarity threshold of 0.20 was too low for text-embedding-3-small (tighter distribution than older models)

## Decision

**7 design choices made via interview:**

1. **Explicit `set_result_order` tool** -- LLM calls this with ordered crawled_profile_ids when ready to rank. No implicit ordering from tool call sequence.
2. **Full objects in batch** -- set_result_order returns complete profile objects, not just IDs requiring a second fetch.
3. **C4 instance state for progress counts** -- `self._last_candidate_count` set by `_execute_tool`, read by `run_streaming`. Simple, matches existing patterns (`_web_search_count`).
4. **Single ranking mechanism** -- only `set_result_order`, no separate `sort_by`. One way to rank.
5. **No cap on IDs** -- the LLM decides how many results to include.
6. **Unknown IDs: silently ignore + accounting** -- return `ignored_ids` in response so LLM can self-correct, but don't error.
7. **Merge dedup** -- when same candidate appears from multiple tools, combine `match_context` entries rather than keeping only first-seen.

**Streaming: buffer-then-emit** -- collect all results during tool execution, apply ordering when `set_result_order` is called, emit as single batch event. Quality > speed.

**Vector threshold: 0.25** (up from proposed 0.20) for text-embedding-3-small.

## Implications
- Streaming now has a brief delay (buffering) but guarantees correct ordering
- Frontend `useStreamingSearch` updated to handle batch results event
- `crawled_profile_id` is the canonical ID across all result paths (not `connection_id`)
- 18 new unit tests cover ordering, dedup, unknown IDs, and streaming buffer behavior
- System prompt updated with ordering workflow guidance for the LLM

## References
- `docs/plan/2026-04-04-search-result-ordering-quality.md` -- original plan (with gaps identified)
- `src/linkedout/intelligence/agents/search_agent.py` -- implementation
- `tests/unit/intelligence/test_result_ordering.py` -- test coverage
