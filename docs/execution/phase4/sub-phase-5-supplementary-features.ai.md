# Sub-Phase 5: Supplementary Features — People Like X, Warm Intros, Search History

**Goal:** linkedin-ai-production
**Phase:** 4 — Intelligence: Search Engine + Affinity Scoring
**Depends on:** SP-1 (vector tool), SP-4 (endpoint pattern + search controller)
**Estimated effort:** 2-3h
**Source plan sections:** 4.7, 4.8, 4.9

---

## Objective

Add three supplementary search features:
1. **People Like X** — similarity search given a specific person
2. **Warm Intro Paths** — find shared-company connections who could introduce you
3. **Search History** — persist searches and enable saved search functionality

## Pre-Flight Checks

Before starting, verify these exist:
- [ ] `src/linkedout/intelligence/controllers/search_controller.py` — search router (SP-4 output)
- [ ] `src/linkedout/intelligence/tools/vector_tool.py` — vector search capability (SP-1 output)
- [ ] Experience entity with `company_id` column (for warm intros)
- [ ] `SearchHistoryService` CRUD exists (check `src/linkedout/` for search_history module)

---

## Step 1: People Like X Endpoint (4.7)

Add to `search_controller.py`:

```python
@search_router.post('/search/similar/{connection_id}')
async def find_similar(
    tenant_id: str, bu_id: str, connection_id: str,
    limit: int = Query(default=10, le=50),
    app_user_id: str = Header(..., alias='X-App-User-Id'),
):
    """Find people similar to a given connection."""
```

**Algorithm:**
1. Look up the connection's `crawled_profile.embedding`
2. If `has_enriched_data=FALSE` (stub profile): return 400 error "Profile must be enriched for similarity search"
3. Run pgvector cosine similarity over user-scoped connections:
   ```sql
   SELECT cp.*, c.affinity_score, c.dunbar_tier,
          1 - (cp.embedding <=> :target_embedding) AS similarity
   FROM crawled_profile cp
   JOIN connection c ON c.crawled_profile_id = cp.id
   WHERE c.app_user_id = :app_user_id
     AND cp.id != :source_profile_id
     AND cp.embedding IS NOT NULL
   ORDER BY cp.embedding <=> :target_embedding
   LIMIT :limit
   ```
4. Return ranked `list[SearchResultItem]` with similarity scores

**Implementation note:** This uses direct SQL with `session.execute(text(...))` — it does NOT go through the SearchAgent (no LLM needed). It's a pure vector similarity lookup.

---

## Step 2: Warm Intro Paths Endpoint (4.8)

Add to `search_controller.py`:

```python
@search_router.get('/search/intros/{connection_id}')
async def find_intro_paths(
    tenant_id: str, bu_id: str, connection_id: str,
    app_user_id: str = Header(..., alias='X-App-User-Id'),
):
    """Find mutual connections who could introduce you to target."""
```

**v1 Algorithm (depth-1, shared companies):**
1. Get the target connection's `crawled_profile_id`
2. Find the target person's companies from their `experience` history
3. Find user's other connections who share companies with the target:
   ```sql
   SELECT DISTINCT c2.id, cp2.full_name, cp2.current_company_name, c2.affinity_score,
          e1.company_name as shared_company
   FROM experience e1
   JOIN experience e2 ON e1.company_id = e2.company_id
        AND e1.crawled_profile_id != e2.crawled_profile_id
   JOIN connection c2 ON c2.crawled_profile_id = e2.crawled_profile_id
   JOIN crawled_profile cp2 ON cp2.id = c2.crawled_profile_id
   WHERE e1.crawled_profile_id = :target_profile_id
     AND c2.app_user_id = :app_user_id
   ORDER BY c2.affinity_score DESC NULLS LAST
   LIMIT 5
   ```
4. Rank by affinity score of the mutual connection

**Response contract:**
```json
{
  "target": {"connection_id": "conn_xxx", "name": "Target Person"},
  "intro_paths": [
    {
      "via": {"connection_id": "conn_yyy", "name": "Mutual Person", "affinity_score": 85},
      "shared_context": "Both worked at Stripe",
      "strength": "strong"
    }
  ]
}
```

**Strength mapping:** affinity_score >= 70 = "strong", >= 40 = "moderate", < 40 = "weak"

---

## Step 3: Search History Integration (4.9)

After each search completes (SSE stream done), persist via `SearchHistoryService`:

```python
# In _stream_search, after all events yielded:
await asyncio.to_thread(
    search_history_service.create,
    SearchHistoryCreateRequest(
        tenant_id=tenant_id,
        bu_id=bu_id,
        app_user_id=app_user_id,
        query_text=request.query,
        query_type=response.query_type,
        result_count=response.result_count,
        is_saved=False,
    )
)
```

**Existing CRUD handles:**
- Save search: PATCH `is_saved=True` + `saved_name` on the search history record
- Re-run saved search: Client re-submits `query_text` to the search endpoint (no special backend logic)
- List searches: GET `/search_histories?app_user_id=X`

**If `SearchHistoryService` doesn't exist:** Skip this step and note it in the output. Search works without history persistence.

---

## Step 4: Unit Tests

Add to existing test files or create new ones:

**`tests/unit/linkedout/intelligence/test_people_like_x.py`:**
- Returns error for unenriched profiles (no embedding)
- Excludes the source profile from results
- Results are user-scoped
- Returns similarity scores

**`tests/unit/linkedout/intelligence/test_warm_intros.py`:**
- Finds shared-company connections
- Ranks by affinity score
- Returns correct strength labels
- Handles target with no experience data (empty intro_paths)

---

## Completion Criteria

- [ ] `POST /search/similar/{connection_id}` returns similar profiles with similarity scores
- [ ] Similar search rejects unenriched profiles with 400 error
- [ ] Similar search is user-scoped (only returns user's connections)
- [ ] `GET /search/intros/{connection_id}` returns intro paths with shared company context
- [ ] Intro paths ranked by affinity score of the mutual connection
- [ ] Search history persisted after each search completes (if SearchHistoryService exists)
- [ ] Unit tests pass for People Like X and Warm Intros
