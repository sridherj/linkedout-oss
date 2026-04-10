# Sub-phase 6a: Context Engineering & Conversational Tools

## Prerequisites
- **SP5 complete** (session persistence must exist for multi-turn state)

## Outcome
The LLM handles all 11 interaction patterns (Refine, Continue, Pivot, Narrow, Broaden, Explain, Compare, Aggregate, Exclude, Sort/Rank, Save/Tag) naturally through context engineering and tool design. NO pattern router or classifier in application code.

## Estimated Effort
5-6 sessions

## Verification Criteria
- [ ] Validation test cases for all 11 interaction patterns pass
- [ ] Multi-pattern messages work ("Remove FAANG people and rank the rest by affinity")
- [ ] LLM asks clarifying questions for ambiguous intent
- [ ] Sliding window + summary works for 20+ turn conversations without losing original query intent
- [ ] In-memory filtering (Refine, Exclude) <100ms
- [ ] Each turn response includes: message, result_summary_chips, suggested_actions, exclusion_state, result_metadata, facets

---

## Activities

### 6a.1 Sliding-Window Context Strategy
- Construct LLM context per turn:
  `[system prompt] + [structured summary of older turns] + [recent N turns verbatim] + [current result set summary] + [session state: exclusions, tags, filters] + [available tools]`
- Default: `summary_window_size=2` (spike-validated)
- **Design production context injection fresh** -- spike's `_inject_conversation_history()` and `run_turn()` are experiments, not production code
- Structured summary must explicitly preserve: original query intent, current result set membership, active exclusions, applied tags, current sort order
- **Key insight from spike:** Structured summary outperforms raw history replay because it forces explicit state preservation rather than relying on the LLM to extract it from verbose tool output. The `selective` replay mode was ruled out (not worth complexity).

### 6a.2 In-Memory Result Set Tools (CRITICAL)
- Multi-turn spike confirmed: the LLM re-runs SQL from scratch each turn, causing accumulated filters to get lossy. In-memory tools are the fix.
- **File:** `src/linkedout/intelligence/tools/result_set_tool.py` (new)

**`filter_results`:**
- Input: `{attribute: str, operator: eq|contains|gt|lt|in, value: any}`
- Operates on current result set (stored in session). No DB query
- Returns filtered set with count + updated facets

**`exclude_from_results`:**
- Input: `{profile_ids: [str]}` or `{criteria: {attribute, operator, value}}`
- Removes from current result set, adds to `excluded_ids` in session state
- Returns updated set + exclusion record (for undo)

**`tag_profiles`:**
- Input: `{profile_ids: [str], tag_name: str, action: add|remove}`
- Persists to SearchTag entity (from SP5)
- Returns confirmation

**`get_tagged_profiles`:**
- Input: `{tag_name: str, session_id: optional}`
- Returns profiles with that tag (global or session-scoped)

**`rerank_results`:**
- Input: `{dimension: affinity|tenure|seniority|recency|custom, order: asc|desc}`
- Re-sorts current result set
- For qualitative dimensions ("rank by how strong my connection is"), delegates to LLM reasoning

**`aggregate_results`:**
- Input: `{dimension: str, operation: count|avg|group_by|distribution}`
- Computes over current result set
- Returns structured aggregation result

**`get_profile_detail`:**
- Input: `{profile_id: str}`
- Returns full profile: experience timeline, education, skills, company details, affinity breakdown (including sub-scores), connection metadata, tags
- Shared with SP6b -- must return all data needed for the 4-tab slide-over panel

### 6a.3 Facet Counts on Result Set
- Every search response and every result set operation must include updated facet summaries:
  `facets: [{group, items: [{label, count, checked}]}]`
- Facet groups computed from current result set: Dunbar Tier, Location, Seniority, Company Stage
- Computed in-memory from stored result snapshot -- no DB roundtrip
- Counts update after exclusions (removing FAANG drops counts accordingly)
- **Implementation:** `compute_facets(result_set)` utility that groups profiles by known dimensions

### 6a.4 Interaction Hint Suggestions
- After each LLM turn, response includes `suggested_actions: [{type, label}]` (3-5 contextual follow-up suggestions)
- Types: `narrow`, `rank`, `exclude`, `broaden`, `ask`
- LLM-generated: add to system prompt: "After each response, suggest 3-5 natural follow-up actions the user might take, formatted as `suggested_actions`"
- Context-aware -- reflect current result set state, not generic suggestions
- **Design reference:** `<linkedout-fe>/docs/design/conversation-history-followup.html` -- hint chips below follow-up bar

### 6a.5 LLM Response Format for Conversation Turns
- Each turn response must include:
  - `message`: natural language response text
  - `result_summary_chips: [{text, type: "count"|"filter"|"sort"|"removal"}]` -- inline summary in conversation thread
  - `suggested_actions`: see 6a.4
  - `exclusion_state: {excluded_count, excluded_description, undoable}` -- for excluded profiles banner
  - `result_metadata: {count, sort_description}` -- for results header
  - `facets`: see 6a.3
- Add this structured output format to the search agent's system prompt

### 6a.6 Session State Update Flow
- After each LLM turn: persist updated result set, exclusions, tags, conversation history
- **Store result snapshots per turn** (spike recommendation) -- the LLM needs to know the current result set, not just what SQL was run
- Handle undo: maintain a stack of result set states per session for Refine/Exclude undo

### 6a.7 Handle Pivot
- When LLM starts a fresh search (new intent, no reference to prior results): create new session, archive previous
- Detection: check if LLM called `execute_sql`/`search_profiles` with completely new query vs using result set tools
- Alternative: add `start_new_search` tool the LLM can explicitly call to signal a pivot

### 6a.8 Validate All 11 Interaction Patterns
- **Live LLM test cases in benchmark suite** (not pytest) -- Plan Review Amendment T2
- Use Claude Code judge scorer to evaluate tool selection and result correctness:
  1. **Refine**: Search -> "Show only Bangalore" -> filter applied, original set preserved
  2. **Continue**: Search -> "Do any have voice AI?" -> references "them" correctly
  3. **Pivot**: Search -> "Forget that, find Stripe people" -> new session created
  4. **Narrow**: Search -> "Only if 2 internships at Series A" -> re-executed with constraints
  5. **Broaden**: Search -> "Include any cloud infra, not just K8s" -> relaxed constraint
  6. **Explain**: Search -> "Why Rahul?" -> detailed explanation with match dimensions
  7. **Compare**: Search -> "Between Priya and Arun for CTO" -> structured comparison
  8. **Aggregate**: Search -> "What cities are they in?" -> aggregation computed
  9. **Exclude**: Search -> "Remove FAANG" -> removal, persistence in session
  10. **Sort/Rank**: Search -> "Rank by connection strength" -> re-sorted
  11. **Save/Tag**: Search -> "Tag Priya as shortlist-ml" -> tag persisted, retrievable
- Multi-pattern: "Remove FAANG and rank rest by affinity" -> both tools invoked in order

### 6a.9 Performance
- In-memory operations (filter, exclude, rerank) must complete <100ms
- These bypass the LLM entirely for simple filters
- Complex filters requiring LLM reasoning use result set tools, not fresh SQL

### 6a.10 Frontend
- **Design reference:** `<linkedout-fe>/docs/design/conversation-history-followup.html`
- Conversation thread above results: user bubbles + system bubbles with inline result summary chips
- System bubbles include removal chips ("−9 FAANG") and undo indicators
- Turn dividers with "Turn N" labels
- Follow-up input bar replaces search bar in active session
- Interaction hint chips below follow-up bar (from `suggested_actions`)
- Excluded profiles banner above results with undo button
- Results header: count + current sort ("13 results · sorted by promo recency")

---

## Design Review Notes

| ID | Issue | Resolution |
|----|-------|------------|
| Architecture | NO pattern router (Decision #10) | 11 patterns are validation test cases. LLM selects tools from context |
| T2 | Interaction pattern tests: live LLM or mocked? | Live LLM in benchmark suite (not pytest). Quality validation |
| Architecture | MAX_ITERATIONS for follow-up turns | May need increase vs initial search. Monitor -- result set tools are fast |
| Error path | Result set tools produce empty results | LLM informs user, suggests relaxation. Natural behavior with right context |
| Security | Result set tools operate on session-scoped data | In-memory set loaded from tenant+user scoped session. No cross-tenant access |
| Spike reference | sql_tool.py error rollback fix | Legitimate production bugfix from multi-turn spike. Keep as-is |

## Key Files to Read First
- `src/linkedout/intelligence/agents/search_agent.py` -- search flow to extend with multi-turn
- `src/linkedout/intelligence/contracts.py` -- spike contracts (inform, don't extend)
- `src/linkedout/intelligence/tools/sql_tool.py` -- existing tool pattern + rollback fix (keep)
- `.taskos/spike_multiturn_conversation_results.ai.md` -- replay mode comparison, code changes
- `.taskos/exploration/playbook_conversational_search.ai.md` -- conversational tools playbook
- `<linkedout-fe>/docs/design/conversation-history-followup.html` -- UI design
