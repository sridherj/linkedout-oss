# Sub-Phase 2: Affinity Scoring Engine

**Goal:** linkedin-ai-production
**Phase:** 4 — Intelligence: Search Engine + Affinity Scoring
**Depends on:** Nothing (independent of SP-1; can run in parallel)
**Estimated effort:** 2-3h
**Source plan sections:** 4.5

---

## Objective

Build the `AffinityScorer` that computes affinity scores and assigns Dunbar tiers for all connections of a user. Scores are stored directly on the `connection` table.

## Context

Affinity scoring uses 4 signals (mutual_connections hardcoded to 0 for v1). The scorer runs as a batch operation after data load and after enrichment. Individual connection scoring is also supported for incremental updates.

## Pre-Flight Checks

Before starting, verify these exist:
- [ ] `src/linkedout/connection/entities/connection_entity.py` — has columns: `affinity_score`, `affinity_source_count`, `affinity_recency`, `affinity_mutual_connections`, `affinity_career_overlap`, `affinity_computed_at`, `affinity_version`, `dunbar_tier`
- [ ] `src/linkedout/crawled_profile/entities/crawled_profile_entity.py` — has `experience` relationship or joinable
- [ ] Experience entity exists with `company_id` or `company_name` column

## Files to Create

```
src/linkedout/intelligence/
├── __init__.py                      # (create if not exists)
└── scoring/
    ├── __init__.py
    └── affinity_scorer.py           # AffinityScorer class
```

---

## Step 1: AffinityScorer Implementation

**Class:** `AffinityScorer`

```python
class AffinityScorer:
    def __init__(self, session: Session):
        self._session = session

    def compute_for_user(self, app_user_id: str) -> int:
        """Recompute affinity for all connections of a user. Returns count updated."""

    def compute_for_connection(self, connection_id: str) -> float:
        """Recompute affinity for a single connection. Returns new score."""
```

### Signal Computation

| Signal | Column | Calculation | Range |
|--------|--------|-------------|-------|
| `affinity_source_count` | `connection.affinity_source_count` | `len(sources)` normalized: 1=0.2, 2=0.5, 3=0.8, 4+=1.0 | 0-1 |
| `affinity_recency` | `connection.affinity_recency` | Decay from `connected_at`: <1yr=1.0, 1-3yr=0.7, 3-5yr=0.4, 5+yr=0.2 | 0-1 |
| `affinity_mutual_connections` | `connection.affinity_mutual_connections` | **v1: hardcoded 0** | 0 |
| `affinity_career_overlap` | `connection.affinity_career_overlap` | Shared companies / max(5, total companies), capped at 1.0 | 0-1 |

### v1 Weighted Formula (re-weighted, excluding mutual_connections)

```
affinity_score = source_count × 0.375 + recency × 0.375 + career_overlap × 0.25
Final: round(score × 100, 1)  → 0-100 scale
```

### Dunbar Tier Assignment (per user, ranked by affinity_score)

| Tier | Rank Range |
|------|-----------|
| `inner_circle` | Top 15 |
| `active` | 16-50 |
| `familiar` | 51-150 |
| `acquaintance` | 151+ |

### Performance: Batch Career Overlap

Pre-fetch ALL experience company_ids for the user's connections in ONE query to avoid O(N) queries for ~24K connections:

```sql
SELECT c.id as connection_id, e.company_id
FROM connection c
JOIN crawled_profile cp ON c.crawled_profile_id = cp.id
JOIN experience e ON e.crawled_profile_id = cp.id
WHERE c.app_user_id = :app_user_id
```

Build `{connection_id: set(company_ids)}` in-memory. Career overlap = set intersection against the user's own company set.

### Bulk Update

After computing all scores and tiers, bulk update connection rows. Set `affinity_computed_at = now()` and bump `affinity_version`.

---

## Step 2: Admin Recompute Endpoint (Optional)

```python
@router.post('/tenants/{tenant_id}/bus/{bu_id}/affinity/recompute')
async def recompute_affinity(tenant_id: str, bu_id: str, app_user_id: str = Header(...)):
    """Trigger batch affinity recomputation for a user."""
```

This is a convenience endpoint for admin/dev use. Wraps `AffinityScorer.compute_for_user()` via `asyncio.to_thread()`.

---

## Step 3: Unit Tests

Create `tests/unit/linkedout/intelligence/test_affinity_scorer.py`:
- Score computation with known inputs → expected output
- Source count normalization (1 source=0.2, 2=0.5, etc.)
- Recency decay (<1yr=1.0, 1-3yr=0.7, etc.)
- Career overlap with shared companies
- Dunbar tier assignment (top 15 = inner_circle, etc.)
- Edge cases: no `connected_at` (default recency), no experience data (career_overlap=0)
- Bulk computation returns correct count

---

## Completion Criteria

- [ ] `AffinityScorer.compute_for_user()` computes scores for all connections and assigns Dunbar tiers
- [ ] Individual signals stored in separate columns (`affinity_source_count`, `affinity_recency`, `affinity_career_overlap`)
- [ ] Final score on 0-100 scale, stored in `affinity_score`
- [ ] `dunbar_tier` assigned by rank (inner_circle top 15, active 16-50, familiar 51-150, acquaintance 151+)
- [ ] Batch career overlap uses single pre-fetch query (not O(N) queries)
- [ ] `affinity_computed_at` and `affinity_version` updated after computation
- [ ] Unit tests pass with SQLite test data
