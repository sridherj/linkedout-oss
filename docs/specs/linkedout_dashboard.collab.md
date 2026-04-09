---
feature: linkedout-dashboard
module: backend/src/linkedout/dashboard
linked_files:
  - backend/src/linkedout/dashboard/controller.py
  - backend/src/linkedout/dashboard/service.py
  - backend/src/linkedout/dashboard/repository.py
  - backend/src/linkedout/dashboard/schemas.py
version: 1
last_verified: "2026-04-09"
---

# LinkedOut Dashboard

**Created:** 2026-04-09 — Adapted from internal spec to OSS implementation

## Intent

Provide a read-only network aggregation endpoint that summarizes a user's LinkedIn connection data across 7 dimensions. Powers the frontend dashboard with pre-computed breakdowns. All queries are scoped to the authenticated user's active connections via RLS and explicit WHERE clauses.

## Behaviors

### Aggregation Endpoint

- **Single async GET endpoint returns all dashboard data**: The dashboard endpoint (GET /tenants/{tenant_id}/bus/{bu_id}/dashboard) returns a DashboardResponse with 7 aggregation sections and a total connection count. The X-App-User-Id header identifies the user. Verify all 7 sections are populated for users with connections.

- **RLS-scoped database session**: The controller extracts app_user_id from the X-App-User-Id request header and passes it to DbSessionManager.get_session(DbSessionType.READ, app_user_id=app_user_id), which sets the PostgreSQL session variable for Row-Level Security. All subsequent dashboard queries are filtered to rows the authenticated user is authorized to see. Verify that dashboard data is tenant-scoped and inaccessible across users.

- **Async execution via asyncio.to_thread**: The synchronous DB queries run in a thread via asyncio.to_thread to avoid blocking the async event loop. The controller is an async def that delegates all work (session creation, repository instantiation, service call) to a synchronous inner function. Verify the endpoint is async-compatible.

- **Empty network returns zero-filled response**: When the user has zero active connections, the endpoint returns a DashboardResponse with all counts at zero and empty breakdown lists. The service short-circuits after checking total_connections == 0, avoiding unnecessary queries. Verify no errors occur for empty networks.

### Aggregation Sections

- **Enrichment status breakdown**: Counts connections whose linked crawled_profile has has_enriched_data=True vs False, via JOIN from ConnectionEntity to CrawledProfileEntity. Calculates enriched_pct as percentage (0-100, 1 decimal). Verify percentages sum to 100.

- **Function area breakdown** (API key: `industry_breakdown`): Groups connections by crawled_profile.function_area, excluding nulls. Returns top 10 by count with percentages. The API field name is `industry_breakdown` for historical reasons but the data represents function areas. Verify top-10 limit is applied and null function areas are excluded.

- **Seniority distribution**: Groups connections by crawled_profile.seniority_level (raw values, no COALESCE — nulls included). The service layer collapses raw levels into 5 display tiers: Executive (c_suite, founder, vp), Director, Manager, Senior IC (lead, senior), IC (mid, junior, intern, NULL, unknown values). Tiers are ordered canonically (Executive -> IC), not by count. Empty tiers are omitted. Verify all connections are bucketed with no separate "Unknown" tier.

- **Location top cities**: Groups connections by crawled_profile.location_city, excluding null cities. Returns top 10 by count with percentages. Verify null cities are excluded.

- **Top companies**: Groups connections by crawled_profile.current_company_name, excluding nulls. Returns top 10 by count with percentages. Verify null companies are excluded.

- **Affinity tier distribution**: Groups connections by dunbar_tier with null coalesced to "Unassigned" via COALESCE. Returns all tiers sorted by count descending. Verify tier labels match affinity scorer output (inner_circle, familiar, active, acquaintance, Unassigned).

- **Network sources**: Uses a subquery that unnests the connection.sources ARRAY(Text) column and counts occurrences of each source type. Only connections with non-null sources are included. Multi-source connections contribute to multiple source counts. Verify multi-source connections are counted correctly.

> Edge: Network sources query uses PostgreSQL's unnest() function on an ARRAY(Text) column. This will not work with SQLite test databases.

### Architecture

- **Repository layer**: DashboardRepository contains all SQL queries. A shared _base_connection_filter method applies tenant_id, bu_id, app_user_id, and is_active=True filters to all queries. Each aggregation has a dedicated repository method.

- **Service layer**: DashboardService orchestrates repository calls and assembles the DashboardResponse. It handles seniority tier bucketing (via _SENIORITY_TIER_MAP) and percentage calculation (via _to_aggregates). The service takes a DashboardRepository in its constructor.

- **Schema layer**: Three Pydantic models — AggregateCount (label + count + pct), EnrichmentStatus (enriched + unenriched + total + enriched_pct), and DashboardResponse (all sections + total_connections).

## Decisions

### Direct aggregation over materialized views — 2026-03-28
**Chose:** Live SQL aggregation queries per request
**Over:** Pre-computed materialized views or cache
**Because:** Connection counts are typically under 5000 per user. Direct queries are fast enough for v1. Materialized views add refresh complexity.

### Single endpoint over per-section endpoints — 2026-03-28
**Chose:** One GET returning all 7 sections
**Over:** Separate endpoints per aggregation
**Because:** The frontend dashboard loads all sections simultaneously. One request reduces round-trips. If any section becomes expensive, it can be split later.

### RLS enforcement at controller level — 2026-04-02
**Chose:** Pass app_user_id to get_session so RLS policies filter dashboard queries
**Over:** Relying on application-level WHERE clauses for tenant scoping
**Because:** RLS provides defense-in-depth at the database level, ensuring no query can accidentally bypass tenant filtering.

### Repository-Service-Controller pattern (no base class) — 2026-04-09
**Chose:** Hand-written repository, service, and controller without extending base CRUD classes
**Over:** Using CRUDRouterFactory or BaseService/BaseRepository
**Because:** The dashboard is read-only aggregation with no CRUD operations. The base stack patterns do not apply.

## Not Included

- Time-series data (growth over time)
- Comparison with other users or benchmarks
- Caching or materialized views
- Filtering by date range or subset of connections
- Per-section endpoints (all data returned in single response)
