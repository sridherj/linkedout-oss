# LinkedOut Quality: Full Execution Plan (Sub-phases 1-7)

## Overview

Close the quality gap between LinkedOut search and Claude Code (Phase 1), then transform search into a persistent conversational workspace (Phase 2). The approach is measurement-first: build benchmark infrastructure, lock down execution-layer security via PostgreSQL RLS, expand LLM tools and prompts informed by gap analysis, then layer conversational state management on top. Five spikes have resolved all major unknowns -- RLS is GO (Option B), LLM-as-judge uses Claude Code subprocess, sliding-window replay is confirmed for multi-turn, tool expansion validated `resolve_company_aliases` as P0, and the "think before you write" prompt insight is the highest-leverage single change.

## Operating Mode

**HOLD SCOPE** -- Requirements are explicit and comprehensive with clear success criteria ("within 1 point of Claude Code on 1-5 scale", "close laptop, return next day, continue"). No signals for expansion or reduction. The scope is large but well-defined across two phases with 7 workstreams.

**NO BACKWARD COMPATIBILITY** -- This is a greenfield quality overhaul. Existing entities (SearchHistory, etc.) can be ignored, replaced, or dropped. No migration of existing data, no dual-path support, no deprecation periods. Build the right thing from scratch.

---

## Sub-phase 1: Measurement Foundation -- Benchmark Infrastructure & Langfuse Tracing

**Outcome:** A repeatable benchmark scores LinkedOut search quality on 30+ queries against a frozen DB. Baseline scores are captured. Langfuse tracing covers the full search flow with session_id from day one.

**Dependencies:** None

**Estimated effort:** 4-5 sessions

**Verification:**
- `python -m dev_tools.benchmark run` produces a markdown report with per-query scores (1-5), per-persona averages, and aggregate score
- `python -m dev_tools.benchmark run --compare baseline` shows delta from baseline
- Frozen DB snapshot restores in <2 minutes via documented script
- A search in the app produces a Langfuse trace with nested spans: `search_request > search_agent_loop > [tool_call_N > sql_execution | vector_search] > why_this_profile`
- All traces include `session_id` metadata field (even though sessions don't exist yet -- forward-look for Phase 2)

### Key Activities

**1.1 Frozen DB Snapshot**
- `pg_dump` the full DB for SJ's app_user. Store outside git at `~/linkedout-benchmark-db/` with restore script
- Document metadata in `benchmarks/README.md`: profile count, experience count, company count, known data quality issues (e.g., `company_alias` table emptiness needs verification), snapshot date
- Restore script: `benchmarks/restore_snapshot.sh` -- single command, idempotent

**1.2 Query Suite Design (30+ queries)**
- Starting set: 10 calibration queries from `src/dev_tools/benchmark/spike_queries.py` + 5 gap analysis queries from spike traces
- Expand to 30+: ~12 SJ persona, ~10 recruiter, ~10 founder
- Store as YAML in `benchmarks/queries/{persona}_{slug}_{nnn}.yaml`:
  ```yaml
  id: sj_01
  persona: sj
  query: "Who are the strongest warm intro paths to someone at Stripe?"
  dimensions: [network_proximity, company, multi_hop_reasoning]
  difficulty: hard
  expected_behavior: "Should find direct connections at Stripe, then 2nd-degree paths via shared companies/alumni"
  ```
- Quality bar per the high-level plan: queries must require multi-step reasoning, inference from incomplete data, and combining multiple signals. Simple lookups are insufficient.

**1.3 Benchmark Runner (`src/dev_tools/benchmark/`)**
- `runner.py`: Orchestrates execution. For each query: call LinkedOut search API, capture full response (results, SQL, tools invoked, latency, WhyThisProfile explanations). Store as JSON in `benchmarks/results/linkedout/{query_id}.json`
- `scorer.py`: Claude Code subprocess scorer. Design production scorer informed by spike's `run_opus_judge_scorer()` approach (Claude Code subprocess + DB access is validated, Spearman rho = 0.739). Each judge session: `claude -p --model sonnet` with DB access, scores relevance 1-5, provides reasoning. Gold standard scores for 10 queries exist at `benchmarks/spike/spike_scores_gold_standard.json`
- `reporter.py`: Markdown report generation. Per-query scores, per-persona averages, aggregate mean/median, worst-performing queries highlighted, delta from baseline if `--compare` flag used
- CLI command: `python -m dev_tools.benchmark run [--compare baseline] [--queries sj_*] [--report-only]`

**1.4 Claude Code Gold Standard Capture**
- Run all 30+ queries through Claude Code (`claude -p` with DB access), capturing: SQL generated, tools invoked, intermediate reasoning, final results
- Store as `benchmarks/results/claude_code/{query_id}.json`
- 5 queries already captured from gap analysis spike -- expand to full set

**1.5 LinkedOut Baseline Capture**
- Run all 30+ queries through current LinkedOut. This is the pre-improvement baseline
- Store as `benchmarks/results/linkedout_baseline/{query_id}.json`
- 5 baseline traces already exist from spike

**1.6 Extended Gap Analysis**
- Expand the spike's gap analysis (`spike_query_traces/gap_analysis.md`) from 5 queries to all 30+
- Root causes already confirmed: single-shot SQL, no career pattern analysis, no graph reasoning, no company classification
- Output: `benchmarks/gap_analysis.md` with per-category failure patterns and prioritized fix list

**1.7 Langfuse Instrumentation**
- Add `@observe` decorators to the search flow:
  - `search_controller.search()` -- top-level trace with `session_id` metadata
  - `search_agent.run()` -- span for the agent loop
  - Each tool call in the loop -- span per invocation with args/response/latency
  - `sql_tool.execute()` -- span with SQL text, execution time, row count
  - `search_profiles` -- span with query text, similarity scores
  - `why_this_person.explain()` -- span with input context size, output per profile
- Token usage tracked per LLM call (already available via LLMMetrics)
- All traces tagged with `session_id` (use a generated UUID for now; Phase 2 replaces with real session ID)
- Spec update needed: `tracing.collab.md` currently says "no custom trace attributes or tags per agent" -- this changes

**1.8 Spec Update**
- `/update-spec` for `tracing.collab.md`: add search-level trace hierarchy, session_id tagging, custom spans per tool call. Moves from "Not Included" to documented behavior.

### Design Review

- **Spec conflict: `tracing.collab.md` > Not Included > "Custom trace attributes or tags per agent"** -- directly contradicted by session_id tagging and per-tool spans. Add `/update-spec` to activities (done, see 1.8).
- **Naming: benchmark CLI** -- `python -m dev_tools.benchmark` follows existing `python -m dev_tools.cli` pattern.
- **Architecture: scorer as subprocess** -- spawning `claude -p` per query is slow but validated by spike (Spearman rho = 0.739). No faster alternative exists that matches quality. Parallelism (4-5 concurrent scorers) can reduce wall clock time.
- **Error path: what if Langfuse is unreachable during benchmark?** -- Benchmark runner should NOT depend on Langfuse. Tracing is observe-only; benchmark captures its own structured output independently.

---

## Sub-phase 2: Execution-Layer Security -- PostgreSQL RLS Implementation

**Outcome:** All search SQL queries are tenant-scoped at the database level via RLS. The LLM no longer adds WHERE clauses for scoping. The system prompt is stripped of scoping instructions.

**Dependencies:** Sub-phase 1 (benchmark measures impact)

**Estimated effort:** 2-3 sessions (spike completed, implementation is mechanical)

**Verification:**
- Run full benchmark, compare scores -- should be equal or better (no regression)
- Execute raw SQL without `app_user_id` WHERE clause via `psql` with the search role -- returns only scoped data
- Execute SQL with unset session variable -- returns 0 rows (fail-closed)
- Integration test: two different `app_user_id` values see different result sets for the same query

### Key Activities

**2.1 Create Non-Superuser DB Role**
- Script: `scripts/create_search_role.sh` -- creates `linkedout_search_role` with SELECT-only on all tables
- SJ must run this once (requires superuser). Front-load this ask at the start of the sub-phase (LEARNINGS: "front-load ALL superuser/DDL requirements in a single upfront ask")
- Role must NOT be table owner (owner bypasses RLS)

**2.2 RLS Policies (Alembic Migration)**
- Single Alembic migration with raw SQL `op.execute()`:
  - `ALTER TABLE connection ENABLE ROW LEVEL SECURITY`
  - Policy on `connection`: `USING (app_user_id = current_setting('app.current_user_id')::uuid)`
  - `ALTER TABLE crawled_profile ENABLE ROW LEVEL SECURITY`
  - Policy on `crawled_profile`: `USING (id IN (SELECT crawled_profile_id FROM connection WHERE app_user_id = current_setting('app.current_user_id')::uuid))`
  - Same subquery policy on `experience`, `education`, `profile_skill` (all JOIN via `crawled_profile_id`)
  - `company` and `company_alias`: NO RLS (reference data shared across users)
  - `FORCE ROW LEVEL SECURITY` on all tables with policies (ensures policies apply even to table owner if we ever switch roles)
- Add composite index: `CREATE INDEX idx_connection_user_profile ON connection(app_user_id, crawled_profile_id)` -- optimizes subquery policies

**2.3 Session Variable Injection**
- Modify the database session layer (or create a dedicated search session factory) to call:
  ```python
  session.execute(text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": str(app_user_id)})
  ```
  at transaction start for search queries
- This must happen BEFORE any LLM-generated SQL executes in the same transaction
- Add a second engine to `DbSessionManager` connected as `linkedout_search_role`. Expose via `get_search_session()` method that creates a session on this engine and calls `set_config()` before returning. Main engine remains for writes; search engine is RLS-enforced reads only

**2.4 Strip Scoping from Prompt**
- Remove all `app_user_id` scoping instructions from `search_system.md`
- Remove the advisory "always include WHERE app_user_id" from `execute_sql` tool description
- Remove few-shot examples that include `app_user_id` in SQL WHERE clauses
- The LLM should now write SQL as if querying a single-user database

**2.5 Validate**
- Run full benchmark. Compare against Sub-phase 1 baseline
- Run targeted queries that previously included `app_user_id` -- verify they still return correct results
- Run same query with two different `app_user_id` session vars -- verify different results

**2.6 Spec Update**
- `/update-spec` for `linkedout_intelligence.collab.md`: the current edge note says "The SQL tool warns but does not block queries missing :app_user_id binding" and the decision record says "Rejected: row-level security" -- both change. RLS is now the enforcement mechanism. The advisory model is replaced by database-level enforcement.

### Design Review

- **Spec conflict: `linkedout_intelligence.collab.md` > Decisions > "SELECT-only SQL with statement timeout" > "Over: row-level security"** -- This decision is reversed. RLS is now chosen. Add `/update-spec` (done, see 2.6).
- **Spec conflict: `linkedout_intelligence.collab.md` > edge note** -- "The SQL tool warns but does not block queries missing :app_user_id" is replaced by RLS enforcement. No more advisory model.
- **Security: fail-closed verification is critical** -- If `set_config` is not called, the session variable defaults to empty string, which `::uuid` cast will fail on. Verify this returns 0 rows, not an error visible to the user. The agent should catch the error and retry with proper setup.
- **Architecture: separate DB connection for search** -- Using a different DB role means a separate connection pool (or at minimum, a role switch per-transaction). This is the right approach but adds connection management complexity. The `get_search_db_session()` factory pattern isolates this.

---

## Sub-phase 3a: Tool Expansion & Prompt Engineering (parallel with 3b)

**Outcome:** The LLM has 5+ new helper tools, full schema visibility, multi-step prompting examples, and "think before you write" scaffolding. Benchmark scores improve 0.5+ average over Sub-phase 2 baseline.

**Dependencies:** Sub-phase 2 (RLS must be in place before unrestricted SQL is safe)

**Estimated effort:** 4-5 sessions

**Verification:**
- LLM writes arbitrary SQL (JOINs, CTEs, window functions) and gets correct, tenant-scoped results
- Helper tools are registered and invoked on relevant queries (verify via Langfuse traces)
- Multi-step SQL decomposition happens on complex queries (2+ SQL calls when reasoning requires it)
- Benchmark score improves 0.5+ average vs Sub-phase 2 baseline
- System prompt is <100 lines with no hardcoded SQL examples or routing rules

### Key Activities

**3a.1 Full Schema Exposure**
- Verify `build_schema_context()` output includes ALL tables, columns, types, relationships
- Critical: expose `role_alias` table (62,717 entries) -- currently invisible to the LLM (gap analysis finding)
- Expose `company_alias` table -- verify it has data; if empty, populate from existing subsidiary resolution data before Sub-phase 3a work
- Include relationship metadata (FK names, JOIN paths) so the LLM knows how to traverse the schema

**3a.2 Register P0 Tools**

`resolve_company_aliases` (VALIDATED by spike -- HIGH IMPACT):
- Wraps `resolve_subsidiary()` and `normalize_company_name()`
- Input: company_name string
- Output: `{canonical_name, aliases: [], subsidiary_of, company_id}`
- The LLM uses this to resolve "TCS" -> "Tata Consultancy Services" before writing SQL
- Implementation: register in `SearchAgent.__init__()` alongside existing tools
- File: `src/linkedout/intelligence/tools/company_tool.py` (new)

`analyze_career_pattern` (NEW from gap analysis -- HIGH IMPACT):
- Input: list of profile IDs (from prior SQL query)
- Output per profile: `{avg_tenure_years, current_role_duration, seniority_progression: [IC, senior, lead, manager], company_type_transitions: [services, product, startup], career_velocity_score}`
- Addresses #1 gap: Claude Code computes career velocity on 3/5 queries; LinkedOut does 0/5
- Implementation: SQL query over `experience` + `company` tables, compute metrics in Python
- File: `src/linkedout/intelligence/tools/career_tool.py` (new)

**3a.3 Register P1 Tools**

`classify_company`:
- Input: company name(s)
- Output: `{name, type: services|product|startup|enterprise, industry, size_tier}`
- Uses `company.industry` + `company.size_tier` + LLM knowledge for unknowns
- Addresses gap analysis Q2/Q4 root cause
- File: extend `company_tool.py`

`find_intro_paths`:
- Input: target company or person name
- Output: ranked intro paths: `[{tier: 1|2|3, path_type: direct|alumni|shared_company, intermediary, affinity_score}]`
- Tier 1: direct connections at target. Tier 2: alumni connections. Tier 3: shared-company connections
- Addresses gap analysis Q3 (Claude Code does 3-tier intro reasoning; LinkedOut just lists "who works at X")
- File: `src/linkedout/intelligence/tools/intro_tool.py` (new)

`get_network_stats` (VALIDATED by spike -- MODERATE IMPACT):
- Input: none (uses current user context)
- Output: `{total_connections, top_industries: [], top_companies: [], avg_tenure, seniority_distribution}`
- Helps LLM calibrate before querying. Cheap to implement
- File: `src/linkedout/intelligence/tools/network_tool.py` (new)

**3a.4 Register P2 Tools (conditional)**

`lookup_role_aliases`:
- Check role_alias table data quality first (62K entries)
- If coverage is good, register as tool. If poor, fix data first (LEARNINGS: "build the tool regardless, fix data if needed")
- File: extend `career_tool.py`

**3a.5 Prompt Rewrite**
- Strip hardcoded SQL examples, routing rules, enum values
- Add "think before you write" meta-instruction (spike key finding): "Use helper tools to gather information BEFORE writing complex SQL. Resolve company names, check career patterns, understand your network before constructing queries."
- Add multi-step prompting examples:
  - "First find candidates, then analyze their career patterns"
  - "Run two independent queries for different signals, then combine"
  - "Use resolve_company_aliases before writing SQL with company names"
- Keep: schema, tool descriptions, intent guidance
- Target: <100 lines
- Benchmark after EACH prompt change to catch regressions (LEARNINGS: "change one thing at a time")

**3a.6 Tool Response Format**
- All new tools return structured JSON (not prose)
- Keep responses compact -- these will be part of multi-turn conversation context in Phase 2 and must survive summarization
- Example: `analyze_career_pattern` returns `{profiles: [{id, name, career_velocity, seniority_progression}]}` not a paragraph of text

**3a.7 Unit Tests for New Tools**
- Write repository-level unit tests (SQLite) for each new tool following existing test layer pattern
- Tests verify: SQL correctness, edge cases (empty data, missing companies, unknown aliases), output format matches structured JSON contract
- One test file per tool file: `test_company_tool.py`, `test_career_tool.py`, `test_intro_tool.py`, `test_network_tool.py`

**3a.8 Validate**
- Run full benchmark, capture per-query deltas
- Identify remaining weak queries -- targeted prompt tuning for specific failure patterns
- Check latency impact: helper tools add +5-10s per query (extra LLM round-trip). If latency is unacceptable, investigate parallel tool execution

### Design Review

- **Spec conflict: `linkedout_intelligence.collab.md` > SearchAgent > "two bound tools (execute_sql and search_profiles)"** -- this changes to 7+ tools. `/update-spec` needed after this sub-phase.
- **Spec conflict: `linkedout_intelligence.collab.md` > SearchAgent > "explicit routing rules: name lookups route to execute_sql..."** -- routing rules are being stripped from the prompt. The LLM decides freely. `/update-spec` needed.
- **Naming: new tool files** -- `company_tool.py`, `career_tool.py`, `intro_tool.py`, `network_tool.py` follow existing `sql_tool.py` naming convention.
- **Architecture: tool registration** -- all tools registered in `SearchAgent.__init__()` following existing pattern for `execute_sql` and `search_profiles`.
- **Error path: what if a helper tool fails?** -- Tool should return a structured error message the LLM can reason about (e.g., `{error: "Company 'XYZ' not found in database", suggestion: "Try a different spelling"}`). The agent loop already handles tool errors and retries.
- **Latency risk: +5-10s per query** -- Monitor via Langfuse. Mitigation: cache common lookups (company aliases rarely change), consider parallel tool execution if the LLM requests multiple tools in the same iteration.

---

## Sub-phase 3b: "Why This Profile" Improvement (parallel with 3a)

**Outcome:** Profile explanations are 2-3 sentences with explicit match dimensions. Full profile context (all experiences, education, company metadata, affinity). Output includes `highlighted_attributes` for result card content slots.

**Dependencies:** Sub-phase 2 (better results feed better explainer inputs; Langfuse enables debugging)

**Estimated effort:** 2-3 sessions

**Verification:**
- 10 representative benchmark queries: each result explanation references specific match dimensions relevant to the query
- No truncation: profiles with 15+ roles show relevant experience from the full history
- Explanations reference education, company metadata, and network proximity when relevant
- Output includes `highlighted_attributes: [attr1, attr2, attr3]` per profile
- Latency: <3s for a batch of 20 profiles

### Key Activities

**3b.1 Study Claude Code's Reasoning Patterns**
- From gap analysis artifacts: capture how Claude Code cites career trajectory patterns, company stage alignment, skill depth, network proximity, tenure velocity, seniority progression
- LinkedOut currently cites none of these (gap analysis Q1-Q5 all show raw filter results without inference)
- Document the reasoning patterns as a template for the new explainer prompt

**3b.2 Expand Profile Context**
- Current: 5 most recent roles + 10 skills (truncated)
- New: fetch full profile data per profile:
  - All experience records (not truncated)
  - Education records
  - Company metadata per experience: `company.size_tier`, `company.industry`
  - Affinity score + sub-scores: `affinity_recency`, `affinity_career_overlap`, `affinity_mutual_connections` (exist in DB, currently unused)
  - Dunbar tier
  - Connection metadata (date connected, source)
- Implementation: modify `why_this_person.py` data fetching. Single query with JOINs across `connection > crawled_profile > experience > company + education + profile_skill`

**3b.2.5 Rewrite Explainer Infrastructure**
- Current `_fetch_enrichment_data()` only fetches experiences + skills (2 queries). Expand to include education, company metadata (size_tier, industry), affinity sub-scores, Dunbar tier, connection metadata
- Current `_PROMPT_TEMPLATE` expects "ID: explanation" text format. Rewrite for structured JSON output with `explanation` + `highlighted_attributes`
- Current `_parse_explanations()` parses plain text. Replace with JSON parser that produces `dict[str, dict]` (connection_id -> {explanation, highlighted_attributes}) instead of `dict[str, str]`
- Update `WhyThisPersonExplainer.explain()` return type accordingly

**3b.3 Rewrite Explainer Prompt**
- 2-3 sentences per profile with explicit match dimensions
- Query-aware: the prompt deeply reasons about mapping between query intent and profile attributes
- Example output: "Relevant because: 8 years in backend engineering with Kubernetes expertise at both Flipkart (startup) and Microsoft (big tech). Currently 18 months at current role -- below their average tenure of 2.4 years, suggesting potential openness to new opportunities."
- Include structured output format:
  ```json
  {
    "connection_id": "conn_abc123",
    "explanation": "...",
    "highlighted_attributes": ["kubernetes_expertise", "startup_to_bigtech_trajectory", "below_avg_tenure"]
  }
  ```

**3b.4 Output Format for Result Cards**
- Each profile in the WhyThisProfile response must include the fields needed by the result card design (see "Design 1: Result Cards" in UI Design Requirements):
  - `explanation` (2-3 sentences)
  - `highlighted_attributes: [{text, color_tier}]` (max 3 chips, color_tier: 0=lavender, 1=rose, 2=sage)
- The `color_tier` assignment should follow: primary match dimension = 0, secondary = 1, tertiary = 2
- For unenriched profiles: `highlighted_attributes` is empty, `explanation` is lower-confidence with a caveat

**3b.5 Batch Processing for Large Result Sets**
- Split results into batches of 10 profiles (not 20 -- full profile data with all experiences, education, company metadata, and affinity sub-scores can be 2,000+ tokens per profile; 10 x 2K = 20K tokens keeps comfortably within context window)
- Process batches in parallel where possible
- Monitor token usage via Langfuse

**3b.5 Instrument with Langfuse**
- Span per batch: input token count, output token count, latency
- Per-profile logging: which attributes were cited, explanation length

**3b.6 Validate**
- Run 10 representative queries through the benchmark
- Manual inspection: do explanations help understand why each person was returned?
- Latency check: <3s per batch of 20 profiles

### Design Review

- **Spec conflict: `linkedout_intelligence.collab.md` > WhyThisPersonExplainer > "Per-result 1-sentence explanations"** -- changes to 2-3 sentences. `/update-spec` needed.
- **Spec conflict: `linkedout_intelligence.collab.md` > WhyThisPersonExplainer > "parsed from 'ID: explanation' format"** -- changes to structured JSON with `highlighted_attributes`. `/update-spec` needed.
- **Architecture: `highlighted_attributes` output** -- this feeds the LLM-driven content slots on result cards (Phase 2). The format must be stable enough for the frontend to consume. Use a fixed set of attribute types (skill_match, company_match, career_trajectory, network_proximity, tenure_signal, seniority_match) rather than freeform strings.
- **Error path: what if the LLM returns malformed JSON?** -- Parse with fallback: if JSON parse fails, extract explanation text only and set `highlighted_attributes` to empty array. Log the parse failure to Langfuse for debugging.

---

## Sub-phase 4: Quality Validation & Phase 1 Completion

**Outcome:** LinkedOut average relevance score is within 1 point of Claude Code across the full 30+ query benchmark. All Phase 1 changes are validated, documented, and spec'd.

**Dependencies:** Sub-phases 3a and 3b

**Estimated effort:** 2-3 sessions

**Verification:**
- Full benchmark: average score within 1 point of Claude Code on 1-5 scale
- Worst-performing queries identified with root causes documented
- All specs updated: `linkedout_intelligence.collab.md`, `tracing.collab.md`
- Gap analysis report finalized: before/after by category
- Frozen post-improvement benchmark snapshot captured as Phase 2 regression baseline

### Key Activities

**4.1 Full Benchmark Run**
- Run complete 30+ query suite with all improvements in place
- Compare against: (a) original LinkedOut baseline, (b) Claude Code gold standard
- Use Claude Code subprocess scorer for automated scoring

**4.2 Targeted Fix Cycle**
- For each query scoring below 3: diagnose root cause from Langfuse traces
  - Missing tool selection? -> Adjust tool descriptions or add prompting examples
  - Wrong SQL? -> Check if schema context is missing relevant tables/columns
  - Correct SQL, wrong interpretation? -> Prompt tuning for the specific pattern
- Change one thing at a time, re-benchmark after each change
- Document fixes in `benchmarks/fix_log.md`

**4.3 Spec Updates**
- Delegate: `/update-spec` for `linkedout_intelligence.collab.md` -- bulk update covering: RLS enforcement (replacing advisory model), 7+ tools (replacing 2), prompt simplification, WhyThisProfile 2-3 sentences with highlighted_attributes, multi-turn support mention
- Delegate: `/update-spec` for `tracing.collab.md` -- search-level trace hierarchy, session_id, per-tool spans
- Review output for accuracy against implemented behavior

**4.4 Phase 1 Handoff Document**
- `benchmarks/phase1_results.md`: what changed, score improvements by category, remaining limitations, Phase 2 regression baseline

**4.5 Capture Post-Improvement Baseline**
- Freeze a new benchmark snapshot (post-improvements) as the regression baseline for Phase 2

### Design Review

- Design review: no flags. This sub-phase is validation and documentation, not new architecture.

---

## Sub-phase 5: Session Persistence -- Search Sessions & History

**Outcome:** Search results and conversation history persist server-side. Users can close the browser, return, and see previous results. Search page loads the most recent active session by default.

**Dependencies:** Sub-phase 4 (Phase 1 complete)

**Estimated effort:** 4-5 sessions

**Verification:**
- Create search, close browser, reopen -- results still there with conversation history
- Session load <500ms for 100 results + 20-turn history
- New search creates new session, archives previous
- Session history navigable (list of past sessions with query summaries)
- SearchSession is the standalone primary entity (SearchHistory ignored, no backward compat)

### Key Activities

**5.1 Data Model -- SearchSession Entity**
- Extends `BaseEntity` + `TenantBuMixin`
- Fields:
  - `app_user_id` (FK to app_user)
  - `initial_query` (text)
  - `conversation_state` (JSONB -- full LLM message history, structured summary)
  - `result_snapshot` (JSONB -- profile IDs + ranking + metadata per turn)
  - `accumulated_filters` (JSONB -- active filters/exclusions)
  - `excluded_ids` (JSONB -- list of excluded profile IDs)
  - `turn_count` (integer)
  - `status` (enum: active, archived)
  - `last_active_at` (datetime)
- Note: multi-turn spike created experimental `ConversationState` with `structured_summary` field in `contracts.py` and `run_turn()` in `search_agent.py`. These validate the approach but are not production code -- design production versions informed by spike findings (see "Spike Artifacts Reference" section below).
- Delegate: `/crud-orchestrator-agent` or follow manual MVCS pattern for SearchSession CRUD stack (entity, repository, service, controller, schemas)

**5.2 Data Model -- SearchTag Entity**
- Fields:
  - `app_user_id` (FK)
  - `session_id` (FK to SearchSession -- provenance, Decision #12)
  - `crawled_profile_id` (FK)
  - `tag_name` (text)
- Tags are global per user with session-aware provenance
- Indexes: `(app_user_id, tag_name)`, `(app_user_id, crawled_profile_id)`, `(session_id)`

**5.3 Alembic Migration**
- Create both tables with indexes
- `app_user_id + last_active_at` index on SearchSession for fast "load most recent active"
- `SearchSession` is a standalone entity -- no FK to `SearchHistory`, no backward compatibility needed. `SearchHistory` can be dropped later

**5.4 SearchSession CRUD Stack**
- Repository: `BaseRepository` (since it's tenant-scoped via TenantBuMixin)
- Service: standard `BaseService` with custom methods: `get_latest_active(app_user_id)`, `archive_session(session_id)`, `save_turn(session_id, turn_data)`
- Controller: session endpoints -- `GET /sessions` (list), `GET /sessions/{id}` (load), `POST /sessions` (create on new search), `PATCH /sessions/{id}` (save turn state)
- Follow existing MVCS patterns from `linkedout_crud.collab.md`

**5.5 Modify Search Flow**
- On new search: create SearchSession, persist initial results + conversation state
- On follow-up turn: load session, inject conversation history as context, execute turn, save updated state
- On page load: `GET /sessions/latest` returns the most recent active session with its results and history (no re-execution)
- On explicit "New Search": archive current session, create new one

**5.6 Conversation History Replay**
- When resuming a session: replay conversation history as LLM context using sliding-window strategy (spike validated this as the best approach)
- Design production `ConversationConfig` with `context_strategy: ContextStrategy` enum (`FULL_HISTORY`, `SLIDING_WINDOW`, `SUMMARY_ONLY`). Default: `SLIDING_WINDOW` with `summary_window_size=2` (spike-validated default). Note: the spike's `ReplayMode` enum and `_inject_conversation_history()` / `run_turn()` methods are experiments -- design production versions informed by spike findings, not constrained by spike code structure
- Do NOT re-execute the original query -- load results from the session snapshot

**5.7 Extend Langfuse Tracing**
- Group traces by `session_id` (now a real session ID from the database)
- Each turn within a session is a separate trace, linked by session_id
- Session-level view in Langfuse: all traces for a session, ordered by turn number

**5.8 Frontend (see "Design 2: Session History + New Search" in UI Design Requirements)**
- Search bar row: search input + session switcher dropdown + "New Search" button
- Session dropdown: scrollable list of sessions with query text, status tag (Active/Archived), timestamp (relative), result count, turn count, resume button on archived sessions
- Active session label below dropdown: dot indicator + "Active session · Turn N"
- Search page loads existing session results by default (not empty search box)
- API: `GET /sessions` (lightweight list for dropdown), `GET /sessions/{id}` (full state), `GET /sessions/latest`, `POST /sessions` (creates new, archives current)

**5.9 Create Spec: `search_sessions.collab.md`**
- `/taskos-update-spec` to create a new spec covering:
  - SearchSession entity: fields, JSONB structure for conversation_state and result_snapshot, lifecycle (active/archived), session resume with sliding-window context replay
  - SearchTag entity: fields, global-per-user with session_id provenance, cross-session retrieval
  - Session CRUD contracts: create, resume (load latest active), archive, list, save turn state
  - Context engineering contract: what the LLM sees per turn (system prompt + structured summary + recent turns + result set + session state + tools)
  - Session API endpoints: `GET /sessions`, `GET /sessions/{id}`, `GET /sessions/latest`, `POST /sessions`, `PATCH /sessions/{id}`
  - Performance target: session load <500ms for 100 results + 20-turn history
  - Decisions: standalone entity (no FK to SearchHistory), TenantBuMixin for both entities, JSONB for conversation state (with migration path to normalized table if needed)
- Register in `docs/specs/_registry.md`

### Design Review

- **Spec reference: `linkedout_crud.collab.md` > Entity Layer > "Scoped entities inherit TenantBuMixin"** -- SearchSession follows this pattern correctly.
- **Spec reference: `linkedout_crud.collab.md` > Repository Layer** -- SearchSession can use `BaseRepository` since it has tenant/BU scoping. SearchTag uses TenantBuMixin (resolved: Tenant→BU→AppUser is always 1:1:1).
- **Naming: `SearchSession` vs `SearchConversation`** -- "Session" aligns with requirements language and the `session_id` already used in tracing. Keep "SearchSession".
- **No backward compat: `SearchHistory` ignored** -- `SearchSession` is standalone. No FK, no data migration. `SearchHistory` can be dropped in a later cleanup migration.
- **Architecture: JSONB for conversation_state** -- Could grow large for 50+ turn conversations. Mitigations: (a) structured summary compresses older turns, (b) PostgreSQL JSONB compression, (c) consider moving to a separate `conversation_turns` table if storage becomes an issue. Start with JSONB; refactor if needed.
- **Security: session data is tenant-scoped** -- TenantBuMixin ensures cross-tenant isolation. `app_user_id` FK ensures cross-user isolation within a tenant. Verify that session load endpoints check both tenant_id AND app_user_id.
- **Error path: what if session load fails?** -- Fallback to empty search box (new session). Never show another user's session. Log the error to Langfuse.

---

## Sub-phase 6a: Context Engineering & Conversational Tools (parallel with 6b)

**Outcome:** The LLM handles all 11 interaction patterns naturally through context engineering and tool design. No pattern router or classifier in application code.

**Dependencies:** Sub-phase 5 (session persistence for multi-turn state)

**Estimated effort:** 5-6 sessions

**Verification:**
- Validation test cases for all 11 interaction patterns pass
- Multi-pattern messages work ("Remove FAANG people and rank the rest by affinity")
- LLM asks clarifying questions for ambiguous intent
- Sliding window + summary works for 20+ turn conversations
- In-memory filtering (Refine, Exclude) <100ms

### Key Activities

**6a.1 Sliding-Window Context Strategy**
- Construct LLM context per turn: `[system prompt] + [structured summary of older turns] + [recent N turns verbatim] + [current result set summary] + [session state] + [available tools]`
- Use `summary_window_size=2` as default (spike-validated)
- Implement production context injection informed by spike's approach (structured summary + recent turns verbatim). The spike's `_inject_conversation_history()` and `run_turn()` are experiments -- design production versions fresh
- The structured summary must explicitly preserve: original query intent, current result set membership, active exclusions, applied tags, current sort order

**6a.2 In-Memory Result Set Tools (CRITICAL)**
- Multi-turn spike confirmed: the LLM re-runs SQL each turn, causing accumulated filters to get lossy. In-memory tools are the fix.

`filter_results`:
- Input: `{attribute: str, operator: eq|contains|gt|lt|in, value: any}`
- Operates on the current result set (stored in session). No DB query
- Returns filtered set with count
- File: `src/linkedout/intelligence/tools/result_set_tool.py` (new)

`exclude_from_results`:
- Input: `{profile_ids: [str]}` or `{criteria: {attribute: str, operator, value}}`
- Removes from current result set, adds to `excluded_ids` in session state
- Returns updated set + exclusion record (for undo)

`tag_profiles`:
- Input: `{profile_ids: [str], tag_name: str, action: add|remove}`
- Persists to SearchTag entity
- Returns confirmation

`get_tagged_profiles`:
- Input: `{tag_name: str, session_id: optional}`
- Returns profiles with that tag (global or session-scoped)

`rerank_results`:
- Input: `{dimension: affinity|tenure|seniority|recency|custom, order: asc|desc}`
- Re-sorts current result set
- For qualitative dimensions (e.g., "rank by how strong my connection is"), delegates to LLM reasoning

`aggregate_results`:
- Input: `{dimension: str, operation: count|avg|group_by|distribution}`
- Computes over current result set
- Returns structured aggregation result

`get_profile_detail`:
- Input: `{profile_id: str}`
- Returns full profile: experience timeline, education, skills, company details, affinity breakdown (including sub-scores), connection metadata, tags
- This is also used by Sub-phase 6b

**6a.3 Facet Counts on Result Set (from Design 1 & 3)**
- Every search response and every result set operation (filter, exclude, rerank) must include updated facet summaries: `facets: [{group, items: [{label, count, checked}]}]`
- Facet groups are computed from the current result set: Dunbar Tier, Location, Seniority, Company Stage (and others as relevant)
- Facets are computed in-memory from the stored result snapshot — no DB roundtrip
- Facet counts change after exclusions (e.g., removing FAANG drops counts accordingly)
- Implementation: add a `compute_facets(result_set)` utility that groups profiles by known dimensions

**6a.4 Interaction Hint Suggestions (from Design 3)**
- After each LLM turn, the response must include `suggested_actions: [{type, label}]` (3-5 contextual follow-up suggestions)
- Types: `narrow`, `rank`, `exclude`, `broaden`, `ask` — matching the 11 interaction patterns
- These are LLM-generated: add to system prompt: "After each response, suggest 3-5 natural follow-up actions the user might take, formatted as `suggested_actions`"
- Hints are context-aware — they reflect the current result set state, not generic suggestions
- Frontend renders these as clickable pill chips below the follow-up input

**6a.5 LLM Response Format for Conversation Turns (from Design 3)**
- Each turn response must include:
  - `message`: natural language response text
  - `result_summary_chips: [{text, type: "count"|"filter"|"sort"|"removal"}]` — inline summary shown in the conversation thread (e.g., "22 results", "−9 FAANG", "Sorted by affinity")
  - `suggested_actions`: see 6a.4 above
  - `exclusion_state: {excluded_count, excluded_description, undoable}` — for the excluded profiles banner
  - `result_metadata: {count, sort_description}` — for the results header ("13 results · sorted by promo recency")
  - `facets`: see 6a.3 above
- Add this structured output format to the search agent's system prompt so the LLM always produces it

**6a.6 Session State Update Flow**
- After each LLM turn: persist updated result set, exclusions, tags, conversation history
- Store result snapshots per turn (spike recommendation) -- the LLM needs to know the current result set, not just what SQL was run
- Handle undo: maintain a stack of result set states per session for Refine/Exclude undo

**6a.7 Handle Pivot**
- When the LLM starts a fresh search (new intent, no reference to prior results): create new session, archive previous
- The LLM signals this naturally -- detect by checking if the LLM called `execute_sql` or `search_profiles` with a completely new query vs. using result set tools
- Alternative: add a `start_new_search` tool that the LLM can explicitly call to signal a pivot

**6a.8 Validate All 11 Interaction Patterns**
- Add these as live LLM test cases in the benchmark suite (not pytest) -- they are quality validation, not regression tests. Use the Claude Code judge scorer to evaluate whether the LLM selects the right tools and produces correct results for each pattern:
  1. **Refine**: Search -> "Show only Bangalore" -> verify filter applied, original set preserved
  2. **Continue**: Search -> "Do any have voice AI?" -> verify references "them" correctly
  3. **Pivot**: Search -> "Forget that, find Stripe people" -> verify new session created
  4. **Narrow**: Search -> "Only if 2 internships at Series A" -> verify re-executed with constraints
  5. **Broaden**: Search -> "Include any cloud infra, not just K8s" -> verify relaxed constraint
  6. **Explain**: Search -> "Why Rahul?" -> verify detailed explanation with match dimensions
  7. **Compare**: Search -> "Between Priya and Arun for CTO" -> verify structured comparison
  8. **Aggregate**: Search -> "What cities are they in?" -> verify aggregation computed
  9. **Exclude**: Search -> "Remove FAANG" -> verify removal, persistence in session
  10. **Sort/Rank**: Search -> "Rank by connection strength" -> verify re-sorted
  11. **Save/Tag**: Search -> "Tag Priya as shortlist-ml" -> verify tag persisted, retrievable
- Multi-pattern: "Remove FAANG and rank rest by affinity" -> verify both tools invoked in order

**6a.9 Performance**
- In-memory operations (filter, exclude, rerank on stored result set) must complete <100ms
- These bypass the LLM entirely for simple filters
- Complex filters that require LLM reasoning (e.g., "remove anyone who seems overqualified") go through the LLM but use result set tools, not fresh SQL

**6a.10 Frontend (see "Design 3: Conversation History + Follow-up" in UI Design Requirements)**
- Conversation thread above results: user bubbles + system bubbles with inline result summary chips
- System bubbles include removal chips ("−9 FAANG") and undo indicators
- Turn dividers with "Turn N" labels between exchanges
- Follow-up input bar replaces search bar when in active session
- Interaction hint chips below follow-up bar (populated from `suggested_actions`)
- Excluded profiles banner above results with undo button
- Results header shows count + current sort: "13 results · sorted by promo recency"

### Design Review

- **Architecture: NO pattern router** -- The 11 patterns are validation test cases. No `if pattern == "refine"` code. The LLM selects tools based on context. This is a design constraint from the requirements (Decision #10).
- **Spec reference: `linkedout_intelligence.collab.md` > SearchAgent > "5 iterations"** -- multi-turn conversations may need more iterations per turn. Consider increasing MAX_ITERATIONS for follow-up turns, or this may be fine since result set tools are fast.
- **Error path: what if result set tools produce empty results?** -- The LLM should inform the user ("Narrowing to X produced 0 results. The most restrictive filter was Y.") and suggest relaxation. This is natural LLM behavior given the right context.
- **Security: result set tools operate on session-scoped data** -- The in-memory result set is loaded from the session (which is tenant+user scoped). No cross-tenant data access possible.

---

## Sub-phase 6b: Profile Questions & Detail View (parallel with 6a)

**Outcome:** Users click profiles to see a slide-over panel with full details. Users ask questions about profiles using existing data. External enrichment on explicit request only. Result cards show fixed scaffold + LLM-driven highlighted attributes.

**Dependencies:** Sub-phase 5 (session context preservation)

**Estimated effort:** 3-4 sessions

**Verification:**
- Click profile -> slide-over with full details. Click another -> panel updates. Close -> results unchanged
- "How long has X been in AI?" -> answered from stored data without external calls
- "Check if Y has published papers" -> system informs user this needs external lookup, confirms before proceeding
- Result cards show fixed zones (name, headline, role/company, affinity, tags, WhyThisProfile) + LLM-driven 2-3 highlighted attributes

### Key Activities

**6b.1 `get_profile_detail` Tool (see "Design 4: Profile Slide-over Panel" in UI Design Requirements for full field list)**
- (Shared with 6a) Must return all data needed by all four panel tabs:
  - **Overview**: `why_this_person_expanded` (full paragraph, longer than card version), `key_signals: [{icon, label, value, color_tier}]` (3 items with full-sentence explanations)
  - **Experience**: `experiences: [{role, company, start_date, end_date, duration, is_current}]` — FULL list, no truncation
  - **Education**: `education: [{school, degree, start_year, end_year}]`
  - **Skills**: `skills: [{name, is_featured}]` — `is_featured` = relevant to current query (accent-highlighted in UI)
  - **Affinity**: `affinity: {score, tier, tier_description, sub_scores: [{name, value, max_value}]}` — sub-scores: recency, career_overlap, mutual_connections
  - **Connection**: `connected_date`, `connection_source`
  - **Tags**: list of tags applied to this profile
- `suggested_questions: [str]` — 3 profile-specific, query-aware question suggestions for the Ask tab (LLM-generated)
- Implementation: SQL query with JOINs across `connection > crawled_profile > experience > company + education + profile_skill`, formatted as structured JSON

**6b.2 Frontend: Profile Slide-Over Panel (see "Design 4: Profile Slide-over Panel" in UI Design Requirements)**
- Fixed panel on right side (520px default, responsive wider), slides in with animation
- Backdrop overlay, non-selected cards dim to 0.45 opacity
- Panel header: large avatar, name, headline, location, connected date, affinity + tier badges, LinkedIn link, close button
- Tab navigation: **Overview** (default) | **Experience** | **Affinity** | **Ask** (marked "New")
- Overview tab: expanded Why This Person (full paragraph, accent-left-bordered) + Key Signals (3 expanded highlight rows with icon, label, full-sentence value) + Experience timeline (full, no truncation) + Education + Skills (featured skills highlighted)
- Affinity tab: large score display + sub-score breakdown bars (recency, career_overlap, mutual_connections) + Dunbar tier info box
- Ask tab (always visible as panel footer): "Ask about {name}" input + send button + 3 profile-specific suggestion chips ("Has she managed a team?", "Mutual connections?", etc.)
- Click different result -> panel updates without closing. Session context preserved.

**6b.3 Profile Questions (Existing Data)**
- The LLM uses `get_profile_detail` + existing SQL tools to answer questions
- No external calls unless explicitly requested
- Example: "How long has X been in AI?" -> fetch profile detail, compute from experience records
- This is natural LLM behavior -- no special implementation needed beyond the tool

**6b.4 External Enrichment Flow**
- When user explicitly requests: inform user, confirm before proceeding
- Use existing Apify infrastructure for LinkedIn re-crawl
- Implementation: add a `request_enrichment` tool that the LLM can call, which returns a confirmation prompt ("This will fetch external data for X. Proceed? [Yes/No]") and only proceeds on user confirmation

**6b.5 LLM-Driven Result Card Content (see "Design 1: Result Cards" in UI Design Requirements)**
- Fixed scaffold: avatar + name + affinity badge + Dunbar tier badge + headline + location + role summary + Why This Person box + footer (connected date + LinkedIn + View profile)
- LLM-driven zone: 2-3 highlight chips from Sub-phase 3b `highlighted_attributes` output, rendered as colored pills (lavender/rose/sage)
- Unenriched profiles: no chips, show "Enrich" prompt bar instead, why-box at lower opacity
- Start fully LLM-driven, lock down scaffold based on what works (Decision #14)

### Design Review

- **Architecture: slide-over preserves search context** -- This means the frontend must NOT navigate away when opening profile detail. Slide-over/drawer pattern is the right approach for this requirement.
- **Security: external enrichment only on explicit request** -- The `request_enrichment` tool must NOT auto-trigger. The LLM must explicitly ask for user confirmation. This is a product constraint (Decision #8: "External enrichment is always user-triggered").
- **Error path: what if profile data is incomplete?** -- Display what's available, indicate missing sections. Don't show "None" (LEARNINGS: `str(None)` produces "None" literal).

---

## Sub-phase 7: Phase 2 Validation & Polish

**Outcome:** Full conversational search works end-to-end: search -> refine -> compare -> tag -> close laptop -> return -> continue. All 11 patterns pass. Performance targets met.

**Dependencies:** Sub-phases 6a and 6b

**Estimated effort:** 2-3 sessions

**Verification:**
- End-to-end: search, refine, tag, close browser, return next day, see results + tags, continue -- all works
- Session load <500ms, follow-up latency comparable to initial search, in-memory filtering <100ms
- All 11 patterns pass validation
- Langfuse shows session-level tracing with per-turn spans
- All specs updated

### Key Activities

**7.1 End-to-End Integration Testing**
- Full conversational workflow across multiple browser sessions
- Test with realistic multi-day usage patterns
- Test edge cases: 20+ turn conversations, empty results after narrowing, conflicting filters, concurrent sessions

**7.2 Performance Testing**
- Session load time against 500ms target
- Follow-up turn latency vs initial search
- In-memory filtering speed against 100ms target
- Measure: total conversation cost (tokens) for a 10-turn conversation

**7.3 Edge Case Testing**
- Very long conversations (20+ turns) -- does structured summary preserve intent?
- Zero results after narrowing -- does LLM suggest relaxation?
- Tag operations across sessions -- do tags survive session archival?
- Concurrent sessions from same user -- no cross-contamination?

**7.4 Spec Updates**
- `/update-spec` for `linkedout_intelligence.collab.md` -- extend with: session support, conversational tools (filter/exclude/tag/rerank/aggregate/profile_detail), interaction patterns, in-memory result set tools, suggested_actions and facets in response format, LLM response structure for conversation turns
- `/update-spec` for `search_sessions.collab.md` -- extend with any behaviors discovered during implementation: pivot detection, undo stack, edge cases for long conversations
- Review both spec outputs for completeness against implemented behavior

**7.5 UX Polish**
- Conversation history display clarity
- Session navigation smoothness
- Profile detail transitions
- Result card content rendering
- Loading states for follow-up turns

**7.6 Regression Check**
- Run Phase 1 benchmark to ensure quality gains are maintained through Phase 2 changes
- Any regression means Phase 2 changes broke Phase 1 search quality -- investigate and fix

### Design Review

- Design review: no flags. This sub-phase is validation and polish.

---

## Build Order

```
Sub-phase 1 (Benchmark + Langfuse)
    |
    v
Sub-phase 2 (RLS)
    |
    v
    +---------- Sub-phase 3a (Tool Expansion + Prompt) ------+
    |                                                         |
    +---------- Sub-phase 3b (Why This Profile) -------------+
                                                              |
                                                              v
                                                  Sub-phase 4 (Quality Validation)
                                                              |
                                                              v
                                                  Sub-phase 5 (Session Persistence)
                                                              |
                                                              v
    +---------- Sub-phase 6a (Context Eng + Conv Tools) -----+
    |                                                         |
    +---------- Sub-phase 6b (Profile Questions + Detail) ---+
                                                              |
                                                              v
                                                  Sub-phase 7 (Phase 2 Validation)
```

**Critical path:** Sub-phase 1 -> Sub-phase 2 -> Sub-phase 3a -> Sub-phase 4 -> Sub-phase 5 -> Sub-phase 6a -> Sub-phase 7

**Phase 1 boundary:** Sub-phases 1-4 (~4-5 weeks, ~12-16 sessions)
**Phase 2 boundary:** Sub-phases 5-7 (~4-5 weeks, ~12-15 sessions)

---

## Design Review Flags (Consolidated)

| Sub-phase | Flag | Action |
|-----------|------|--------|
| 1 | Spec conflict: `tracing.collab.md` > "No custom trace attributes or tags per agent" | `/update-spec` in Sub-phase 1 activity 1.8 |
| 2 | Spec conflict: `linkedout_intelligence.collab.md` > Decisions > "Over: row-level security" | `/update-spec` in Sub-phase 2 activity 2.6 |
| 2 | Spec conflict: `linkedout_intelligence.collab.md` > edge note about advisory scoping | `/update-spec` in Sub-phase 2 activity 2.6 |
| 2 | Security: fail-closed verification for unset session variable | Integration test in Sub-phase 2 activity 2.5 |
| 3a | Spec conflict: `linkedout_intelligence.collab.md` > "two bound tools" becomes 7+ | `/update-spec` in Sub-phase 4 activity 4.3 (batch) |
| 3a | Spec conflict: `linkedout_intelligence.collab.md` > "explicit routing rules" stripped | `/update-spec` in Sub-phase 4 activity 4.3 (batch) |
| 3a | Latency risk: +5-10s per query from helper tools | Monitor via Langfuse, parallel execution mitigation |
| 3b | Spec conflict: `linkedout_intelligence.collab.md` > "1-sentence explanations" -> 2-3 sentences | `/update-spec` in Sub-phase 4 activity 4.3 (batch) |
| 3b | Spec conflict: `linkedout_intelligence.collab.md` > "ID: explanation" format -> structured JSON | `/update-spec` in Sub-phase 4 activity 4.3 (batch) |
| 5 | Architecture: JSONB conversation_state could grow large for 50+ turn conversations | Start with JSONB, refactor if needed |
| 5 | Entity pattern: SearchTag may not need TenantBuMixin if scoped by app_user_id alone | Verify scoping pattern before creating entity |
| 6a | Architecture: NO pattern router (design constraint from Decision #10) | Enforced by validation tests, not code review |
| 6a | NEW: Facet counts must update after each result set operation | Added activity 6a.3 — compute from in-memory result snapshot |
| 6a | NEW: Interaction hint suggestions must be LLM-generated per turn | Added activity 6a.4 — add to system prompt |
| 6a | NEW: Structured response format for conversation turns | Added activity 6a.5 — message + chips + suggestions + facets |
| 6b | NEW: Profile slide-over has 4 tabs (Overview, Experience, Affinity, Ask) | `get_profile_detail` response must cover all tabs |
| 6b | NEW: Ask tab needs profile-specific question suggestions (LLM-generated) | Added to `get_profile_detail` response |

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tool expansion latency (+5-10s per query) | Medium | Parallel tool execution, caching common lookups (company aliases, network stats). Monitor via Langfuse |
| Prompt simplification causes regression on currently-working queries | Medium | Benchmark before/after every prompt change. Change one thing at a time. Keep rollback capability |
| Context window limits for WhyThisProfile with full profile data on 100 results | Medium | Batch processing (20 profiles per batch). Monitor token usage via Langfuse |
| Sliding window + summary loses critical context in long conversations (20+ turns) | Medium | Spike validated through turn 5. Test with 30-turn conversations in Sub-phase 6a. Structured summary explicitly preserves key state |
| LLM re-runs SQL instead of using result set tools | Medium | Prompt engineering: "Use filter_results and exclude_from_results to modify the current result set rather than re-querying." Validate with interaction pattern tests |
| SearchSession JSONB grows unbounded for long conversations | Low | Structured summary compresses older turns. Monitor average session size. Refactor to normalized turns table if >1MB per session |
| company_alias table is empty | Low | Verify during Sub-phase 1. Populate from subsidiary resolution data if empty |

---

## Resolved Questions

- **SearchTag scoping: TenantBuMixin.** Tenant→BU→AppUser is always 1:1:1, so TenantBuMixin follows the standard MVCS pattern with no practical downside. No pattern deviation needed.

- **SearchSession: new standalone entity, no backward compatibility.** `SearchSession` is the new primary entity for search state. No FK to `SearchHistory`, no migration of existing history data. `SearchHistory` can be dropped or ignored. Clean separation, no coupling overhead.

- **Simple filters: always through the LLM.** No pattern router or bypass path. All follow-up interactions go through the LLM, which selects tools (including `filter_results`) based on context. This honors Decision #10 (no pattern classifier). ~3s latency is acceptable at launch; optimize later via streaming or faster tool dispatch if needed.

---

## UI Design Requirements (Distilled from HTML Designs)

Source designs: `<linkedout-fe>/docs/design/`. These requirements are distilled so implementers don't need to read the raw HTML.

### Design 1: Result Cards with Highlighted Attributes (`result-cards-highlighted-attributes.html`)

**Sub-phases:** 3b (backend output format), 6b (frontend rendering)

**Card scaffold (fixed zones, always present, same position):**
- Avatar (initials, pastel color)
- Name + affinity score badge (numeric, e.g. "87") + Dunbar tier badge ("Inner Circle" / "Active" / "Familiar")
- Headline (role · company)
- Location (mono font)
- Current role summary (mono font, e.g. "Senior PM, Notion · Previously Staff Eng, TCS")
- "Why This Person" box (accent background, 2-3 sentences)
- Card footer: "Connected {date}" + action buttons ("LinkedIn", "View profile")

**LLM-driven zone (between why-box and footer):**
- 2-3 highlight chips per profile, query-aware (same person shows different chips for different queries)
- Chips are pill-shaped with color-coding: lavender (default), rose (secondary), sage (tertiary)
- Each chip has a dot indicator + short text (e.g. "IC → PM in 18 mo", "3 promos in 4 yrs", "Series B → growth")
- Max 3 chips per card

**Unenriched profile state:**
- Card is slightly dimmed (opacity 0.85)
- No highlight chips shown
- Instead shows an "Enrich" prompt bar: "Enrich to see career arc, key signals, and full history" + "Enrich" button
- Why-box is present but lower-confidence (opacity 0.7)

**Backend API requirements:**
- Each profile in search results must include: `affinity_score` (numeric), `dunbar_tier` (string), `why_this_person` (text), `highlighted_attributes` (array of `{text, color_tier}`, max 3), `is_enriched` (boolean), `connected_date` (date)
- Highlight chip `color_tier` maps to: 0=lavender, 1=rose, 2=sage

**Left sidebar — Facet refinement panel:**
- Title: "Refine" (mono uppercase)
- Facet groups with counts: Dunbar Tier, Location, Seniority (and others as relevant to query)
- Facets are clickable (toggleable filter), with `.checked` state
- Counts update dynamically after each conversational turn (exclusions, filters)

**Backend API requirements for facets:**
- Search response must include `facets: [{group: "Dunbar Tier", items: [{label: "Inner Circle", count: 8, checked: false}, ...]}, ...]`
- After each result set operation (filter, exclude, rerank), the response must include updated facet counts reflecting the current result set
- Facet groups are derived from the result set data, not hardcoded

---

### Design 2: Session History + New Search (`session-history-new-search.html`)

**Sub-phase:** 5

**Search bar row (top of page):**
- Search input (focused state has accent border + ring)
- Session switcher button: pill-shaped, shows "N sessions" with dot indicator, toggles dropdown
- "New Search" button: accent-colored with + icon

**Session dropdown (expands below search bar):**
- Header: "Your search sessions" + "View all history →" link
- Scrollable list (max ~340px height) of session items
- Current session: highlighted accent background
- Each session item shows:
  - Icon (search icon, accent for current, grey for past)
  - Query text (truncated if long)
  - Metadata row: status tag ("Active" green / "Archived" grey), timestamp (relative: "Just now", "Yesterday, 4:12 PM", "Mar 30, 10:41 AM"), result count, turn count
  - Action button on past sessions: "Resume" (play icon)
- Active session label below dropdown: dot indicator + "Active session · Turn N"

**Backend API requirements:**
- `GET /sessions` returns list: `[{id, initial_query, status, last_active_at, result_count, turn_count}]` — lightweight for dropdown rendering
- `GET /sessions/{id}` returns full session state for resumption
- `GET /sessions/latest` returns most recent active session
- `POST /sessions` creates new session (archives current active)
- Session status enum: `active`, `archived`
- Timestamps must support relative display (ISO format, frontend computes "Just now" etc.)

---

### Design 3: Conversation History + Follow-up (`conversation-history-followup.html`)

**Sub-phase:** 6a

**Conversation thread (above results, below search bar):**
- Each turn = user message + system response, separated by turn dividers
- User message: avatar (initials) + bubble (subtle background, left-aligned)
- System response: search icon + bubble (accent background, indented 38px)
- System response includes inline result summary chips: "22 results", "8 Inner Circle", "Sorted by affinity"
- For exclusions, chips show: "−9 FAANG" (rose-colored removal chip) + "Undo available" chip
- Turn dividers: thin line + "Turn N" label (mono, small)

**Follow-up input bar (below conversation thread, above results):**
- Full-width text input: "Refine, narrow, exclude, ask a question about these results..."
- Send button (accent, arrow icon)
- This REPLACES the search bar when in an active session (search bar is for new searches, follow-up bar is for continuation)

**Interaction hint chips (below follow-up bar):**
- Row of contextual suggestion pills, each with a type label + action text
- Examples: `[Narrow] Only SF / NYC`, `[Rank] By affinity score`, `[Exclude] No one I've messaged`, `[Broaden] Include mid-level too`, `[Ask] Who's most likely to respond?`
- Chips are clickable (populate the follow-up input)
- **Hints are context-aware** — they change based on the current result set and conversation state

**Excluded profiles banner (above results, below hints):**
- Shown when exclusions are active: "9 people at FAANG excluded from this session" + "Undo" button
- Rose background, dismissible

**Results reflect accumulated state:**
- Result count and sort order shown: "13 results · sorted by promo recency"
- Facet sidebar counts update to reflect post-exclusion state

**Backend API requirements:**
- Each LLM turn response must include: `{message: str, result_summary_chips: [{text, type: "count"|"filter"|"sort"|"removal"}], suggested_actions: [{type: "narrow"|"rank"|"exclude"|"broaden"|"ask", label: str}]}`
- `suggested_actions` are generated by the LLM as part of each turn response (add to system prompt: "After each response, suggest 3-5 natural follow-up actions the user might take")
- Exclusion state must be surfaced: `{excluded_count: int, excluded_description: str, undoable: bool}`
- Result count + current sort order included in response metadata

---

### Design 4: Profile Slide-over Panel (`profile-slideover-panel.html`)

**Sub-phase:** 6b

**Panel container:**
- Fixed to right side, slides in with animation (0.25s ease-out)
- Width: 520px default, 600px on ≥1400px screens, 680px on ≥1800px
- Backdrop: semi-transparent overlay, clicking dismisses
- When panel open: non-selected result cards dim to 0.45 opacity, facet sidebar dims

**Panel header:**
- Larger avatar (52px) + name (1.25rem bold) + headline + location · connected date
- Affinity score badge + Dunbar tier badge (larger than card badges)
- Actions: "LinkedIn" external link button + close button (×)
- Tab navigation: **Overview** | **Experience** | **Affinity** | **Ask** (marked "New")

**Overview tab content:**
1. **Why This Person** — expanded version (accent-left-bordered box), longer than card version (full paragraph with network proximity reasoning)
2. **Key Signals** (labeled "AI") — expanded highlighted attributes as rows (not chips):
   - Each row: icon (emoji) + label (mono uppercase, e.g. "VELOCITY") + value (full sentence explanation)
   - 3 signal rows, each with color-coded icon background (purple, rose, sage)
   - Much richer than the card chips — these are full explanations, not just labels
3. **Experience Timeline** — full chronological list (no truncation), vertical line connecting dots
   - Current role highlighted with "Current" badge
   - Each entry: role title, company, date range + duration
4. **Education** — school icon + school name + degree + dates
5. **Skills** — grid of skill tags, "featured" skills highlighted in accent color

**Affinity tab content (inferred from CSS):**
- Large affinity score number (2.5rem, accent color)
- Affinity sub-score breakdown bars: name + value + progress bar fill
  - Sub-scores: recency, career_overlap, mutual_connections (from DB)
- Dunbar tier info box (lavender background, explains the tier)

**Ask tab (panel footer, always visible):**
- "Ask about {name}" label (mono uppercase)
- Input: "e.g. How long has she been in the AI space?"
- Send button (accent)
- Suggestion chips below input: "Has she managed a team?", "Mutual connections?", "Why did she leave TCS?"
- Suggestions are profile-specific and query-aware

**Backend API requirements:**
- `get_profile_detail` tool response must include all fields for all tabs:
  - Overview: `why_this_person_expanded` (longer than card version), `key_signals: [{icon, label, value, color_tier}]` (3 items)
  - Experience: `experiences: [{role, company, start_date, end_date, duration, is_current}]` — FULL list, no truncation
  - Education: `education: [{school, degree, start_year, end_year}]`
  - Skills: `skills: [{name, is_featured}]` — featured = relevant to current query
  - Affinity: `affinity: {score, tier, tier_description, sub_scores: [{name, value, max_value}]}`
  - Connection: `connected_date`, `connection_source`
- Profile questions endpoint: accepts question text + profile_id, returns answer from existing data
- Profile question suggestions: `suggested_questions: [str]` — 3 profile-specific, query-aware suggestions (LLM-generated)

---

### Cross-Design Patterns

**Consistent across all designs:**
- Berry Fields Soft color palette (CSS variables defined in design system)
- Fraunces serif for body text, Fragment Mono for metadata/labels/counts
- Affinity score as numeric badge (pastel-mint for high, pastel-peach for mid, bg-subtle for low)
- Dunbar tier as text badge (Inner Circle=lavender, Active=sage, Familiar=peach, Acquaintance=subtle)
- Sticky header with nav (Dashboard, Search, Import, History)
- 1200px max-width content area

**Backend response format implications:**
- All search responses need consistent profile data shape across cards, conversation, and slide-over
- The same profile appears in three contexts (card, conversation mention, slide-over) at different detail levels — the API should support this via a `detail_level` parameter or separate endpoints
- Facet counts must be computable from the current result set without a DB roundtrip (in-memory on the stored result snapshot)

---

## Spec Operations Plan

| Spec | Action | When | What Changes |
|------|--------|------|--------------|
| `tracing.collab.md` (v1) | **Update** | Sub-phase 1 (activity 1.8) | Add search-level trace hierarchy, session_id tagging, per-tool spans. Remove "no custom trace attributes" from Not Included |
| `linkedout_intelligence.collab.md` (v5) | **Update** (batch) | Sub-phase 4 (activity 4.3) | RLS replaces advisory scoping, 7+ tools (from 2), routing rules stripped, WhyThisProfile 2-3 sentences with structured JSON + highlighted_attributes, multi-turn support |
| `linkedout_intelligence.collab.md` | **Update** (extend) | Sub-phase 7 (activity 7.4) | Session support, conversational tools (filter/exclude/tag/rerank/aggregate/profile_detail), interaction patterns, in-memory result set tools, suggested_actions in response format |
| `search_sessions.collab.md` | **Create new** | Sub-phase 5 (activity 5.9) | SearchSession entity (JSONB conversation_state, result snapshots, sliding-window replay, session lifecycle), SearchTag entity (global per user, session-aware provenance), session CRUD, session resume/archive, context engineering contracts |
| `search_benchmark.collab.md` | **Skip** | N/A | Dev tooling — documented in `benchmarks/README.md`, not a product spec |

## Spec References

| Spec | Sections Referenced | Conflicts Found |
|------|---------------------|-----------------|
| `linkedout_intelligence.collab.md` (v5) | SearchAgent (tool list, routing rules, MAX_ITERATIONS, multi-turn), WhyThisPersonExplainer (format, parsing), Decisions (RLS rejection), Edge (advisory scoping) | 6 -- all addressed via `/update-spec` in Sub-phases 2, 4 |
| `tracing.collab.md` (v1) | Not Included (custom trace attributes, dashboard) | 1 -- addressed via `/update-spec` in Sub-phase 1 |
| `linkedout_crud.collab.md` (v2) | Entity Layer (TenantBuMixin pattern), Repository Layer (BaseRepository), Service Layer (BaseService) | 0 -- new entities follow existing patterns |
| `linkedout_data_model.collab.md` (v5) | Table relationships for RLS policies | 0 -- RLS policies reference existing schema correctly |
| `search_sessions.collab.md` | **NEW** -- to be created in Sub-phase 5 | N/A |

## Spike Artifacts

Consult during implementation:
- `rls-spike-report.md` -- RLS Option B policy SQL, edge case results
- `spike_query_traces/gap_analysis.md` -- Root cause analysis, per-query comparison
- `spike_llm_judge.ai.md` -- Scorer architecture, correlation data, prototype location
- `spike_tool_expansion_results.ai.md` -- Per-tool impact, "think before you write" insight, latency
- `spike_multiturn_conversation_results.ai.md` -- Replay mode comparison, sliding_window validation, code changes

## Spike Artifacts Reference

Spikes validated approaches and produced reusable data. Production implementations should be **informed by spike findings, not constrained by spike code structure**. Spike code may be cleaned up or removed as production versions are built.

### Reusable Artifacts (keep as-is)

| File | What's Reusable | Sub-phase |
|------|-----------------|-----------|
| `src/dev_tools/benchmark/spike_queries.py` | 10 calibration query definitions (data, not runner code) | 1 |
| `benchmarks/spike/spike_scores_gold_standard.json` | Gold standard scores for 10 queries | 1 |
| `src/linkedout/intelligence/tools/sql_tool.py` | SQL error rollback fix (legitimate production bugfix from multi-turn spike) | 6a |

### Spike Learnings (inform design, don't extend)

| File | What Was Validated | Production Implication | Sub-phase |
|------|-------------------|----------------------|-----------|
| `src/dev_tools/benchmark/spike_scorers.py` | Claude Code subprocess (`claude -p`) as judge scorer. Spearman rho = 0.739 | Design production scorer fresh; the *approach* (subprocess + DB access) is validated, not the code | 1 |
| `src/linkedout/intelligence/contracts.py` | `ConversationState.structured_summary`, multi-turn contracts | Names and structure are open for redesign. `ReplayMode` → `ContextStrategy` (FULL_HISTORY, SLIDING_WINDOW, SUMMARY_ONLY) | 5, 6a |
| `src/linkedout/intelligence/agents/search_agent.py` | `_inject_conversation_history()`, `run_turn()` -- structured summary + recent turns approach works | The *approach* is validated; design production method signatures and implementation fresh | 5, 6a |
| `spikes/s8_tool_expansion_spike.py` | `resolve_company_aliases` is high-impact P0, "think before you write" is highest-leverage prompt change | Tool *concepts* validated; production implementations designed fresh following `sql_tool.py` patterns | 3a |
| `tests/eval/multi_turn_runner.py` | Sliding window with `summary_window_size=2` outperforms other replay modes | Use as design input for `ContextStrategy.SLIDING_WINDOW`; don't extend the test runner | 5, 6a |
