# Sub-Phase 1: Backend — Network Aggregation Endpoints

**Goal:** linkedin-ai-production
**Phase:** 5b — Network Dashboard
**Depends on:** Nothing (first sub-phase)
**Estimated effort:** 2-3h
**Source plan sections:** 1.1–1.5

---

## Objective

Build a read-only dashboard module at `src/linkedout/dashboard/` with a single endpoint that returns all network aggregation data for a user. This module is NOT a CRUD module — it uses a custom controller, not `CRUDRouterFactory`.

## Context

The dashboard provides a network composition overview: enrichment status, industry breakdown, seniority distribution, location top-10, top companies, affinity tier distribution, and network sources. All data is derived from existing `connection` and `crawled_profile` entities via aggregation queries.

**Cross-phase reconciliation (C5):** The endpoint uses `X-App-User-Id` header for user identity (not URL path param), consistent with Phase 4 decision P4-3.

## Pre-Flight Checks

Before starting, verify these exist:
- [ ] `src/linkedout/connection/entities/connection_entity.py` — has `app_user_id`, `dunbar_tier`, `sources` (ARRAY column), `crawled_profile_id`
- [ ] `src/linkedout/crawled_profile/entities/crawled_profile_entity.py` — has `has_enriched_data`, `function_area`, `seniority_level`, `location_city`, `current_company_name`
- [ ] `connection.sources` is a PostgreSQL `ARRAY(Text)` column (Phase 3 migration)

## Files to Create

```
src/linkedout/dashboard/
├── __init__.py
├── schemas.py          # Response schemas (DashboardResponse, EnrichmentStatus, AggregateCount)
├── repository.py       # 7 aggregation queries, session-injected
├── service.py          # Orchestrates repository calls, assembles DashboardResponse
└── controller.py       # Custom FastAPI controller with single GET endpoint
```

---

## Step 1: Response Schemas (`schemas.py`)

Create Pydantic schemas for the dashboard response:

```python
from pydantic import BaseModel


class AggregateCount(BaseModel):
    label: str
    count: int
    pct: float  # percentage of total, 0-100


class EnrichmentStatus(BaseModel):
    enriched: int       # connections with crawled_profile.has_enriched_data=True
    unenriched: int     # connections with crawled_profile.has_enriched_data=False
    total: int
    enriched_pct: float  # 0-100


class DashboardResponse(BaseModel):
    enrichment_status: EnrichmentStatus
    industry_breakdown: list[AggregateCount]      # top 10
    seniority_distribution: list[AggregateCount]   # all levels
    location_top: list[AggregateCount]             # top 10 cities
    top_companies: list[AggregateCount]            # top 10
    affinity_tier_distribution: list[AggregateCount]  # 4 tiers
    total_connections: int
    network_sources: list[AggregateCount]          # by import source
```

---

## Step 2: Dashboard Repository (`repository.py`)

Create a repository with 7 aggregation query methods. This is NOT a `BaseRepository` subclass — it's a plain class with session injection.

**All queries are user-scoped:** filter by `connection.app_user_id = :app_user_id` (and `tenant_id`/`bu_id` from TenantBuMixin).

### Methods:

| Method | Query | Join |
|--------|-------|------|
| `get_enrichment_status(tenant_id, bu_id, app_user_id)` | COUNT grouped by `crawled_profile.has_enriched_data` | INNER JOIN crawled_profile |
| `get_industry_breakdown(tenant_id, bu_id, app_user_id)` | COUNT grouped by `crawled_profile.function_area`, top 10 | INNER JOIN crawled_profile |
| `get_seniority_distribution(tenant_id, bu_id, app_user_id)` | COUNT grouped by `crawled_profile.seniority_level` | INNER JOIN crawled_profile |
| `get_location_top(tenant_id, bu_id, app_user_id)` | COUNT grouped by `crawled_profile.location_city`, top 10, exclude NULL | INNER JOIN crawled_profile |
| `get_top_companies(tenant_id, bu_id, app_user_id)` | COUNT grouped by `crawled_profile.current_company_name`, top 10, exclude NULL | INNER JOIN crawled_profile |
| `get_affinity_tier_distribution(tenant_id, bu_id, app_user_id)` | COUNT grouped by `connection.dunbar_tier` | No join |
| `get_network_sources(tenant_id, bu_id, app_user_id)` | `unnest(connection.sources)`, COUNT per source | No join |

### Implementation notes:

- Use raw SQLAlchemy `select()` with `func.count()`, `group_by()`, `order_by(desc)`, `limit(10)`
- Session injected via constructor (consistent with codebase patterns)
- For `get_network_sources`: use `func.unnest(ConnectionEntity.sources)` and filter `sources != '{}'` before unnest
- For NULL handling: exclude NULL `location_city` and `current_company_name` from their respective aggregates
- For NULL `seniority_level` or `function_area`: group under `"Unknown"` label using `coalesce()`

---

## Step 3: Dashboard Service (`service.py`)

Create `DashboardService` that:
1. Takes `DashboardRepository` as a constructor dependency
2. Has a single method: `get_dashboard(tenant_id, bu_id, app_user_id) -> DashboardResponse`
3. Calls all 7 repository methods
4. Assembles results into `DashboardResponse`
5. Calculates `enriched_pct` from enrichment counts
6. Calculates `pct` for each `AggregateCount` from total connections

### Edge cases:
- No connections: return all zeros, empty lists
- All unenriched: industry/seniority/location/company return empty lists (stubs have no data)
- Division by zero: if total is 0, all percentages are 0.0

---

## Step 4: Dashboard Controller (`controller.py`)

Create a custom FastAPI router (NOT `CRUDRouterFactory`):

```python
router = APIRouter(prefix="/tenants/{tenant_id}/bus/{bu_id}/dashboard", tags=["dashboard"])

@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    tenant_id: str,
    bu_id: str,
    request: Request,  # extract X-App-User-Id header
    session: AsyncSession = Depends(get_session),
):
    app_user_id = request.headers.get("X-App-User-Id")
    # ... instantiate repository, service, call get_dashboard
```

**Important:** Use `X-App-User-Id` header (not URL path param) per cross-phase reconciliation C5.

---

## Step 5: Registration in `main.py`

- Import and include the dashboard router in `main.py`
- Add a comment marking it as a read-only aggregation route (not CRUD)

---

## Step 6: Compliance Checker Exclusion

Add `dashboard` to the CRUD compliance checker's exclusion list. This module intentionally has no entity and no `CRUDRouterFactory`.

---

## Verification

- [ ] `GET /tenants/{tid}/bus/{bid}/dashboard` with `X-App-User-Id` header returns valid JSON with all 7 aggregate sections
- [ ] User scoping works: different `app_user_id` returns different data
- [ ] Empty user returns all zeros, empty lists (no errors)
- [ ] Module structure matches plan: `src/linkedout/dashboard/{__init__, schemas, repository, service, controller}.py`
- [ ] Server starts without errors (`python main.py`)
