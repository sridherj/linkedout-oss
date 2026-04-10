# Phase H.4: Update linkedout_intelligence Spec

**Effort:** 30 min
**Dependencies:** Phases B+C complete (web search tool, prompt simplification)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Update the intelligence spec to reflect the new tool-first architecture.

## What to Do

### 1. Read current spec

**File:** `./docs/specs/linkedout_intelligence.collab.md`

### 2. Use the taskos-update-spec agent

Invoke `/taskos-update-spec` with these changes:

**Add:**
- `web_search` tool: delegates to OpenAI Responses API (gpt-4.1-mini + web_search_preview), 10s timeout, 3 calls/turn max
- Funding table access: `funding_round` and `startup_tracking` visible in schema context and SQL tool
- Simplified prompt philosophy: capabilities-oriented vs. prescriptive routing
- SQL resilience rules: zero-result fallback, timeout recovery

**Remove:**
- Result set tools: `filter_results`, `exclude_from_results`, `rerank_results`, `aggregate_results`, `start_new_search`
- Prescriptive "When to Use Which Tool" decision table
- `ContextStrategy`, `ConversationState`, `ConversationConfig`, `ExclusionState` contracts

**Update:**
- Tool list: add web_search, update intro_tool to 5 tiers, remove result set tools
- Architecture section: note tool-first approach
- Cross-references to ConversationManager (in llm_client spec)

## Verification

- Spec accurately reflects the implemented search agent
- Tool list matches actual registered tools
- No references to removed concepts
