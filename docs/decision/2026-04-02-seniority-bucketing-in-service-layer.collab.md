# Decision: Seniority Display Bucketing in Service Layer

**Date:** 2026-04-02
**Status:** Accepted
**Context:** LinkedOut Dashboard - Seniority Distribution Chart

## Question
Where should the logic live that groups 10 raw seniority levels (c_suite, founder, vp, director, manager, lead, senior, mid, junior, intern) into 5 display tiers (Executive, Director, Manager, Senior IC, IC)?

## Key Findings
- Repository returns raw `seniority_level` counts from the database (GROUP BY)
- The 10 raw buckets are too granular for a chart, and "mid" is a meaningless catch-all
- NULL/unknown values (31% of data) should fold into "IC" rather than showing as "Unknown"
- This grouping is purely a presentation concern -- different views might want different groupings

## Decision
Bucketing lives in the service layer (`DashboardService`), not the repository SQL.

The repository returns raw seniority counts. The service maps them into display tiers using a static mapping dict and returns tiers in canonical order (Executive -> IC), not by count.

## Implications
- Repository stays reusable -- other consumers can group differently
- Bucketing logic is unit-testable without a database
- If new seniority levels are added to the DB, only the service mapping needs updating
- Frontend receives pre-bucketed data and renders directly -- no client-side grouping needed

## References
- `src/linkedout/dashboard/service.py` -- SENIORITY_DISPLAY_BUCKETS mapping
- `src/linkedout/dashboard/repository.py` -- raw seniority query
- `docs/specs/linkedout_dashboard.collab.md` -- spec v2
