# Search Quality Overhaul Plan

## Investigation Summary (2026-03-29 session)

SJ reported that search result explanations were "horrible and unrelated" — for a query about "engineers who moved from IT → product companies", the system returned a reason like "Built at Google, Amazon, and Adobe" with no mention of career transitions.

**What we did in this session:**
1. Traced the full search pipeline: SearchController → SearchAgent → SQL/Vector tools → ResultItem mapping → WhyThisPersonExplainer → SSE streaming
2. Read every critical file: `search_system.md` (system prompt), `schema_context.py`, `search_agent.py`, `sql_tool.py`, `vector_tool.py`, `why_this_person.py`, `contracts.py`, `search_controller.py`
3. Audited the actual DB data via direct SQL queries — discovered that company enrichment fields (industry, size_tier, employee_count, hq_city) are ALL NULL across 47K companies, making the system prompt's business rules completely broken
4. Verified that career transition queries CAN work via experience table joins + company name matching (452 matches for IT→product)
5. Mapped the data quality across all tables (experience coverage, seniority/function_area fill rates, skill counts, company name fragmentation)
6. Designed a phased fix plan: prompt fix (highest impact) → explainer enrichment → dedup → eval framework

**Key insight:** The system prompt teaches the LLM the "right" SQL patterns, but those patterns filter on NULL columns. The LLM dutifully generates correct-looking SQL that returns 0 results. The fix is to replace column-based predicates with name-based ILIKE patterns that match actual data.

---

## Context

The LinkedOut search system produces poor results and worse explanations. The user queried "find software engineers who moved from IT → Product companies" and got an explanation like "Built at Google, Amazon, and Adobe" — completely unrelated to the query criteria.

### The Problem (Observed Behavior)

1. **Company-type queries return 0 results**: "IT services companies", "product companies", "startups", "AI companies" all fail silently because the system prompt teaches the LLM to filter on `co.industry`, `co.size_tier`, `co.estimated_employee_count` — columns that are ALL NULL.
2. **Explanations hallucinate**: The WhyThisPersonExplainer only sees name/position/company/headline. For a "moved from IT → product" query, it invents generic reasons like "Built at Google, Amazon" instead of citing the actual career transition evidence.
3. **Match evidence is discarded**: When the SQL agent selects extra columns (e.g., previous company, transition date), `_sql_rows_to_result_items()` silently drops them because they don't map to `SearchResultItem` fields.

### DB Data Audit (as of 2026-03-29)

**Overall data health:**
| Metric | Count |
|--------|-------|
| Total connections | 28,004 |
| Enriched profiles (with embeddings) | 22,419 |
| Experience records | 133,763 |
| Education records | 47,248 (across 21,747 profiles) |
| Skills | 758,163 (49,172 unique) |
| Role aliases | 62,717 |
| Avg experiences per enriched profile | 6.1 |

**Company table — critically under-enriched:**
| Column | Populated | Total | Notes |
|--------|-----------|-------|-------|
| canonical_name | 47,453 | 47,453 | Only useful field |
| linkedin_url | 37,548 | 47,453 | Partial |
| industry | **0** | 47,453 | ALL NULL — system prompt relies on this |
| size_tier | **0** | 47,453 | ALL NULL — system prompt relies on this |
| estimated_employee_count | **0** | 47,453 | ALL NULL — system prompt relies on this |
| hq_city / hq_country | **0** | 47,453 | ALL NULL |
| website / domain | **0** | 47,453 | ALL NULL |
| founded_year | **0** | 47,453 | ALL NULL |
| company_alias rows | **0** | — | Table is EMPTY |
| startup_tracking rows | **0** | — | Table is EMPTY |

**Experience data — good quality:**
| Field | Populated | Total | Coverage |
|-------|-----------|-------|----------|
| company_id (FK) | 133,735 | 133,763 | 99.9% |
| seniority_level | 105,287 | 133,763 | 79% |
| function_area | 83,678 | 133,763 | 63% |
| start_date | 130,506 | 133,763 | 98% |
| is_current = true | 24,421 | 133,763 | 18% |

**Profile classification:**
| seniority_level | count | | function_area | count |
|-----------------|-------|-|---------------|-------|
| mid | 7,399 | | engineering | 8,920 |
| senior | 3,427 | | data | 1,349 |
| manager | 2,084 | | consulting | 835 |
| lead | 1,852 | | sales | 571 |
| founder | 893 | | hr | 491 |
| director | 759 | | marketing | 485 |
| c_suite | 660 | | product | 440 |
| vp | 347 | | design | 279 |

**Dunbar tier distribution:**
| Tier | Count | Avg Affinity |
|------|-------|-------------|
| inner_circle | 15 | 48.57 |
| active | 35 | 46.30 |
| familiar | 100 | 45.00 |
| acquaintance | 27,854 | 18.61 |

**Company name fragmentation (examples):**
- "Google" → 110 DB variants (Google, Google Cloud - Minnesota, Google Summer of Code, Google Developer Student Clubs, etc.)
- "TCS" → 26 variants (Tata Consultancy Services, Tata Consultancy Servicess [typo], TCS iON, TCS Research & Innovation, etc.)

**Top companies by experience count:**
| Company | Exp Records | Type |
|---------|-------------|------|
| Tata Consultancy Services | 1,446 | IT Services |
| Infosys | 1,230 | IT Services |
| Crio.Do | 1,170 | EdTech |
| Cognizant Technology Solutions | 963 | IT Services |
| Google Cloud - Minnesota | 701 | Product |
| Google | 692 | Product |
| Accenture AI | 641 | IT Services |
| Amazon | 625 | Product |
| Amazon.com | 609 | Product |
| Wipro | 547 | IT Services |

**Career transition ground truth:**
- 452 people have experience at BOTH an IT services company AND a product company (tested via name-based ILIKE)
- 5,151 profiles have both Python and React skills

### Root Causes

1. **Dead business rules in system prompt** (`search_system.md` lines 69-73) — The business rules map "IT company" → `co.industry ILIKE '%information technology%'`, "product company" → `co.industry ILIKE '%software%'`, etc. Since `co.industry` is NULL for ALL 47K companies, these predicates ALWAYS return 0 rows. The LLM follows the prompt guidance exactly, generating correct-looking SQL that matches nothing.

2. **Dead company alias fallback** (`search_system.md` lines 79-87) — The few-shot examples show alias lookup patterns (`SELECT 1 FROM company_alias ca WHERE ca.company_id = co.id AND ca.alias_name ILIKE ...`). The table has 0 rows, so this is dead code that wastes LLM tokens.

3. **Explainer has no match evidence** (`why_this_person.py`) — The `_format_result()` function passes only: connection_id, full_name, current_position, current_company_name, location, headline, affinity_score, dunbar_tier. No work history, no skills, no education, no SQL match reason. The LLM has to fabricate an explanation.

4. **SQL-to-ResultItem mapping drops context** (`search_agent.py` line 123) — `_sql_rows_to_result_items()` has a hardcoded field mapping. Any extra columns the LLM's SQL returns (e.g., `previous_company`, `old_company_name`, `skill_names`) are silently discarded before reaching the explainer.

5. **No result deduplication** (`search_agent.py` line 242) — `_collect_results()` combines results from multiple tool calls without dedup. Hybrid queries (SQL + vector) can return the same person twice.

---

## Phase 1: Fix System Prompt (Highest Impact)

**File:** `src/linkedout/intelligence/prompts/search_system.md`

> **Review Decision (2026-03-31):** Phase 1a (hardcoded company name lists) is **dropped**. Company enrichment is in progress and will populate `co.industry`, `co.size_tier`, etc. The existing column-based filters will work once enrichment lands. No temporary workarounds.

### ~~1a. Replace dead business rules with name-based predicates~~ — DROPPED

### 1b. Fix few-shot SQL examples

- **Lines 79-87** (company alias fallback): Remove since table is empty. Replace with guidance: "When filtering by company name, use `co.canonical_name ILIKE '%name%'` — note that company names have variants (e.g., 'Tata Consultancy Services', 'Tata Consultancy Servicess', 'TCS')."
- Update few-shot examples to use column-based filters (these will work once enrichment lands)

### 1c. Add data availability warnings

Add a section after the schema noting partial coverage:
```
- ~79% of experience records have seniority_level; ~63% have function_area.
- When filtering by seniority/function, add ILIKE fallback on current_position to catch unclassified profiles.
```

---

## Phase 2: Fix the Explainer (High Impact)

**Files:** `contracts.py`, `search_agent.py`, `why_this_person.py`, `search_controller.py`

### 2a. Add `match_context` to SearchResultItem

**File:** `src/linkedout/intelligence/contracts.py`

```python
match_context: Optional[dict] = None  # Extra SQL columns explaining why this person matched
```

Backwards-compatible (Optional, default None). Frontend ignores unknown fields.

### 2b. Capture extra SQL columns in match_context

**File:** `src/linkedout/intelligence/agents/search_agent.py` — `_sql_rows_to_result_items()`

> **Review Decision:** Use an explicit exclude set (`_KNOWN_FIELDS = {"connection_id", "crawled_profile_id", ...}`). Any SQL columns NOT in this set get collected into `match_context` dict. This prevents internal columns like `app_user_id` from leaking into the payload.

### 2c. Enrich explainer with work history from DB

**File:** `src/linkedout/intelligence/explainer/why_this_person.py`

Change `explain()` to accept optional `session` + `app_user_id`. When provided, fetch enrichment data via **two explicit batch queries** (not one combined query):
1. Experiences: `SELECT ... FROM experience WHERE crawled_profile_id IN (...) ORDER BY start_date DESC`
2. Skills: `SELECT ... FROM profile_skill WHERE crawled_profile_id IN (...)`

Group results in Python by `crawled_profile_id`. Include this context in the LLM prompt alongside the existing surface data.

> **Review Decision:** If either batch query fails (DB timeout, etc.), **skip explanations entirely** for affected profiles rather than falling back to surface-level data. No half-baked guesses.

### 2d. Rewrite explainer prompt

Change from generic "write a 1-sentence explanation" to:
```
For each person, write a 1-sentence explanation of why they match the query "{query}".
ONLY reference facts present in the data below. Do NOT invent or assume facts.
Focus on specific evidence: career transitions, matching companies, relevant skills, seniority changes.
If the query asks about transitions (e.g., "IT to product"), mention the specific companies involved.
```

### 2e. Wire session into explainer call

**File:** `src/linkedout/intelligence/controllers/search_controller.py`

Change `_run_explainer()` to open a DB session and pass it to the explainer.

---

## Phase 3: Add Deduplication + Fix Retry Loop

**File:** `src/linkedout/intelligence/agents/search_agent.py`

### 3a. Dedup in `_collect_results()`

Deduplicate by `crawled_profile_id`, falling back to `connection_id` if profile ID is empty. Keep the first occurrence (higher relevance from the tool that found it first).

> **Review Decision:** Dedup key is `crawled_profile_id` primary, `connection_id` fallback. Unit test required: feed `_collect_results` two ToolMessages with the same profile from SQL + vector tools, assert only first occurrence survives and ordering is preserved.

### 3b. Fix `_execute_tool_with_retry` (existing bug)

> **Review Decision:** The current retry loop (lines 205-224) never actually retries — it returns on the first iteration regardless. Fix the hand-rolled loop to properly send the error+hint back to the LLM for self-correction. This is NOT a tenacity case (LLM-in-the-loop retry, not infrastructure retry).

---

## Phase 4: Schema Context — Data Availability Notes

**File:** `src/linkedout/intelligence/schema_context.py`

Append data availability notes to `_BUSINESS_RULES` string so the LLM sees NULL column warnings even if it ignores the system prompt business rules section.

---

## Phase 5: Eval Framework

> **Review Decision:** Use `integration-test-creator-agent` to scaffold test infrastructure (conftest, fixtures, DB wiring). Hand-write the eval-specific logic (EvalQuery dataclass, scoring, pytest.mark.eval). Use range assertions for ground truth counts, not exact numbers (data changes over time).

**New files:**
- `tests/eval/search_eval_queries.py` — 30 query definitions with ground truth
- `tests/eval/test_search_quality.py` — pytest eval runner

### Eval Query Set (30 queries across 8 categories)

**Name Lookup (3):**
1. "Find Agil C" → expect exact name match, connection_id returned
2. "Who is Karthik Viswanathan" → expect name match
3. "Priya" → partial name, expect multiple results

**Company-Specific (4):**
4. "Engineers at Google" → expect 50+ results (692 exp records)
5. "People at Infosys" → expect 100+ results (1,230 exp records)
6. "Who works at Flipkart right now" → filter is_current=true
7. "People from Crio.Do" → expect results (1,170 exp records)

**Company-Type (4):**
8. "People at IT services companies" → expect results from TCS/Infosys/Wipro/Cognizant
9. "Product company engineers" → expect Google/Amazon/Microsoft results
10. "People at FAANG companies" → canonical FAANG list
11. "Who's at consulting firms" → Deloitte/McKinsey/Accenture

**Career Transitions (5):**
12. "Moved from IT services to product companies" → 452 ground truth matches
13. "Engineering to product management transition" → function_area change
14. "People who left Google in last 2 years" → is_current=false, recent end_date
15. "Recently joined startups" → semantic search needed
16. "Career changers — engineering to non-engineering" → function_area shift

**Skills-Based (3):**
17. "People who know Python and React" → 5,151 ground truth
18. "Machine learning experts" → skill_name ILIKE '%machine learning%'
19. "Full stack developers with AWS experience" → multi-skill query

**Location (3):**
20. "Engineers in Bangalore" → location_city ILIKE '%bangalore%'
21. "Connections in the US" → location_country filtering
22. "People in London" → specific city

**Seniority (3):**
23. "Senior engineers" → seniority_level IN (senior, lead)
24. "Founders in my network" → seniority_level = 'founder' OR position ILIKE
25. "Directors and VPs" → seniority_level IN (director, vp)

**Semantic/Concept (3):**
26. "People working on AI agents" → vector search
27. "Climate tech founders" → vector search
28. "People interested in open source" → vector search

**Aggregation (2):**
29. "How many connections by country" → GROUP BY query
30. "Top companies in my network by connection count" → aggregation

### Eval Criteria Per Query

```python
@dataclass
class EvalQuery:
    query: str
    expected_min_results: int              # Minimum result count
    expected_query_type: str               # sql | vector | hybrid
    must_include_names: list[str] = []     # Names that MUST appear (ground truth)
    company_pattern: str | None = None     # For company-type queries: regex that N% of results must match
    no_hallucination: bool = True          # Check explainer doesn't invent facts
```

### Running Evals

- Use `pytest.mark.eval` marker, excluded from regular test runs
- Run against real DB (same as integration tests)
- Execute the actual SearchAgent.run() → collect results → check criteria
- Report: pass/fail per query + overall score

---

## Review Decisions (2026-03-31)

| # | Issue | Decision |
|---|-------|----------|
| Arch-1 | Hardcoded company names | Drop Phase 1a — enrichment will populate columns |
| Arch-2 | Batch query strategy | Two explicit batch queries (experiences + skills) |
| Arch-3 | Eval framework delegation | Use integration-test-creator-agent for scaffolding only |
| Arch-4 | Dual DB sessions | Accept, document as intentional |
| Code-1 | Extra SQL columns | Capture with explicit exclude set into `match_context` |
| Code-2 | Explainer fallback on failure | Skip explanation entirely, no half-baked guesses |
| Code-3 | Dedup key | `crawled_profile_id` primary, `connection_id` fallback |
| Code-4 | Broken retry loop | Fix hand-rolled loop, not a tenacity case |
| Tests-1 | Explainer unit tests | Unit test data-fetching/formatting, mock LLM |
| Tests-2 | Stale ground truth | Range assertions, not exact counts |
| Tests-3 | Dedup test coverage | Unit test `_collect_results` with duplicates |
| Tests-4 | Updating existing tests | Implicit — precommit-tests catches it |
| Perf-1 | Index verification | Verify indexes on `experience.crawled_profile_id` and `profile_skill.crawled_profile_id` during implementation |

## Verification Plan

1. **After Phase 1** (prompt fix): Run 3 manual queries via the API:
   - "People at IT services companies" → should return TCS/Infosys results (was returning 0)
   - "Moved from IT to product company" → should return 452+ matches
   - "Senior engineers at Google" → should return named people like Agil C, Bharat Thatavarti

2. **After Phase 2** (explainer fix): Check explanation quality:
   - "IT to product" query → explanation should mention specific companies like "Worked at Infosys (2018-2021) before joining Flipkart"
   - Should NOT hallucinate facts not in the person's profile

3. **After Phase 5** (eval framework): Run full 30-query eval suite
   - Target: >80% of queries return expected results
   - Target: 0 hallucinated explanations

4. **Run existing tests**: `precommit-tests` must pass throughout

---

## Execution Order

```
Phase 1b-1c (System Prompt cleanup) ── prompt-only change (1a dropped)
Phase 4 (Schema Context) ── complement to Phase 1, tiny change
Phase 2a-2b (match_context) ── contract + mapping change
Phase 3a-3b (Dedup + retry fix) ── search_agent.py fixes
Phase 2c-2e (Explainer enrichment) ── code change, needs DB session wiring
Phase 5 (Eval Framework) ── can be built in parallel with above
```

---

## Files to Modify

| File | Phase | Change |
|------|-------|--------|
| `src/linkedout/intelligence/prompts/search_system.md` | 1 | Replace broken business rules + examples |
| `src/linkedout/intelligence/schema_context.py` | 4 | Add data availability notes |
| `src/linkedout/intelligence/contracts.py` | 2a | Add `match_context` field |
| `src/linkedout/intelligence/agents/search_agent.py` | 2b, 3 | Capture extra columns, dedup |
| `src/linkedout/intelligence/explainer/why_this_person.py` | 2c, 2d | Enrich context, fix prompt |
| `src/linkedout/intelligence/controllers/search_controller.py` | 2e | Wire session to explainer |
| `tests/eval/search_eval_queries.py` | 5 | New: eval query definitions |
| `tests/eval/test_search_quality.py` | 5 | New: eval runner |
