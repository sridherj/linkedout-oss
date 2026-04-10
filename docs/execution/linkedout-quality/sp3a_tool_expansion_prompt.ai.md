# Sub-phase 3a: Tool Expansion & Prompt Engineering

## Prerequisites
- **SP2 complete** (RLS must be in place before unrestricted SQL is safe)

## Outcome
The LLM has 5+ new helper tools, full schema visibility, multi-step prompting examples, and "think before you write" scaffolding. Benchmark scores improve 0.5+ average over SP2 baseline.

## Estimated Effort
4-5 sessions

## Verification Criteria
- [ ] LLM writes arbitrary SQL (JOINs, CTEs, window functions) and gets correct, tenant-scoped results
- [ ] Helper tools are registered and invoked on relevant queries (verify via Langfuse traces)
- [ ] Multi-step SQL decomposition on complex queries (2+ SQL calls when reasoning requires it)
- [ ] Benchmark score improves 0.5+ average vs SP2 baseline
- [ ] System prompt is <100 lines with no hardcoded SQL examples or routing rules
- [ ] Unit tests pass for all new tools (SQLite pattern)

---

## Activities

### 3a.1 Full Schema Exposure
- Verify `build_schema_context()` output includes ALL tables, columns, types, relationships
- **Critical:** expose `role_alias` table (62,717 entries) -- currently invisible to the LLM (gap analysis finding). One-liner: add `RoleAliasEntity` to `schema_context.py:_ENTITIES` list
- Expose `company_alias` table -- verify it has data; if empty, populate from existing subsidiary resolution data
- Include relationship metadata (FK names, JOIN paths) so the LLM can traverse the schema
- **Key file:** `src/linkedout/intelligence/schema_context.py`

### 3a.2 Register P0 Tools

**`resolve_company_aliases`** (VALIDATED by spike -- HIGH IMPACT):
- Wraps `resolve_subsidiary()` and `normalize_company_name()`
- Input: `company_name: str`
- Output: `{canonical_name, aliases: [], subsidiary_of, company_id}`
- The LLM uses this to resolve "TCS" -> "Tata Consultancy Services" before writing SQL
- Register in `SearchAgent.__init__()` alongside existing tools
- **File:** `src/linkedout/intelligence/tools/company_tool.py` (new)
- **Spike reference:** `spike_tool_expansion_results.ai.md` -- confirmed high impact

**`analyze_career_pattern`** (NEW from gap analysis -- HIGH IMPACT):
- Input: list of profile IDs (from prior SQL query)
- Output per profile: `{avg_tenure_years, current_role_duration, seniority_progression: [IC, senior, lead, manager], company_type_transitions: [services, product, startup], career_velocity_score}`
- Addresses #1 gap: Claude Code computes career velocity on 3/5 queries; LinkedOut does 0/5
- Implementation: SQL query over `experience` + `company` tables, compute metrics in Python
- **File:** `src/linkedout/intelligence/tools/career_tool.py` (new)

### 3a.3 Register P1 Tools

**`classify_company`**:
- Input: company name(s)
- Output: `{name, type: services|product|startup|enterprise, industry, size_tier}`
- Uses `company.industry` + `company.size_tier` + LLM knowledge for unknowns
- Addresses gap analysis Q2/Q4 root cause
- **File:** extend `company_tool.py`

**`find_intro_paths`**:
- Input: target company or person name
- Output: ranked intro paths: `[{tier: 1|2|3, path_type: direct|alumni|shared_company, intermediary, affinity_score}]`
- Tier 1: direct connections at target. Tier 2: alumni. Tier 3: shared-company
- Addresses gap analysis Q3 (Claude Code does 3-tier intro reasoning; LinkedOut just lists "who works at X")
- **File:** `src/linkedout/intelligence/tools/intro_tool.py` (new)

**`get_network_stats`** (VALIDATED by spike -- MODERATE IMPACT):
- Input: none (uses current user context)
- Output: `{total_connections, top_industries: [], top_companies: [], avg_tenure, seniority_distribution}`
- Helps LLM calibrate before querying. Cheap to implement
- **File:** `src/linkedout/intelligence/tools/network_tool.py` (new)

### 3a.4 Register P2 Tools (conditional)

**`lookup_role_aliases`**:
- Check `role_alias` table data quality first (62K entries)
- If coverage is good, register as tool. If poor, fix data first then build tool regardless
- **File:** extend `career_tool.py`

### 3a.5 Prompt Rewrite
- Strip hardcoded SQL examples, routing rules, enum values
- Add **"think before you write" meta-instruction** (spike key finding): "Use helper tools to gather information BEFORE writing complex SQL. Resolve company names, check career patterns, understand your network before constructing queries."
- Add multi-step prompting examples:
  - "First find candidates, then analyze their career patterns"
  - "Run two independent queries for different signals, then combine"
  - "Use resolve_company_aliases before writing SQL with company names"
- Keep: schema, tool descriptions, intent guidance
- Target: <100 lines
- **Benchmark after EACH prompt change** to catch regressions (change one thing at a time)
- **Key file:** `src/linkedout/intelligence/prompts/search_system.md`

### 3a.6 Tool Response Format
- All new tools return structured JSON (not prose)
- Keep responses compact -- Phase 2 forward-look: these responses will be part of multi-turn conversation context and must survive summarization
- Example: `analyze_career_pattern` returns `{profiles: [{id, name, career_velocity, seniority_progression}]}` not paragraphs

### 3a.7 Unit Tests for New Tools
- Write repository-level unit tests (SQLite) for each new tool following existing test layer pattern
- Tests verify: SQL correctness, edge cases (empty data, missing companies, unknown aliases), output format matches structured JSON contract
- One test file per tool file: `test_company_tool.py`, `test_career_tool.py`, `test_intro_tool.py`, `test_network_tool.py`

### 3a.8 Validate
- Run full benchmark, capture per-query deltas
- Identify remaining weak queries -- targeted prompt tuning for specific failure patterns
- Check latency impact: helper tools add +5-10s per query (extra LLM round-trip). If unacceptable, investigate parallel tool execution and caching common lookups (company aliases, network stats)

---

## Design Review Notes

| ID | Issue | Resolution |
|----|-------|------------|
| Spec conflict | `linkedout_intelligence.collab.md` > "two bound tools" becomes 7+ | `/update-spec` deferred to SP4 activity 4.3 (batch) |
| Spec conflict | `linkedout_intelligence.collab.md` > "explicit routing rules" stripped | `/update-spec` deferred to SP4 activity 4.3 (batch) |
| A3 | `role_alias` exposure is a one-liner | Add `RoleAliasEntity` to `schema_context.py:_ENTITIES` |
| C2 | `search_profiles` tool lives in `vector_tool.py`, not `sql_tool.py` | Implementer orientation |
| Naming | New tool files | `company_tool.py`, `career_tool.py`, `intro_tool.py`, `network_tool.py` follow existing `sql_tool.py` naming |
| Architecture | Tool registration | All tools in `SearchAgent.__init__()` following existing pattern |
| Latency | +5-10s per query from helper tools | Monitor via Langfuse. Parallel execution + caching for mitigation |
| Error path | Tool failure | Return structured error message the LLM can reason about: `{error: "...", suggestion: "..."}` |

## Key Files to Read First
- `src/linkedout/intelligence/agents/search_agent.py` -- tool registration pattern (`__init__`)
- `src/linkedout/intelligence/tools/sql_tool.py` -- existing tool pattern to follow
- `src/linkedout/intelligence/tools/vector_tool.py` -- existing tool pattern
- `src/linkedout/intelligence/schema_context.py` -- `_ENTITIES` list, `build_schema_context()`
- `src/linkedout/intelligence/prompts/search_system.md` -- current system prompt (to rewrite)
- `.taskos/spike_tool_expansion_results.ai.md` -- tool impact ratings, "think before you write" insight
- `.taskos/exploration/playbook_search_quality.ai.md` -- playbook for tool expansion
- `spike_query_traces/gap_analysis.md` -- root cause analysis per query
