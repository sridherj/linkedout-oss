# Pipeline: API vs Direct DB Access

**Date:** 2026-03-28
**Status:** Deferred
**Context:** Phase 2b SP-7 (Agent Definition Updates)

## Question

Should the startup pipeline agents (`second-brain/agents/pipeline/`) call LinkedOut's FastAPI endpoints instead of connecting directly to the PostgreSQL database via psycopg2?

## Current State

The pipeline code in `second-brain` uses raw SQL via `agents.pipeline.db` and `agents.pipeline.company_ops` to read/write `company`, `startup_tracking`, `funding_round`, `growth_signal`, and pipeline infrastructure tables directly. Connection is via `LINKEDOUT_DSN` env var.

## Arguments For API

- **Decoupling:** No shared DB credentials between repos. Pipeline becomes a true API client.
- **Validation:** Business logic and schema validation in LinkedOut's service layer would be enforced.
- **Evolvability:** LinkedOut can change its schema without breaking the pipeline (API contract is the boundary).
- **Observability:** API calls are logged, rate-limited, and traceable out of the box.

## Arguments For Direct DB (Current)

- **Simplicity:** No HTTP overhead, no auth tokens to manage, no API versioning.
- **Performance:** Bulk operations (e.g., `execute_values` for 100+ raw_feed_items) are much faster via direct SQL.
- **Pipeline-specific tables:** `raw_feed_item`, `pipeline_state`, `extracted_company` etc. are pipeline infrastructure — exposing them via LinkedOut's API would pollute the API surface.

## Decision

Deferred. Current direct-DB approach works and was just migrated to LinkedOut's schema in Phase 2b. Revisit when:
- A second consumer of the same data appears (e.g., a frontend dashboard hitting the same tables)
- The pipeline needs to run on a different host than the DB
- Schema drift between pipeline SQL and LinkedOut entities causes bugs

## Implications

- Pipeline continues using `LINKEDOUT_DSN` + raw psycopg2
- LinkedOut API endpoints exist for frontend/external use but pipeline bypasses them
- If revisited, consider a hybrid: API for company/funding CRUD, direct DB for pipeline infrastructure tables
