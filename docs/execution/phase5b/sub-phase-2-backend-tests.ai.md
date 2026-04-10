# Sub-Phase 2: Backend — Dashboard Tests

**Goal:** linkedin-ai-production
**Phase:** 5b — Network Dashboard
**Depends on:** SP-1 (Backend: Aggregation Endpoints)
**Estimated effort:** 1h
**Source plan sections:** 2.1–2.3

---

## Objective

Write unit tests for the dashboard service and repository, plus an integration test for the dashboard endpoint against real PostgreSQL. Follow existing test patterns in the codebase.

## Context

The dashboard module at `src/linkedout/dashboard/` is a read-only aggregation module (not CRUD). Tests follow the standard layered pattern: mock the repository in service tests, use SQLite in-memory DB for repository tests, and PostgreSQL for integration tests.

## Pre-Flight Checks

Before starting, verify SP-1 output exists:
- [ ] `src/linkedout/dashboard/schemas.py` — `DashboardResponse`, `EnrichmentStatus`, `AggregateCount`
- [ ] `src/linkedout/dashboard/repository.py` — `DashboardRepository` with 7 aggregation methods
- [ ] `src/linkedout/dashboard/service.py` — `DashboardService` with `get_dashboard()`
- [ ] `src/linkedout/dashboard/controller.py` — registered and serving `GET /dashboard`

## Files to Create

```
tests/
├── unit/linkedout/dashboard/
│   ├── __init__.py
│   ├── test_dashboard_service.py
│   └── test_dashboard_repository.py
└── integration/linkedout/dashboard/
    ├── __init__.py
    └── test_dashboard_endpoint.py
```

---

## Step 1: Unit Tests — Dashboard Service (`test_dashboard_service.py`)

Mock `DashboardRepository`. Test scenarios:

1. **Correct assembly:** Service assembles `DashboardResponse` correctly from repository return values (all 7 sections populated)
2. **Enrichment calculation:** Enriched=10, unenriched=5, total=15, pct=66.67
3. **Top-N sorting:** Aggregates sorted by count descending
4. **Percentage calculation:** Each `AggregateCount.pct` correctly calculated relative to total
5. **Empty connections:** When repository returns all empty/zero — service returns all zeros, empty lists, pct=0.0
6. **Unknown labels:** Repository returns `None` labels for seniority/function — service maps to `"Unknown"`

### Test pattern (from existing codebase):
- Mock `DashboardRepository` methods to return controlled data
- Assert `DashboardResponse` fields match expected values
- No database involved

---

## Step 2: Unit Tests — Dashboard Repository (`test_dashboard_repository.py`)

Use SQLite in-memory DB (consistent with other repository unit tests in this codebase).

**Important SQLite limitation:** SQLite does not support `unnest()` for ARRAY columns. The `get_network_sources` test may need to be deferred to integration tests (PostgreSQL). Document this limitation with a `@pytest.mark.skip` or move that specific test to integration.

Test scenarios:

1. **Enrichment status:** Seed connections with mixed `has_enriched_data` True/False — verify correct counts
2. **Top-N limit:** Seed >10 industries — verify only top 10 returned, sorted by count desc
3. **NULL exclusion:** Seed connections with NULL `location_city` and `current_company_name` — verify excluded from respective aggregates
4. **User scoping:** Seed two users — verify each gets only their data
5. **Unknown coalesce:** Seed connections with NULL `seniority_level` — verify grouped under `"Unknown"`

### Test pattern:
- Use in-memory SQLite session fixture
- Seed `ConnectionEntity` + `CrawledProfileEntity` rows
- Call repository methods directly, assert return values

---

## Step 3: Integration Test — Dashboard Endpoint (`test_dashboard_endpoint.py`)

Test against real PostgreSQL (consistent with `tests/integration/` pattern).

### Setup:
- Seed a tenant, BU, and app_user
- Seed 20 connections: 10 with `has_enriched_data=True` (enriched crawled_profiles with varied data), 10 with `has_enriched_data=False` (stub crawled_profiles)
- Enriched profiles should have varied: `function_area`, `seniority_level`, `location_city`, `current_company_name`, `dunbar_tier`
- Set `sources` arrays on connections (e.g., `["linkedin"]`, `["linkedin", "gmail"]`)

### Test cases:

1. **Full dashboard response:** `GET /dashboard` with `X-App-User-Id` header → validates all 7 aggregate sections return expected counts
2. **User isolation:** Seed a second user with different connections → call with second user's ID → verify different data returned
3. **Empty state:** Call with a user that has no connections → verify all zeros, empty lists
4. **Enrichment accuracy:** Verify `enriched=10, unenriched=10, total=20, enriched_pct=50.0`
5. **Source aggregation:** Verify `unnest(sources)` produces correct counts (e.g., linkedin=20, gmail=10 if some have both)

### Test pattern:
- Use the existing integration test fixtures (PostgreSQL session, test client)
- HTTP calls via `TestClient`
- Include `X-App-User-Id` header in requests

---

## Verification

- [ ] `pytest tests/unit/linkedout/dashboard/ -v` passes
- [ ] `pytest tests/integration/linkedout/dashboard/ -v` passes against PostgreSQL
- [ ] No test relies on test execution order (each test is independent)
- [ ] `precommit-tests` passes (all existing tests still pass)
