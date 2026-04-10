# Search Agent Quality V2: Tool-First, Not Prompt-First

**Date:** 2026-04-02
**Status:** Spike validated, ready to implement
**Predecessor:** [search-quality-overhaul.collab.md](search-quality-overhaul.collab.md) (Phase 1: prompt/data fixes)

---

> **CRITICAL — Workspace & File Resolution Rules**
>
> These rules apply to this plan, all execution sub-phases, and any artifacts derived from it.
>
> 1. **Repo locations:**
>    - Frontend code: `<linkedout-fe>`
>    - Backend code: `.`
>    - When working on frontend phases (G, H.2) or any frontend-related spec updates, **always read `<linkedout-fe>/CLAUDE.md` first.**
> 2. **File search scope:** When searching for files during frontend phases, **search both `<linkedout-fe>` and `.`**. Backend types, SSE contracts, and API schemas are defined in the backend repo but consumed by the frontend.
> 3. **Use full absolute paths** in all plans, execution phases, and artifacts. Never use relative paths or assume a file location. **If you cannot locate a file, STOP and ask** — do not guess or proceed with a wrong path.

---

## The Problem

The search agent scores ~3.1/5 average across 32 hard benchmark queries. When Claude Code (a human + LLM with DB access + web search) handled the same queries, it produced dramatically richer results.

### Concrete Example: "Find people who can help me reach out to Lovable"

**Claude Code found (4 tiers, ~10 people):**
1. Direct employee — Abhijeet Jha, Member of Technical Staff at Lovable (from DB)
2. Community/ambassadors — Anadee (Lovable Ambassador), Nayana K. (headline mentions Lovable) (from DB, headline search)
3. Investor connections — Chitranjan Jain, Rachitt Shah at Accel (Claude Code **web-searched** "Lovable investors" to learn Accel invested, then queried DB for Accel connections)
4. Former colleague warm paths — Dunzo/Google alumni who overlapped with Abhijeet (from DB, career history cross-reference)

**The search agent found (1 tier, 1 person):**
1. Abhijeet Jha — direct employee at Lovable

The agent missed tiers 2-4 entirely.

### Why the Agent is Shallow

The gap is NOT that the agent doesn't know how to think. GPT-5.4 is perfectly capable of decomposing queries and running multi-step searches. **The gap is that the agent lacks the tools to do what the LLM would naturally do.**

| What the LLM would naturally do | What's blocking it |
|---|---|
| Web search "who invested in Lovable" | No web search tool exists |
| Query funding/investor data | `funding_round` and `startup_tracking` tables are invisible (not in schema context) |
| Search headlines for brand mentions | `find_intro_paths` only checks `current_company_name`, not `headline` |
| Run 4-5 targeted sub-queries | Nothing blocking this per se — but without web search + full data, there's nothing useful to decompose *into* |

### The Key Insight

> Instead of writing an elaborate prompt that teaches the LLM *how* to decompose queries (worked examples, mandatory planning protocols, etc.), **give it the right tools and let it do what it would naturally do.**
>
> Claude Code didn't need a "decomposition protocol" — it had DB access + web search + a simple goal. The LLM naturally planned, searched, queried, and synthesized.

This means: **simpler prompt + richer tools > elaborate prompt + limited tools.**

## Spike Validation (2026-04-02)

Ran `tmp_spike_web_search.py` — a minimal script giving GPT-5.4 just two tools (execute_sql + web_search) and a 12-line system prompt. No decomposition protocol, no worked examples, no routing rules.

**Results matched Claude Code quality:**

| Tier | Claude Code | GPT-5.4 Spike | Notes |
|---|---|---|---|
| Direct employee | Abhijeet Jha | Abhijeet Jha | Same |
| Community/ambassadors | Anadee, Nayana K. | Anadee, Nayana K., Mayank S. | Spike found more |
| Investor connections | Chitranjan, Rachitt at Accel | Divyansh, Rachitt, Chitranjan at Accel | Spike found more (web searched investors) |
| Former colleague warm paths | Dunzo/Google overlap (3 people) | Google overlap (6 people, inner_circle tier, affinity 40-49) | Spike found stronger connections |
| Outreach strategy | — | Copy-paste message templates per tier | Bonus |

**Spike stats:** 3 iterations, 7 SQL calls, 1 web search. The LLM naturally:
1. Fired 5 parallel tool calls in iteration 1 (web search + 4 SQL queries)
2. Self-corrected a column name error in iteration 2
3. Synthesized and ranked all tiers with outreach recommendations

**Key finding:** Zero prompt engineering produced Claude Code-quality results. The only things needed were the right tools + data access.

### How Web Search Works (Architecture Decision)

OpenAI's `web_search_preview` is a Responses API feature, not available in Chat Completions API.

**Solution (validated in spike):** Implement `web_search` as a regular function tool. The LLM decides when to call it. The tool's implementation delegates to OpenAI's Responses API with `web_search_preview` on a cheap model (gpt-4.1-mini) for the actual search.

```
Main LLM (GPT-5.4, Chat Completions via LangChain)
  ├── calls execute_sql → runs SQL against PostgreSQL
  ├── calls web_search → delegates to OpenAI Responses API (gpt-4.1-mini + web_search_preview)
  ├── calls search_profiles → pgvector semantic search
  └── calls other tools...
```

**Why this works with LangChain:** `web_search` is just another function tool in `_TOOL_DEFINITIONS`, dispatched in `_execute_tool()` like all the others. No LangChain changes needed. No changes to `llm_client.py` needed. The web search implementation is self-contained in a new tool file.

### Benchmark Score Patterns

Queries that score 2-3 consistently fail for tool/data reasons, not reasoning reasons:

| Query | Score | What's Missing |
|---|---|---|
| sj_01: Warm intros to Stripe | 3 | No multi-hop paths (tool gap) |
| sj_03: People probably hiring | 3 | No funding data (invisible table) |
| sj_09: College alumni doing impressive things | 2 | No web context for "impressive" |
| sj_12: Founders in my network | 2 | Weak signal extraction (tool gap) |
| rec_01: ML engineers, multi-signal | 3 | No compound filtering (tool gap) |
| rec_03: Eng leadership at Series B-C | 3 | No funding stage data (invisible table) |
| fnd_04: Big tech to climate pivot | 2 | No web context for climate companies |
| fnd_06: Early employees at funded startups | 3 | No funding data (invisible table) |
| fnd_08: Repeat founders | 2 | Counting advisory roles (tool gap) |
| rec_10: Non-traditional backgrounds | 2 | No web context for bootcamps |

## Changes (Ordered by Impact)

### Change 1: Add Web Search Tool (HIGHEST IMPACT)

**New file:** `src/linkedout/intelligence/tools/web_tool.py`

```python
"""Web search tool for SearchAgent — delegates to OpenAI Responses API."""
from openai import OpenAI

def web_search(query: str) -> str:
    """Search the internet and return factual results."""
    client = OpenAI(api_key=...)
    resp = client.responses.create(
        model="gpt-4.1-mini",
        tools=[{"type": "web_search_preview"}],
        input=f"Search the web and return factual information: {query}",
    )
    # Extract text from response
    ...
```

**Register in search agent** (`src/linkedout/intelligence/agents/search_agent.py`):
- Add to `_TOOL_DEFINITIONS`:
  ```python
  {
      "type": "function",
      "function": {
          "name": "web_search",
          "description": "Search the internet for context not in the database — "
                         "company info, investors, funding details, industry context, "
                         "recent news, executive teams.",
          "parameters": {
              "type": "object",
              "properties": {
                  "query": {"type": "string", "description": "Search query"}
              },
              "required": ["query"],
          },
      },
  }
  ```
- Add dispatch in `_execute_tool()`:
  ```python
  elif tool_name == "web_search":
      return web_search(tool_args["query"])
  ```

**No changes needed to:** `llm_client.py`, LangChain integration, or the tool-calling loop.

**Guardrails (review decision):**
- **Max 3 web search calls per turn.** Counter in `_execute_tool()` — returns graceful "web search limit reached, work with what you have" after 3 calls. Spike used 1; 3 covers multi-faceted queries (company + investors + news).
- **10s timeout per call.** Set on the OpenAI client in `web_tool.py`. Prevents a single hung search from blocking the turn.

**Impact:** Unblocks every query needing external context. Validated in spike.

### Change 2: Expose Funding Tables to Schema Context (10 min)

**Files:**
- `src/linkedout/intelligence/schema_context.py` — add `FundingRoundEntity` and `StartupTrackingEntity` to `_ENTITIES` list (line 17)
- `src/linkedout/intelligence/tools/sql_tool.py` — add `'funding_round'`, `'startup_tracking'` to `_AVAILABLE_TABLES` (line 15)

**What to add:**
```python
# schema_context.py - imports
from linkedout.funding.entities.funding_round_entity import FundingRoundEntity
from linkedout.funding.entities.startup_tracking_entity import StartupTrackingEntity

# schema_context.py - _ENTITIES list (line 17)
_ENTITIES = [
    CrawledProfileEntity, ConnectionEntity, ExperienceEntity,
    EducationEntity, CompanyEntity, CompanyAliasEntity,
    ProfileSkillEntity, RoleAliasEntity,
    FundingRoundEntity, StartupTrackingEntity,  # NEW
]
```

Add to `_BUSINESS_RULES`:
```
- `funding_round` links to `company` via `company_id`. Contains round_type, amount_usd, lead_investors (text array), all_investors (text). NOT user-scoped (no RLS) — public company data.
- `startup_tracking` links to `company` via `company_id` (1:1). Contains funding_stage, total_raised_usd, vertical, watching flag. NOT user-scoped.
```

**Data status:** Verified — `funding_round` has 198 rows, `startup_tracking` has 182 rows.

**Impact:** Directly unblocks sj_03, rec_03, fnd_06, and any query involving funding stage, investors, or startup classification.

### Change 3: Expand find_intro_paths with Tiers 3-5

**File:** `src/linkedout/intelligence/tools/intro_tool.py`

Current tool has Tier 1 (direct at company) + Tier 2 (alumni). Add:

**Tier 3 — Headline/community mentions:** People mentioning target in headline but not employed there.
```sql
SELECT cp.id, cp.full_name, cp.headline, cp.current_position, cp.current_company_name,
       c.affinity_score, c.dunbar_tier
FROM crawled_profile cp
JOIN connection c ON c.crawled_profile_id = cp.id
WHERE cp.headline ILIKE :pattern
  AND (cp.current_company_name NOT ILIKE :pattern OR cp.current_company_name IS NULL)
ORDER BY c.affinity_score DESC NULLS LAST
LIMIT 10
```

**Tier 4 — Shared-company warm paths:** Connections who worked at same prior companies as target employees. Adapts the `_INTRO_SQL` pattern from `search_controller.py:135`.
```sql
SELECT DISTINCT cp2.id, cp2.full_name, cp2.current_position, cp2.current_company_name,
       c2.affinity_score, c2.dunbar_tier,
       e1.company_name AS shared_company, cp1.full_name AS target_person
FROM crawled_profile cp1
JOIN connection c1 ON c1.crawled_profile_id = cp1.id
JOIN experience e1 ON e1.crawled_profile_id = cp1.id AND e1.company_id IS NOT NULL
JOIN experience e2 ON e2.company_id = e1.company_id AND e2.crawled_profile_id != cp1.id
JOIN crawled_profile cp2 ON cp2.id = e2.crawled_profile_id
JOIN connection c2 ON c2.crawled_profile_id = cp2.id
WHERE cp1.current_company_name ILIKE :pattern
  AND cp2.current_company_name NOT ILIKE :pattern
ORDER BY c2.affinity_score DESC NULLS LAST
LIMIT 10
```

**Tier 5 — Investor connections:** Connections at firms that invested in target. Uses `funding_round.lead_investors` (ARRAY(Text)).
```sql
SELECT cp.id, cp.full_name, cp.current_position, cp.current_company_name,
       c.affinity_score, c.dunbar_tier
FROM funding_round fr
JOIN company co_target ON co_target.id = fr.company_id
CROSS JOIN LATERAL unnest(fr.lead_investors) AS inv(investor_name)
JOIN crawled_profile cp ON cp.current_company_name ILIKE '%' || inv.investor_name || '%'
JOIN connection c ON c.crawled_profile_id = cp.id
WHERE co_target.canonical_name ILIKE :pattern
ORDER BY c.affinity_score DESC NULLS LAST
LIMIT 10
```

**Also update:**
- Tool description in `search_agent.py` (line 205) to advertise all 5 tiers
- Return dict to include `tier3_count`, `tier4_count`, `tier5_count`
- Tests in `tests/unit/intelligence/test_intro_tool.py`

**Note:** With web search (Change 1), the LLM can also discover investors via web and query the DB directly. Tier 5 in the tool is a convenience — the LLM did this naturally in the spike without the tool having it built-in.

### Change 4: Simplify the System Prompt

**File:** `src/linkedout/intelligence/prompts/search_system.md`

**Philosophy:** The current prompt tries to be a decision tree that tells the LLM which tool to use for each query type. This over-constrains the LLM and makes it follow rules instead of thinking. The spike proved that a 12-line prompt with the right tools produces better results than the current 94-line prescriptive prompt.

**What to change:**
- Remove the prescriptive "When to Use Which Tool" decision table (lines 46-54)
- Remove the "Think Before You Write" rules that lock specific tools to specific query patterns (lines 3-12)
- Replace with a simpler capabilities summary:
  ```markdown
  ## Your Capabilities
  
  You have access to the user's LinkedIn network database (~28K connections) and web search.
  
  - **Database tools** let you query connections, experience history, education, skills, 
    company data, and funding information
  - **Web search** lets you look up anything not in the database — company info, investors, 
    industry context, recent news
  - **Semantic search** lets you find people by meaning/concept when SQL isn't enough
  - **Helper tools** resolve company names, classify companies, analyze career patterns
  
  Be thorough. Combine multiple tools for complex queries. A good answer to 
  "who can intro me to X" might use web search (learn about the company/investors), 
  database queries (find connections), and career analysis (identify warm paths).
  ```
- Keep the schema context, enum values, output format, and safety rules unchanged
- Keep the result set tool guidance (filter/exclude/rerank) since those are session-specific

**Impact:** Lets the LLM use its natural reasoning instead of following a script. Validated in spike.

### Change 5: Turn Table + Simple Conversation History

**Problem:** The current multi-turn system is over-engineered:
- `conversation_state` on the session entity gets **overwritten** each turn — only the last turn's transcript survives
- 7 result set tools try to manage state in-memory (filter/exclude/rerank/aggregate/start_new_search)
- Complex `_inject_conversation_history()` with 3 unused context strategies
- Synthetic "result set state" injection with fake user/assistant exchanges

**Example of why this is fragile:**
```
Turn 1: "find out folks who can connect me to Palo Alto Networks"
Turn 2: "only people I know very well"              → should filter by affinity
Turn 3: "never mind, anyone who worked with me"     → should BROADEN back
```

Turn 3 breaks the current model. The LLM can't broaden because it's mutating an in-memory result set.

**The fix:** Three things — persist each turn separately, let the LLM handle history naturally, and make the frontend own session lifecycle.

**Key design decisions (from plan review):**
- **Frontend owns session lifecycle.** Backend has zero pivot detection or auto-archiving logic. New conversation = frontend sends no `session_id`. Continuation = frontend sends `session_id`. Backend is stateless with respect to session decisions.
- **Conversation history management lives in `llm_manager/`, not `LLMClient`.** New `ConversationManager` class in `src/utilities/llm_manager/conversation_manager.py` — generic infrastructure, but caller provides the summarization prompt. `LLMClient` stays untouched.
- **No backward compatibility.** Existing search history in DB can be discarded. Old columns/contracts removed outright.

#### Sub-phase D.1: `search_turn` table (MVCS stack)

```
search_turn
  id            (prefixed PK, "sturn_xxx")
  session_id    (FK → search_session)
  turn_number   (int, 1-indexed)
  user_query    (text)
  transcript    (JSONB — full messages including tool calls/results for this turn)
  results       (JSONB — the result set produced this turn)
  summary       (text, nullable — LLM-generated summary, cached after first generation)
  created_at
```

- **Each turn writes a new row** instead of overwriting `conversation_state` on the session
- **Session entity cleanup:** Keep `turn_count`, `initial_query`, `last_active_at`. Drop `conversation_state`, `excluded_ids`, `accumulated_filters`, `result_snapshot`, `status`. Sessions are listed by `last_active_at` — no active/archived distinction.
- **History reconstruction**: `SELECT * FROM search_turn WHERE session_id = ? ORDER BY turn_number`
- **Future**: "go back to turn 3 results" is just a query by turn_number

**Execution:** Use `crud-orchestrator-agent` (`.claude/agents/crud-orchestrator-agent.md`) for the SearchTurn MVCS stack. After completion, run `crud-compliance-checker-agent` to audit. The entity lives in the existing `search_session` module — no new module needed.

**Files:**
- **NEW** `src/linkedout/search_session/entities/search_turn_entity.py`
- **NEW** `src/linkedout/search_session/repositories/search_turn_repository.py`
- **NEW** `src/linkedout/search_session/services/search_turn_service.py`
- **NEW** `src/linkedout/search_session/schemas/search_turn_schema.py`
- **NEW** `src/linkedout/search_session/schemas/search_turn_api_schema.py`
- `src/linkedout/search_session/entities/search_session_entity.py` — drop `conversation_state`, `excluded_ids`, `accumulated_filters`, `result_snapshot` columns
- Alembic migration for both changes

#### Sub-phase D.2: ConversationManager (generic infrastructure)

**New file:** `src/utilities/llm_manager/conversation_manager.py`

```python
class ConversationManager:
    def __init__(
        self,
        summarization_prompt: str,  # caller provides — domain-specific
        model: str = "gpt-4.1-mini",  # cheap model for summarization
        recent_turns: int = 4,  # how many turns to keep verbatim
    ):
        ...

    def build_history(
        self, turns: list[dict],  # turn rows from DB
    ) -> list[dict]:  # messages ready to inject into LLMMessage
        """Recent N turns verbatim, older turns summarized using caller's prompt."""
        ...
```

- Caller (SearchAgent) initializes with `intelligence/summarize_turns` prompt loaded via PromptManager
- A different agent could pass a completely different summarization prompt
- Summary generated once per turn (when conversation exceeds N turns), then **cached on the turn row** (`search_turn.summary`) so we never re-summarize

**Summarization prompt** (~5 lines, loaded via `PromptManager` per the [prompt_management spec](../specs/prompt_management.collab.md)):
- **NEW** `prompts/intelligence/summarize_turns.md` — loaded via key `intelligence/summarize_turns`
```markdown
Summarize this search conversation concisely. Include:
- What the user was looking for
- Key results found (names, companies)
- Any filters/preferences expressed
Keep the summary under 500 tokens.
```

**Context construction per turn:**
```
[system prompt]
+ [cached summary of turns 1..K]     ← from search_turn.summary or generated + cached
+ [recent N turns verbatim]           ← from search_turn.transcript
+ [current user message]
```

**Config:**
```python
# src/shared/config/config.py
SUMMARIZE_BEYOND_N_TURNS: int = 4
```

#### Sub-phase D.3: Rewire SearchAgent + remove result set tools

- Replace `_inject_conversation_history()` with ConversationManager call
- Remove `filter_results`, `exclude_from_results`, `rerank_results`, `aggregate_results`, `start_new_search` from `_TOOL_DEFINITIONS` and `_execute_tool()` dispatch
- Remove `_current_result_set`, `_excluded_ids`, `_pivot_detected` state from agent
- Keep `tag_profiles`, `get_tagged_profiles` (DB-persisted, useful)
- Keep `compute_facets` (used for UI facets)
- Remove `ContextStrategy` enum from contracts
- Remove `ConversationState`, `ConversationConfig` from contracts (replaced by turn rows)

**Files:**
- `src/linkedout/intelligence/agents/search_agent.py` — use ConversationManager, remove result set tools, remove `_inject_conversation_history`, remove `_current_result_set`/`_excluded_ids`/`_pivot_detected`
- `src/linkedout/intelligence/tools/result_set_tool.py` — remove filter/exclude/rerank/aggregate, keep tag/compute_facets
- `src/linkedout/intelligence/contracts.py` — remove `ContextStrategy`, `ConversationState`, `ConversationConfig`, `ExclusionState`
- `src/linkedout/intelligence/prompts/search_system.md` — remove result set tools section

#### Sub-phase D.4: Simplify search controller

- Remove `_create_or_resume_session` (frontend decides)
- Remove `_save_session_state` complexity — just write a `search_turn` row per turn
- Remove `_handle_pivot` — no pivot detection
- Remove `get_latest_active` auto-archiving
- Controller receives `session_id` from frontend. If provided, fetch turn history and pass to agent via ConversationManager. If not provided, create new session.
- Remove `agent.excluded_ids`, `agent.current_result_set` reads after run
- Simplify SSE `conversation_state` event — remove `exclusion_state`

**Files:**
- `src/linkedout/intelligence/controllers/search_controller.py` — major simplification

**Impact:** Full turn history in DB, any agent can use ConversationManager, natural broadening/narrowing/pivoting, dramatically simpler code.

### Change 6: SQL Resilience (low effort, prevents regressions)

**File:** `src/linkedout/intelligence/prompts/search_system.md`

Add to Rules section:
```markdown
- **Zero-result fallback:** If a query returns 0 results, try a simpler version before giving up. 
  Remove the most restrictive filter.
- **Timeout recovery:** If SQL times out (5s limit), simplify. Prefer UNION of simple queries 
  over one complex multi-JOIN query.
```

## Implementation Sequence

| Phase | Changes | Effort | Expected Impact |
|---|---|---|---|
| A | Change 2 (expose funding tables) | 15 min | +1-2 pts on 3-5 queries |
| B | Change 1 (web search tool, 3 calls max, 10s timeout) | 1 session | +0.5-1.0 avg across 10-15 queries |
| C | Change 4 + 6 (prompt simplification + SQL resilience) | 1 session | Unlocks natural LLM reasoning |
| D | Change 5 (multi-turn overhaul, 4 sub-phases) | 1-2 sessions | Cleaner code, natural conversation flow |
| D.1 | — `search_turn` table MVCS stack + session entity cleanup | | |
| D.2 | — `ConversationManager` in `llm_manager/` | | |
| D.3 | — Rewire SearchAgent + remove result set tools | | |
| D.4 | — Simplify search controller | | |
| E | Change 3 (intro tool tiers 3-5) | 1 session | +1-2 pts on intro queries |
| F | Full benchmark run + iterate | 1 session | Measure, fix stragglers |
| G | Frontend changes (separate repo: linkedout-fe) | 1-2 sessions | Session lifecycle ownership, remove stale UI state |
| G.1 | — Session resume via turn history + remove ExcludedBanner | | |
| G.2 | — Frontend owns session lifecycle | | |
| G.3 | — Test updates | | |
| H | Spec updates | 1 session | Keep specs in sync with implementation |
| H.1 | — `search_sessions.collab.md` — major rewrite (drop old columns, add SearchTurn, remove ContextStrategy/pivot detection, frontend-owned lifecycle) | | |
| H.2 | — `search_conversation_flow.collab.md` — remove T10, update T7/T8/T11, remove exclusionState, turn-based resume | | |
| H.3 | — `llm_client.collab.md` — add ConversationManager as companion utility | | |
| H.4 | — `linkedout_intelligence.collab.md` — add web search tool, funding table access, simplified prompt, remove result set tools | | |

Phase A first (15 min, immediate unblock). Phase B next (highest impact, spike-validated). Phase C alongside B (prompt changes are quick). Phase D after B+C stabilize (multi-turn is the biggest change, sub-phases keep it manageable). Phase E last (nice-to-have since the LLM already does multi-hop naturally with web search). Phase G is a separate frontend effort after backend stabilizes. Phase H (spec updates) should be done alongside each phase — H.1 with D, H.2 with G, H.3 with D.2, H.4 with B+C.

## What We're NOT Doing (and why)

- **No query router / specialized prompts** — The LLM doesn't need routing. It needs tools. The spike proved a 12-line prompt beats a 94-line prescriptive prompt when the tools are right.
- **No decomposition protocol / worked examples** — Over-engineers the prompt. The LLM naturally decomposes when given the tools to act on each sub-query.
- **No multi-agent orchestrator** — Single agent with richer tools is simpler and lower latency.
- **No LangChain changes** — Web search is a regular function tool. No changes to `llm_client.py` needed.
- **No in-memory result set management** — The LLM can re-query with adjusted criteria. Filter/exclude/rerank tools add complexity without matching what the LLM would naturally do (just run a new query).
- **No backend pivot detection** — Frontend owns session lifecycle. Backend receives `session_id` or doesn't. No auto-archiving, no `get_latest_active`, no `start_new_search` tool.
- **No conversation history in LLMClient** — `LLMClient` stays a clean provider abstraction. Conversation management lives in `ConversationManager` (generic `llm_manager/` utility), caller passes summarization prompt.
- **No backward compatibility** — Existing search history discarded. Old columns/contracts removed outright.

## Verification

### New Test Files to Create

| Test File | Phase | What It Tests |
|---|---|---|
| `tests/unit/intelligence/test_web_tool.py` | B | Web search delegation, 3-call limit, 10s timeout, error handling, response extraction |
| `tests/unit/utilities/test_conversation_manager.py` | D.2 | Recent turns verbatim, older turns summarized, summary caching, custom prompt injection, edge cases (0 turns, 1 turn, exactly N turns) |
| `tests/unit/search_session/test_search_turn_repository.py` | D.1 | CRUD wiring (via crud-orchestrator) |
| `tests/unit/search_session/test_search_turn_service.py` | D.1 | Service wiring (via crud-orchestrator) |
| `tests/integration/linkedout/intelligence/test_multiturn_integration.py` | D.4 | Full 4-turn conversation against real DB: narrow → broaden → refine → verify turn rows persisted |
| `tests/integration/linkedout/intelligence/test_web_search_integration.py` | B | Live web search call (marked `live_llm`, skipped in CI) — verifies OpenAI Responses API returns results |

### Existing Tests That Need Updating

| Test File | Phase | What Changes |
|---|---|---|
| `tests/unit/intelligence/test_result_set_tool.py` | D.3 | Remove tests for `filter_results`, `exclude_from_results`, `rerank_results`, `aggregate_results`. Keep `compute_facets` tests. |
| `tests/eval/multi_turn_runner.py` | D.3 | Rewrite: remove `ContextStrategy`, `ConversationState`, `ConversationConfig` imports. Use `ConversationManager` + `search_turn` rows. |
| `tests/eval/test_multiturn_poc.py` | D.3 | Rewrite: remove `ContextStrategy` references. Single replay mode via `ConversationManager`. Update 5-turn scenario to not depend on result set tools (turn 4 "exclude" becomes a re-query, turn 5 "aggregate" becomes SQL aggregation). |
| `tests/eval/test_search_quality.py` | C | May need updates if `SearchAgent.run()` signature changes. Verify it still works with simplified prompt. |
| `tests/integration/linkedout/intelligence/test_search_integration.py` | A | Add test: verify `funding_round` and `startup_tracking` are queryable via `execute_sql` with RLS session. |
| `<linkedout-fe>/src/__tests__/hooks/useStreamingSearch.test.ts` | G.3 | Remove `exclusionState` tests. Update `restoreResults`/`restoreTurns` for turn-based flow. |
| `<linkedout-fe>/src/__tests__/components/search/SearchPageContent.regression-001.test.tsx` | G.3 | Remove `result_snapshot` references. Update session resume to use turn API. |
| `<linkedout-fe>/src/__tests__/hooks/useStreamingSearch.split-panel-bugs.test.ts` | G.3 | Review `restoreResults` tests — likely minor updates. |

### Per-Phase Gates

Each phase has a verification gate that must pass before moving to the next.

**Phase A (funding tables):**
- `pytest tests/unit/intelligence/ -v` — all existing tests still pass (no regressions)
- `pytest tests/integration/linkedout/intelligence/ -v` — new funding table test passes
- Manual: run "people at Series B startups" — agent sees funding tables in schema context, queries them, returns results

**Phase B (web search tool):**
- `pytest tests/unit/intelligence/test_web_tool.py -v` — all new tests pass:
  - Successful web search returns extracted text
  - 4th call in same turn returns "limit reached" message
  - Timeout after 10s returns graceful error
  - Network error returns graceful error (not stack trace)
  - Empty/null query returns validation error
- `pytest tests/integration/linkedout/intelligence/test_web_search_integration.py -v -m live_llm` — live call succeeds
- Manual: "find people who can help me reach out to Lovable" — 4+ tiers, ~15 people, matches spike results

**Phase C (prompt simplification):**
- `pytest tests/unit/intelligence/ -v` — all tests pass
- Manual: run 3-4 representative queries to sanity-check the simplified prompt produces reasonable results
- Note: full benchmark run deferred to Phase F — prompt simplification is validated by unit tests + manual spot checks here

**Phase D (multi-turn overhaul):**
- D.1:
  - `crud-compliance-checker-agent` passes on SearchTurn MVCS stack
  - `uv run validate-orm` succeeds (new entity registered)
  - `alembic upgrade head` applies cleanly (drop columns + new table)
  - `pytest tests/unit/search_session/ -v` — CRUD wiring tests pass
- D.2:
  - `pytest tests/unit/utilities/test_conversation_manager.py -v` — all pass:
    - 0 turns → empty history
    - 3 turns (< N) → all verbatim, no summarization
    - 6 turns (> N=4) → turns 1-2 summarized, turns 3-6 verbatim
    - Summary cached on turn row, not re-generated on second call
    - Custom summarization prompt is used (not hardcoded)
- D.3:
  - `pytest tests/unit/intelligence/ -v` — all tests pass after removing result set tool tests
  - Grep verification: `filter_results`, `exclude_from_results`, `rerank_results`, `aggregate_results`, `start_new_search` do NOT appear in `_TOOL_DEFINITIONS` or `_execute_tool()`
  - `_current_result_set`, `_excluded_ids`, `_pivot_detected` do NOT appear in `search_agent.py`
  - `ContextStrategy`, `ConversationState`, `ConversationConfig` do NOT appear in `contracts.py`
- D.4:
  - Manual multi-turn test (7 turns — covers narrow, broaden, pivot-like, cross-reference, aggregate):
    ```
    Turn 1: "find out folks who can connect me to Palo Alto Networks"
            → results: direct connections + alumni + warm paths
    Turn 2: "only people I know very well"
            → narrowed: LLM re-queries with affinity/dunbar filter (NOT filter_results tool)
    Turn 3: "never mind, anyone who worked with me"
            → broadened: LLM re-queries without affinity constraint
    Turn 4: "who among them are in cybersecurity or infra"
            → refined: LLM adds role/skill filter
    Turn 5: "what companies are they at?"
            → aggregation: LLM runs SQL GROUP BY on results
    Turn 6: "tag the top 3 as palo-alto-intros"
            → tag tool: persists tags to DB
    Turn 7: "show my palo-alto-intros tag"
            → retrieves tagged profiles
    ```
    Verify: `SELECT * FROM search_turn WHERE session_id = '...' ORDER BY turn_number` returns 7 rows.
    Verify: Turn 7 LLM context includes summarized history from earlier turns.
    Verify: Turn 3 successfully broadens (the original broken case from the problem statement).
    Verify: Tags from turn 6 are retrievable in turn 7.
  - `precommit-tests` — full backend suite (unit + integration + live_llm) passes
  - `pytest tests/eval/test_multiturn_poc.py -m eval -v` — updated multi-turn eval runs successfully

**Phase E (intro tool tiers 3-5):**
- `pytest tests/unit/intelligence/test_intro_tool.py -v` — new tests pass:
  - Tier 3: finds people with target in headline but not employed there
  - Tier 4: finds shared-company connections (tests with known overlapping experience data)
  - Tier 5: finds investor connections via `funding_round.lead_investors`
  - Empty result handling: tier returns 0 without error
- Manual: "who can intro me to Stripe" — returns 3+ tiers
- Performance: Tier 4 (5-JOIN) and Tier 5 (CROSS JOIN LATERAL) execute in < 5s on full dataset

**Phase F (benchmark + eval iteration):**

This is the iteration phase — run, measure, fix, repeat. Not a gate blocking other phases.

- Run full 32-query benchmark: `python -m src.dev_tools.benchmark`
- Run eval suite: `pytest tests/eval/test_search_quality.py -m eval -v`
- Run multi-turn eval: `pytest tests/eval/test_multiturn_poc.py -m eval -v`
- **Target:** average score ≥ 4.0. No individual query below 3.
- Specific queries to watch (previously scored 2):
  - sj_09 "college alumni doing impressive things" — needs web context → should benefit from web search
  - fnd_04 "big tech to climate pivot" — needs web context for climate companies
  - fnd_08 "repeat founders" — was counting advisory roles
  - rec_10 "non-traditional backgrounds" — needs web context for bootcamps
- For each failing query: document root cause (tool gap vs prompt gap vs data gap), fix, re-run
- This phase may span multiple sessions — that's expected

**Phase G (frontend):**
- G.1: `cd <linkedout-fe> && npm run test` — all updated tests pass
- G.1: Manual: close browser, reopen → session resumes from `search_turn` API
- G.1: Manual: verify `ExcludedBanner` component no longer renders
- G.2: Manual: click "New Search" → state clears, no network call to archive
- G.2: Manual: type follow-up → request includes `session_id`
- G.2: Manual: type in fresh SearchBar → request has no `session_id`
- G.3: `cd <linkedout-fe> && npm run test` — full suite green, zero skipped

**Phase H (spec updates):**
- Each spec update is verified by reading the spec and confirming it matches the implemented behavior. No automated test — specs are documentation.

### Final Acceptance

All phases complete when:
1. `precommit-tests` pass (backend — unit + integration + live_llm)
2. `cd <linkedout-fe> && npm run test` pass (frontend — full suite)
3. 32-query benchmark average ≥ 4.0, no query below 3
4. Manual Lovable test: "find people who can help me reach out to Lovable" produces 4+ tiers with ~15 people
5. Manual Palo Alto Networks multi-turn test: 7-turn sequence (narrow → broaden → refine → aggregate → tag → retrieve) works naturally, all turns persisted as `search_turn` rows
6. Manual session lifecycle: new search (no session_id) → follow-up (with session_id) → new search (no session_id) — all work correctly
7. No removed contracts/tools referenced anywhere in codebase: `grep -r "ContextStrategy\|start_new_search\|_pivot_detected\|result_snapshot\|excluded_ids" src/` returns zero hits

## Critical Files

| File | Changes | Phase |
|---|---|---|
| `src/linkedout/intelligence/tools/web_tool.py` | NEW — web search tool (OpenAI Responses API, gpt-4.1-mini, 10s timeout, 3 calls/turn max) | B |
| `src/linkedout/intelligence/schema_context.py` | Add FundingRoundEntity, StartupTrackingEntity to _ENTITIES | A |
| `src/linkedout/intelligence/tools/sql_tool.py` | Add funding_round, startup_tracking to _AVAILABLE_TABLES | A |
| `src/linkedout/intelligence/prompts/search_system.md` | Simplify prompt: remove prescriptive routing + result set tools sections, add web search + funding tables to capabilities | C |
| `src/linkedout/intelligence/tools/intro_tool.py` | Add Tiers 3-5 (headline, shared-company, investor) | E |
| `src/linkedout/search_session/entities/search_turn_entity.py` | NEW — search_turn entity | D.1 |
| `src/linkedout/search_session/repositories/search_turn_repository.py` | NEW — search_turn repo | D.1 |
| `src/linkedout/search_session/services/search_turn_service.py` | NEW — search_turn service | D.1 |
| `src/linkedout/search_session/entities/search_session_entity.py` | Drop conversation_state, excluded_ids, accumulated_filters, result_snapshot | D.1 |
| `src/utilities/llm_manager/conversation_manager.py` | NEW — generic ConversationManager (caller provides summarization prompt) | D.2 |
| `prompts/intelligence/summarize_turns.md` | NEW — summarization prompt for search conversations | D.2 |
| `src/shared/config/config.py` | Add SUMMARIZE_BEYOND_N_TURNS: int = 4 | D.2 |
| `src/linkedout/intelligence/agents/search_agent.py` | Register web_search, use ConversationManager, remove result set tools + _current_result_set/_excluded_ids/_pivot_detected | B + D.3 |
| `src/linkedout/intelligence/tools/result_set_tool.py` | Remove filter/exclude/rerank/aggregate. Keep tag_profiles, get_tagged_profiles, compute_facets | D.3 |
| `src/linkedout/intelligence/contracts.py` | Remove ContextStrategy, ConversationState, ConversationConfig, ExclusionState | D.3 |
| `src/linkedout/intelligence/controllers/search_controller.py` | Remove pivot detection, auto-archiving, complex session state. Write turn rows, read history via ConversationManager | D.4 |
| `tests/unit/intelligence/test_web_tool.py` | NEW — tests for web search tool | B |
| `tests/unit/intelligence/test_intro_tool.py` | Tests for new tiers | E |

### Frontend Critical Files (Phase G — `linkedout-fe` repo)

| File | Changes | Sub-phase |
|---|---|---|
| `src/hooks/useStreamingSearch.ts` | Remove `exclusionState` from state. Session resume reads turns from new API instead of `result_snapshot`/`conversation_state`. Remove `exclusion_state` parsing from SSE `conversation_state` event. | G.1 |
| `src/hooks/useSession.ts` | Fetch turn history from `search_turn` list endpoint instead of session's `result_snapshot`. Resume loads latest turn's results. | G.1 |
| `src/components/search/SearchPageContent.tsx` | Remove `ExcludedBanner` usage. Session resume: replace `latestSession.result_snapshot` reads with turn-based restore. Remove `parseConversationTurns(conversation_state.messages)` — turns come from API. | G.1 |
| `src/components/search/ExcludedBanner.tsx` | DELETE — no more exclusion state from backend | G.1 |
| `src/types/conversation.ts` | Remove `ExclusionState` type | G.1 |
| `src/types/session.ts` | Remove `result_snapshot`, `conversation_state`, `excluded_ids` from session type. Add `turns` endpoint reference. | G.1 |
| `src/lib/parseConversationTurns.ts` | Rewrite or DELETE — turns come structured from API, no more parsing from raw message blobs | G.1 |
| `src/components/search/SearchPageContent.tsx` | "New Search" button: just calls `reset()` + clears `activeSessionId`. No backend archive call — backend doesn't care. | G.2 |
| `src/__tests__/hooks/useStreamingSearch.test.ts` | Update: remove exclusionState tests, update restoreResults/restoreTurns tests for turn-based flow | G.3 |
| `src/__tests__/components/search/SearchPageContent.regression-001.test.tsx` | Update: remove `result_snapshot` references, update session resume tests | G.3 |
| `src/__tests__/hooks/useStreamingSearch.split-panel-bugs.test.ts` | Review: restoreResults tests may need updates | G.3 |

## Phase G: Frontend Changes (linkedout-fe repo)

**Prerequisite:** Backend Phases A–D complete and stable.

### G.1: Session resume via turn history

The biggest frontend change. Currently, session resume reads `result_snapshot` and `conversation_state.messages` from the `SearchSession` entity. After Phase D, those columns are gone. Instead:

1. **New API contract:** `GET /search-sessions/{id}/turns` returns `search_turn` rows ordered by `turn_number`. Each turn has `results` (JSONB) and `user_query`.
2. **`useSession.ts`:** Fetch turns via the new endpoint. `restoreResults(latestTurn.results)`. `restoreTurns(turns)` — turns are already structured, no parsing needed.
3. **`SearchPageContent.tsx`:** Replace all `latestSession.result_snapshot` reads with turn-based restore. Remove `parseConversationTurns(conversation_state.messages)`.
4. **Remove `ExcludedBanner`:** No exclusion state from backend. Delete component, remove from `SearchPageContent`.
5. **Type cleanup:** Remove `ExclusionState`, update `SessionType` to drop `result_snapshot`, `conversation_state`, `excluded_ids`.

### G.2: Frontend owns session lifecycle

1. **"New Search" button:** Calls `reset()` on the hook + clears `activeSessionId`. Does NOT call backend to archive. The old session just stays — backend doesn't enforce "one active session."
2. **Follow-up:** Sends `session_id` in the request. Backend reads turn history.
3. **First search:** No `session_id` sent. Backend creates a new session.
4. **Remove T10 (pivot detection):** No `start_new_search` from backend, no session swap handling in the SSE stream. If backend sends a new `session` event, just update `sessionId` — but this shouldn't happen in the new flow.

### G.3: Test updates

Update all tests that reference:
- `exclusionState` / `ExclusionState`
- `result_snapshot` / `conversation_state.messages`
- Pivot detection / session swaps
- `parseConversationTurns`

### SSE Protocol Changes (Backend → Frontend)

| SSE Event | Before | After |
|---|---|---|
| `conversation_state` | `{result_summary_chips, suggested_actions, exclusion_state, result_metadata, facets}` | `{result_summary_chips, suggested_actions, result_metadata, facets}` — `exclusion_state` removed |
| `session` | Emitted on new session AND pivot (session swap) | Emitted only on new session creation. No pivots. |
| All others | Unchanged | Unchanged |

### Transitions Affected (from search_conversation_flow spec)

| Transition | Change |
|---|---|
| T7 (Undo/Remove Filter) | No more `filter_results`/`start_new_search` tools. LLM re-queries with adjusted SQL. Frontend flow unchanged — still a follow-up. |
| T8 (Session Resume) | Reads from `search_turn` API instead of `result_snapshot`/`conversation_state` on session |
| T10 (Pivot Detection) | **REMOVED.** No pivots. User clicks "New Search" explicitly. |
| T11 (New Search) | Simplified: just `reset()` + clear session ID. No backend archive call. |

## Review Decisions Log

Decisions made during plan review (2026-04-02):

1. **Web search guardrails:** 3 calls max per turn, 10s timeout per call. Counter in `_execute_tool()`, timeout in `web_tool.py`.
2. **Pivot detection:** Removed entirely. Frontend owns session lifecycle — sends `session_id` for continuation, omits it for new search. Backend has zero session decision logic.
3. **Conversation history location:** New `ConversationManager` class in `src/utilities/llm_manager/conversation_manager.py`. Generic infrastructure — caller provides summarization prompt. `LLMClient` stays untouched.
4. **Change 5 staging:** Single phase (D) with 4 sub-phases (D.1–D.4). No backward compatibility, existing search history discarded.
5. **Frontend:** Separate phase (G), separate repo (linkedout-fe). Backend changes are additive — frontend updates follow after backend stabilizes.
