# Phase E: Expand find_intro_paths with Tiers 3-5

**Effort:** 1 session
**Dependencies:** None (can start in parallel with A/B, but should land after C for benchmark measurement)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Extend the `find_intro_paths` tool from 2 tiers (direct employee + alumni) to 5 tiers (+ headline mentions, shared-company warm paths, investor connections).

**Note:** With web search (Phase B), the LLM already does multi-hop intro discovery naturally. These tool tiers are a convenience — the LLM did this naturally in the spike without the tool. However, having it as a tool reduces latency (one tool call vs. multiple SQL + web search calls).

## What to Do

### 1. Read current intro tool

**File:** `./src/linkedout/intelligence/tools/intro_tool.py`

Understand existing Tier 1 (direct at company) and Tier 2 (alumni) implementations.

### 2. Add Tier 3: Headline/community mentions

People mentioning target company in headline but not employed there:
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

### 3. Add Tier 4: Shared-company warm paths

Connections who worked at same prior companies as target employees:
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

### 4. Add Tier 5: Investor connections

Connections at firms that invested in target company. Uses `funding_round.lead_investors` (requires Phase A):
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

### 5. Update tool description

**File:** `./src/linkedout/intelligence/agents/search_agent.py`

Update the `find_intro_paths` tool description (around line 205) to advertise all 5 tiers.

### 6. Update return dict

Add `tier3_count`, `tier4_count`, `tier5_count` to the return dictionary so the LLM knows how many results each tier found.

### 7. Update tests

**File:** `./tests/unit/intelligence/test_intro_tool.py`

Add tests with specific per-tier assertions:

- `test_tier3_headline_mentions` — Mock DB with profiles mentioning target in headline but NOT employed there. Assert: results include those profiles, results do NOT include actual employees.
- `test_tier4_shared_company_warm_paths` — Mock DB with known overlapping experience data (two people who worked at the same company). Assert: the shared-company connection is found, the `shared_company` and `target_person` fields are populated.
- `test_tier5_investor_connections` — Mock DB with `funding_round.lead_investors` data. Assert: connections at investor firms are found via `CROSS JOIN LATERAL unnest(fr.lead_investors)`.
- `test_empty_tier_returns_zero` — Mock DB returning 0 rows for a tier. Assert: tier returns count of 0 without error (no exception, no crash).
- `test_tier4_performance` — Tier 4 (5-JOIN query) executes in < 5s on full dataset.
- `test_tier5_performance` — Tier 5 (CROSS JOIN LATERAL) executes in < 5s on full dataset.

Note: Performance tests should be marked `@pytest.mark.slow` or run only in integration context against a real DB.

## Verification

```bash
# Unit tests
pytest tests/unit/intelligence/test_intro_tool.py -v
pytest tests/unit/intelligence/ -v

# Manual verification
# "who can intro me to Stripe" — returns 3+ tiers

# Performance check (against real DB)
# Tier 4 and Tier 5 execute in < 5s on full dataset

# Precommit
precommit-tests
```

## Expected Impact

+1-2 points on intro-related queries (sj_01: warm intros to Stripe, etc.). However, impact may be smaller if the LLM is already discovering these paths via web search + SQL (Phase B).
