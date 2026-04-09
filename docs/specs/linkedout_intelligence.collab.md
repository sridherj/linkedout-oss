---
feature: linkedout-intelligence
module: backend/src/linkedout/intelligence
linked_files:
  - backend/src/linkedout/intelligence/
  - backend/src/linkedout/intelligence/agents/search_agent.py
  - backend/src/linkedout/intelligence/scoring/affinity_scorer.py
  - backend/src/linkedout/intelligence/tools/
  - backend/src/linkedout/intelligence/explainer/
  - backend/src/linkedout/intelligence/controllers/search_controller.py
  - backend/src/linkedout/intelligence/controllers/best_hop_controller.py
  - backend/src/linkedout/intelligence/contracts.py
  - backend/src/linkedout/intelligence/schema_context.py
  - backend/src/linkedout/intelligence/prompts/search_system.md
version: 1
last_verified: "2026-04-09"
---

# LinkedOut Intelligence

## Intent

Provide AI-powered search and scoring across a user's LinkedIn network. The intelligence layer has three components: (1) an agentic search engine that uses LLM tool-calling to route natural language queries to SQL or vector search, (2) an affinity scoring engine that computes relationship strength and assigns Dunbar tiers, and (3) supplementary endpoints for finding similar people and warm intro paths. All queries are user-scoped via `app_user_id` and enforced by PostgreSQL RLS.

## Behaviors

### SearchAgent (Agentic NL Search)

- **LLM tool-calling loop**: The SearchAgent (`search_agent.py`) uses the LLM client abstraction (`call_llm_with_tools`) with 14 registered tools across five categories: DB tools (`execute_sql`, `search_profiles`), web tool (`web_search`), helper tools (`resolve_company_aliases`, `classify_company`, `analyze_career_pattern`, `lookup_role_aliases`, `find_intro_paths`, `get_network_stats`), ordering tools (`set_result_order`), profile tools (`get_profile_detail`, `request_enrichment`), and persistent tools (`tag_profiles`, `get_tagged_profiles`). The system prompt uses a capabilities-oriented approach -- describing what the agent can do rather than prescribing when to use which tool. Tool descriptions guide selection; no hardcoded routing rules. The loop runs up to `MAX_ITERATIONS = 20` until the LLM produces a final text answer.

- **Two execution modes**: `run()` returns a `SearchResponse` (full result set), `run_turn()` returns a `ConversationTurnResponse` (with transcript, facets, chips, token estimates). `run_streaming()` yields `SearchEvent` objects via an async generator with progress events. The search controller uses `run_turn()` for the SSE endpoint.

- **SQL tool with safety guardrails**: The `execute_sql` tool (`sql_tool.py`) accepts only SELECT queries, auto-injects `LIMIT 100` if missing, and sets a **10-second** statement timeout (`_STATEMENT_TIMEOUT_MS = 10000`). Tenant isolation is enforced via PostgreSQL RLS -- the session has `app.current_user_id` set via `set_config`, and RLS policies on connection, crawled_profile, and experience tables automatically scope all queries. Uses a savepoint (`session.begin_nested()`) so SQL errors don't invalidate the outer transaction's RLS context.

- **SQL error recovery with column hints**: When a SQL query fails with a column-not-found error, the tool queries `information_schema.columns` for available columns and returns them as hints in the response. The tool also returns available table names for relation-not-found errors. The LLM can self-correct on retry. Available tables: `crawled_profile`, `connection`, `experience`, `education`, `company`, `company_alias`, `profile_skill`, `funding_round`, `startup_tracking`.

- **Web search tool**: The `web_search` tool (`web_tool.py`) delegates to OpenAI Responses API (`gpt-4.1-mini` with `web_search_preview` built-in tool). Used for context not in the database -- company info, investors, funding details, industry context, recent news, executive teams. Guardrails: 10-second timeout, max 3 calls per turn (`MAX_WEB_SEARCHES_PER_TURN = 3`). Rate limiting is tracked via a mutable `_call_count` dict passed from the agent.

- **Funding table access**: The `funding_round` and `startup_tracking` tables are included in the schema context and accessible via the SQL tool. These tables are NOT user-scoped (no RLS policies) -- `funding_round` links to `company` via `company_id` (round_type, amount_usd, lead_investors, all_investors), and `startup_tracking` links to `company` via `company_id` 1:1 (funding_stage, total_raised_usd, vertical).

- **Vector search tool**: The `search_profiles` tool (`vector_tool.py`) generates an embedding from the query text via `EmbeddingProvider`, then runs a pgvector cosine distance query against crawled_profile embeddings joined with connections. Supports dual embedding columns (`embedding_openai` or `embedding_nomic`) based on configured provider. Results include similarity scores and are user-scoped via RLS.

- **Vector search similarity floor**: The vector search tool applies a **0.25 cosine similarity floor**, filtering out profiles with similarity scores below this threshold (`1 - (cp.{col} <=> ...) > 0.25`). This removes unrelated profiles from vector results before they enter the merge-dedup pipeline.

- **set_result_order tool (LLM-declared ordering)**: The `set_result_order` tool allows the LLM to declare the final display order of search results after gathering candidates. It accepts an ordered list of `crawled_profile_id` values. The handler stores this order on `self._declared_order`. When present, `_collect_results()` sorts the final result set to match the declared order. Profiles not in the declared order appear after the ordered ones.

- **Merge dedup in _collect_results()**: When the same profile appears from both vector search and SQL results, `_collect_results()` merges `match_context` dicts rather than keeping only the first occurrence. Null fields in the earlier occurrence are filled from the later one. Dedup key is `crawled_profile_id` or `connection_id`.

- **Candidate count tracking**: Result-producing tools (`search_profiles`, `execute_sql`, `find_intro_paths`) set `self._last_candidate_count` during `_execute_tool()`. The `run_streaming()` method reads this value to emit progress messages via `thinking` events (e.g., "Found 15 candidates, evaluating...").

- **Query type determination**: After the conversation completes, the agent categorizes the query as `SQL`, `VECTOR`, `HYBRID` (both tools used), or `DIRECT` (no tools). Classification is based on actual tool calls in the message history. SQL-adjacent tools (`resolve_company_aliases`, `classify_company`, `analyze_career_pattern`, `lookup_role_aliases`, `get_network_stats`, `find_intro_paths`) count as SQL.

- **Multi-turn conversation support**: The agent supports multi-turn conversations via `ConversationManager` (see [LLM Client spec](llm_client.collab.md)). The `run()` and `run_turn()` methods accept `turn_history` (list of dicts with `user_query`, `transcript`, `summary` keys). The agent calls `conv_manager.build_history()` to reconstruct context from prior turns, then injects the resulting messages into the LLM conversation.

- **Schema context injection**: The `schema_context.py` module dynamically builds a schema context from SQLAlchemy entity metadata for 10 entities: `CrawledProfile`, `Connection`, `Experience`, `Education`, `Company`, `CompanyAlias`, `ProfileSkill`, `RoleAlias`, `FundingRound`, `StartupTracking`. Includes business rules: RLS auto-scoping, required SELECT columns (`crawled_profile_id`, `connection_id`, `full_name`, etc.), data availability notes (79% of experience records have `seniority_level`), and the `is_current IS NULL` pattern for past roles.

- **get_network_stats tool**: Returns `{total_connections, top_companies, top_industries, seniority_distribution, top_locations}`. Each sub-key returns up to 10 entries with counts. Note: `avg_affinity_score` is NOT computed despite appearing in the function docstring -- it is absent from the actual implementation.

### Persistent Tools

- **tag_profiles**: Persists tags to the `SearchTagEntity` via direct SQL. Supports add/remove actions. Deduplication prevents double-tagging (checks for existing tag with same app_user_id, session_id, crawled_profile_id, tag_name before insert). Remove uses `DELETE` with `ANY(:pids)`. Returns `{action, tag_name, profile_ids, count}`.

- **get_tagged_profiles**: Retrieves profiles with a specific tag, optionally scoped to a session. Joins with `crawled_profile` for display data (full_name, current_position, current_company_name). Returns `{tag_name, profiles: [...], count}`. Cross-session tag retrieval works when `session_id` is omitted.

### Facets & Result Metadata

- **compute_facets**: A standalone function (not an LLM tool) in `result_set_tool.py` that computes facet groups from an in-memory result set. Facet dimensions: Dunbar Tier (`dunbar_tier`), Location (`location_city`), Company (`current_company_name`), and Seniority (inferred from `current_position` text via keyword matching -- intern through C-Suite/Founder). Returns `[{group: str, items: [{label: str, count: int}]}]`, each group capped at 10 items. Called by `run_turn()` to populate `ConversationTurnResponse.facets`.

### Profile Detail (Slide-Over Panel)

- **get_profile_detail tool**: Returns comprehensive profile data for all 4 slide-over panel tabs: (1) Overview -- identity fields, about, location, plus `why_this_person_expanded` (full paragraph explanation) and `key_signals` (list of `KeySignal` objects: `{icon, label, value, color_tier}`). (2) Experience -- full timeline with role, company, start/end dates, duration, is_current, company industry/size_tier. (3) Affinity -- score, tier, tier_description, 5 sub-scores (recency, career_overlap, mutual_connections, external_contact, embedding_similarity). (4) Skills -- with query-relevance highlighting (`is_featured=True` if skill name matches search query terms). Also returns education, connection metadata, and suggested questions.

- **request_enrichment tool**: Checks profile enrichment state and returns a confirmation message that the LLM must relay to the user. Never auto-triggers enrichment -- requires explicit user confirmation. Returns status (already_enriched/not_enriched) with appropriate messaging.

- **Profile detail REST endpoint**: `GET /tenants/{tenant_id}/bus/{bu_id}/search/profile/{connection_id}` returns `ProfileDetailResponse` with all panel data. Uses RLS-scoped session. Returns 404 for unknown connections.

### SSE Streaming Search

- **Server-Sent Events streaming endpoint**: `POST /tenants/{tenant_id}/bus/{bu_id}/search` accepts `SearchRequest` (query, session_id, limit) and returns a `StreamingResponse` with SSE events: `thinking` (progress messages), `session` (session_id after create/resume), `result` (individual `SearchResultItem` per result), `explanations` (WhyThisPersonExplainer output in batches of 10), `conversation_state` (result_summary_chips, suggested_actions, result_metadata, facets), `done` (summary with total, query_type, answer, session_id), `error`, and `heartbeat` (every 15 seconds). Results are streamed individually as they come from `run_turn()`.

- **Session integration in SSE flow**: The search endpoint creates or resumes a `SearchSession`. If `session_id` is provided in the request and the session exists, it resumes with existing conversation state (turn history loaded from `search_turn` rows). Otherwise, it creates a new session. After results stream, session state (turn data, transcript, results with merged explanations) is persisted via fire-and-forget. See [Search Sessions spec](search_sessions.collab.md).

- **Heartbeat to prevent idle timeout**: The `stream_with_heartbeat()` wrapper in `_sse_helpers.py` emits heartbeat SSE events every 15 seconds (`HEARTBEAT_INTERVAL = 15`) if no search events are produced. Uses `asyncio.wait()` with timeout instead of `wait_for()` to avoid cancelling the underlying generator.

- **Explain toggle**: The `explain` query parameter (default `True`) controls whether WhyThisPersonExplainer runs after results. When disabled, no `explanations` events are emitted.

### Best Hop (Chrome Extension)

- **Best-hop ranking endpoint**: `POST /tenants/{tenant_id}/bus/{bu_id}/best-hop` accepts `BestHopRequest` (target_name, target_url, mutual_urls, optional session_id) and returns SSE-streamed ranked results. The `BestHopService` ranks mutual connections by relevance to the target using LLM analysis. Returns `BestHopResultItem` objects with rank, why_this_person explanation. Shares session infrastructure with search (creates/resumes `SearchSession`, persists turn data).

### Conversation Turn Contracts

The following Pydantic models in `contracts.py` define the structured response for a conversation turn:

- **ConversationTurnResponse**: Top-level response model. Contains `message`, `result_summary_chips`, `suggested_actions`, `result_metadata`, `facets`, `results`, `query_type`, `turn_transcript`, and token estimates.
- **ResultSummaryChip**: `{text, type}` -- type is one of `count`, `filter`, `sort`, `removal`.
- **SuggestedAction**: `{type, label}` -- type is one of `narrow`, `rank`, `exclude`, `broaden`, `ask`.
- **ResultMetadata**: `{count, sort_description}`.
- **FacetItem / FacetGroup**: `{label, count}` items grouped by dimension `{group, items}`.
- **SearchTurnResult**: Wraps `SearchResponse` with `turn_transcript` and token estimates. Used internally.
- **BestHopRequest / BestHopResultItem**: Chrome extension contracts for mutual connection ranking.

### WhyThisPersonExplainer

- **Per-result 1-2 sentence explanations with match strength and highlighted attributes**: After search results are collected, the `WhyThisPersonExplainer` (`explainer/why_this_person.py`) generates structured JSON explanations. Each explanation includes a 1-2 sentence narrative (40-50 words max) mapping profile attributes to query dimensions, a `match_strength` assessment (strong/partial/weak), plus 2-3 `highlighted_attributes` chips (short labels with `color_tier` 0-2). Output is a JSON array with `connection_id`, `explanation`, `match_strength`, and `highlighted_attributes` fields (with text fallback parsing, defaulting match_strength to "partial" when absent). Profiles are processed in batches of `BATCH_SIZE = 10` per LLM call. Full profile enrichment (career history, education, skills, company metadata, affinity sub-scores) is fetched via `prepare_enrichment()` before generating explanations. If enrichment fetch fails, the explainer returns `{}` with a warning log.

### Search Agent System Prompt Personalization

- **Network preferences injection**: When `app_user.network_preferences` is non-null and non-empty, the text is injected into the search agent system prompt under a "User's Network Preferences" section. Falls back to "No specific preferences set." when null or empty. The `AppUserEntity` is looked up in `__init__` via `session.get()`.

### Similar People

- **Vector similarity endpoint**: `POST /tenants/{tenant_id}/bus/{bu_id}/search/similar/{connection_id}` finds people similar to a given connection by comparing their profile embedding against all other enriched profiles in the user's network. Supports configurable limit (default 10, max 50). Returns 400 for unenriched profiles, 404 for unknown connections. Uses the configured embedding column (`embedding_openai` or `embedding_nomic`).

### Warm Intro Paths (5-Tier System)

- **find_intro_paths tool**: The `find_intro_paths` tool (`intro_tool.py`) accepts a company or person name (not a `connection_id`) and returns ranked introduction paths across 5 tiers, each returning up to 10 results ordered by affinity score:
  - **Tier 1 -- Direct connections** currently at the target company (matched via `current_company_name` ILIKE or `company_id` in `company.canonical_name`).
  - **Tier 2 -- Alumni** who previously worked at the target company (via `experience` table, filtering `is_current IS NULL OR is_current = FALSE`, excluding people currently at the target).
  - **Tier 3 -- Headline mentions** of the target in `crawled_profile.headline`, excluding people currently employed at the target.
  - **Tier 4 -- Shared-company warm paths**: connections who worked at the same prior companies as current target employees (multi-JOIN through `experience.company_id`). Excludes people currently at the target.
  - **Tier 5 -- Investor connections**: connections at firms that invested in the target company, via `funding_round.lead_investors` with `UNNEST`.

  Return shape: `{target, paths: [{tier, path_type, profile_id, intermediary, current_role, company, affinity_score, dunbar_tier, ...}], tier1_count, tier2_count, tier3_count, tier4_count, tier5_count}`. Additional fields vary by tier (e.g., `past_role`/`past_company` for alumni, `shared_company`/`target_person` for tier 4, `headline` for tier 3).

  **Note:** The `IntroPathsResponse` contract in `contracts.py` (`via`, `shared_context`, `strength`) reflects the REST endpoint contract (`GET /search/intros/{connection_id}`) which uses a simpler shared-company approach only. The 5-tier system is the tool's internal implementation used by the LLM agent.

- **REST intro endpoint**: `GET /tenants/{tenant_id}/bus/{bu_id}/search/intros/{connection_id}` uses a simpler approach -- finds connections who worked at the same companies as the target via the `experience.company_id` JOIN. Returns `IntroPathsResponse` with `{via, shared_context, strength}`. Limited to 5 results.

### Affinity Scoring

> Extracted to dedicated spec: [LinkedOut Affinity Scoring](linkedout_affinity_scoring.collab.md) -- covers V3 scoring formula (5 signals, configurable weights), Dunbar tiers, and batch computation.

## Decisions

### Agentic tool-calling over hardcoded routing -- 2026-03-28
**Chose:** LLM decides which tools to call per query
**Over:** Regex/keyword-based routing to SQL vs vector
**Because:** Natural language queries are ambiguous. The LLM can combine SQL and vector tools in a single conversation and self-correct on SQL errors. Hardcoded routing would require maintaining pattern lists.

### SELECT-only SQL with statement timeout -- 2026-03-28
**Chose:** Reject all non-SELECT queries, 10-second timeout
**Over:** Sandboxed read-only replica
**Because:** Simple and effective. The agent's system prompt instructs SELECT-only, the tool enforces it, and the timeout prevents accidental full-table scans. Read replica adds infra complexity.

### RLS enforcement over advisory scoping -- 2026-04-01
**Chose:** PostgreSQL RLS policies with `set_config` session variable
**Over:** Prompt-based app_user_id injection
**Because:** RLS provides defense-in-depth -- even if the LLM generates unexpected SQL, it cannot access other users' data. The SQL tool uses savepoints to preserve RLS context across errors.

### Tool-first architecture with capabilities-oriented prompt -- 2026-04-02
**Chose:** 14 specialized tools with a capabilities-oriented system prompt
**Over:** 2 generic tools (SQL + vector) with a long prescriptive routing prompt
**Because:** Specialized tools act as "think before you write" scaffolding -- the LLM gathers context (canonical company names, role variants, web context, network stats) before writing SQL. Tool descriptions guide selection naturally; prescriptive routing rules added complexity without quality benefit. Web search fills knowledge gaps the database can't cover.

## Not Included

- WhyThisPersonExplainer error propagation -- if enrichment data fetch fails, the explainer returns `{}` with a warning log rather than erroring the response. This silent skip is intentional fire-and-forget behavior.
- Saved searches or search alerts
- Conversation branching (fork from mid-conversation)
- Auto-archiving of stale sessions
- Tag-based search filtering (search within tagged profiles)
- Session sharing between users
- Fuzzy name matching via pg_trgm (not implemented in any tool; may exist at the prompt level)
- SQL resilience rules (zero-result fallback, timeout recovery) -- these are prompt-level guidance, not code-enforced behaviors
