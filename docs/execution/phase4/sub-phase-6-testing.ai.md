# Sub-Phase 6: Comprehensive Testing

**Goal:** linkedin-ai-production
**Phase:** 4 — Intelligence: Search Engine + Affinity Scoring
**Depends on:** SP-1 through SP-5 (all prior sub-phases)
**Estimated effort:** 2-3h
**Source plan sections:** 4.10

---

## Objective

Build the full test suite for Phase 4: unit tests for any gaps, integration tests against PostgreSQL, and live LLM tests. This sub-phase validates the entire intelligence layer end-to-end.

## Pre-Flight Checks

Before starting, verify:
- [ ] All SP-1 through SP-5 code exists and is importable
- [ ] PostgreSQL is running with pgvector extension enabled
- [ ] Test database has seed data (connections + crawled_profiles with embeddings)
- [ ] `.env.test` has `SEARCH_LLM_MODEL` configured

## Files to Create

```
tests/
├── unit/
│   └── linkedout/intelligence/
│       ├── __init__.py
│       ├── test_sql_tool.py          # (extend if created in SP-1)
│       ├── test_vector_tool.py       # (extend if created in SP-1)
│       ├── test_search_agent.py      # (extend if created in SP-3)
│       ├── test_affinity_scorer.py   # (extend if created in SP-2)
│       └── test_why_this_person.py   # (extend if created in SP-4)
├── integration/
│   └── linkedout/intelligence/
│       ├── __init__.py
│       ├── test_search_integration.py
│       └── test_affinity_integration.py
└── live_llm/
    └── linkedout/intelligence/
        ├── __init__.py
        └── test_search_live.py
```

---

## Step 1: Fill Unit Test Gaps

Review what SP-1 through SP-5 created and fill any missing unit test coverage. Refer to the unit test table from the detailed plan:

| Component | What to test | Mocking |
|-----------|-------------|---------|
| `sql_tool.execute_sql()` | SELECT-only validation, LIMIT injection, user-scoping, error hints | SQLite session |
| `vector_tool.search_profiles()` | Embedding call, SQL generation, user-scoping | Mock embedding client, SQLite (skip pgvector) |
| `AffinityScorer` | Score computation, Dunbar tier assignment, signal normalization | SQLite session with test data |
| `WhyThisPersonExplainer` | Prompt formatting, response parsing | Mock LLM client |
| `SearchAgent` | Tool routing, iteration loop, error recovery | Mock tools + LLM |

---

## Step 2: Integration Tests (PostgreSQL)

Create `tests/integration/linkedout/intelligence/test_search_integration.py`:

| Test | What it validates |
|------|-------------------|
| `test_search_user_isolation` | User A's search returns only User A's connections |
| `test_cross_user_isolation_negative` | User A search returns zero results from User B's connections |
| `test_llm_sql_injection_negative` | Query that tricks LLM into dropping user-scoping WHERE → post-execution validation catches it |
| `test_unenriched_in_sql_results` | Regular JOIN returns both enriched and stub profiles |
| `test_unenriched_visibility_split` | SQL returns enriched + unenriched; vector returns only enriched |
| `test_vector_search_user_scoped` | pgvector results filtered to user's network |
| `test_sse_streaming` | SSE events stream correctly, no buffering |
| `test_people_like_x_user_scoped` | Returns similar profiles only within user's network |
| `test_warm_intro_paths` | Finds shared-company connections |

Create `tests/integration/linkedout/intelligence/test_affinity_integration.py`:

| Test | What it validates |
|------|-------------------|
| `test_batch_affinity_computation` | All connections get scores + tiers |
| `test_dunbar_tier_distribution` | Top 15 = inner_circle, 16-50 = active, etc. |
| `test_affinity_signals_stored` | Individual signal columns populated |
| `test_recompute_idempotent` | Running twice produces same results |

**Test data setup:** Use fixtures or factory functions to create:
- 2 users (User A, User B) with separate connections
- Mix of enriched and unenriched connections for User A
- Connections with embeddings for vector search tests
- Connections with shared company experience for warm intro tests

---

## Step 3: Live LLM Tests

Create `tests/live_llm/linkedout/intelligence/test_search_live.py` (marked `@pytest.mark.live_llm`):

| Test | What it validates |
|------|-------------------|
| `test_nl_query_to_sql` | LLM generates valid, user-scoped SQL for "engineers at Google" |
| `test_nl_query_to_vector` | LLM routes "people working on AI agents" to `search_profiles` |
| `test_why_this_person_relevance` | Generated explanations reference relevant profile attributes |
| `test_error_recovery_bad_column` | LLM retries after column-not-found error with hint |

**Important:** These tests hit real LLM API. They should:
- Be marked with `@pytest.mark.live_llm` so they're excluded from CI by default
- Use a small result set (limit=5) to minimize cost
- Assert on structure (valid SQL, correct tool called) not exact output

---

## Step 4: Run Full Test Suite

```bash
# Unit tests
pytest tests/unit/linkedout/intelligence/ -v

# Integration tests (requires PostgreSQL)
pytest tests/integration/linkedout/intelligence/ -v

# Live LLM tests (requires API key)
pytest tests/live_llm/linkedout/intelligence/ -v -m live_llm

# Full precommit-tests
precommit-tests
```

---

## Completion Criteria

- [ ] All unit test gaps from SP-1 through SP-5 filled
- [ ] Integration tests pass against PostgreSQL with pgvector
- [ ] User isolation verified: cross-user search returns zero results
- [ ] Unenriched visibility split verified: SQL returns both, vector returns only enriched
- [ ] SSE streaming verified in integration test
- [ ] Affinity batch computation verified end-to-end
- [ ] Live LLM tests pass (NL → SQL, NL → vector, error recovery)
- [ ] `precommit-tests` passes with no regressions
