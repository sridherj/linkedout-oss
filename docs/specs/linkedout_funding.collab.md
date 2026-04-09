---
feature: linkedout-funding
module: backend/src/linkedout/funding
linked_files:
  - backend/src/linkedout/funding/entities/funding_round_entity.py
  - backend/src/linkedout/funding/entities/growth_signal_entity.py
  - backend/src/linkedout/funding/entities/startup_tracking_entity.py
  - backend/src/linkedout/funding/repositories/funding_round_repository.py
  - backend/src/linkedout/funding/repositories/growth_signal_repository.py
  - backend/src/linkedout/funding/repositories/startup_tracking_repository.py
  - backend/src/linkedout/funding/services/funding_round_service.py
  - backend/src/linkedout/funding/services/growth_signal_service.py
  - backend/src/linkedout/funding/services/startup_tracking_service.py
  - backend/src/linkedout/funding/controllers/funding_round_controller.py
  - backend/src/linkedout/funding/controllers/growth_signal_controller.py
  - backend/src/linkedout/funding/controllers/startup_tracking_controller.py
  - backend/src/linkedout/funding/schemas/
version: 1
last_verified: "2026-04-09"
---

# LinkedOut Funding (Startup Tracking)

**Created:** 2026-04-09 — Adapted from internal spec for OSS

## Intent

Track startup funding rounds, growth signals, and watchlist status for companies in the LinkedOut network. Three shared (no tenant/BU scoping) entities provide the data model for the startup intelligence pipeline. All three entities are linked to Company via company_id foreign key.

## Behaviors

### Entity Layer

- **FundingRound tracks investment rounds**: Each funding round has a company_id, round_type (Seed, Series A, etc.), announced_on date, amount_usd (BigInteger), lead_investors and all_investors (ARRAY(Text) columns), source_url, and confidence score (SmallInteger, 1-10, default 5). ID prefix is `fr`. A dedup unique constraint (`ix_fr_dedup`) prevents duplicate rounds per company_id+round_type+amount_usd. Additional indexes on company_id, announced_on, and round_type. Verify the dedup constraint is enforced.

- **GrowthSignal tracks company metrics**: Each signal has a company_id, signal_type (arr, mrr, revenue, headcount, etc.), signal_date (Date, required), value_numeric (BigInteger), value_text (Text), source_url, and confidence score (SmallInteger, 1-10, default 5). ID prefix is `gs`. A dedup unique constraint (`ix_gs_dedup`) prevents duplicates per company_id+signal_type+signal_date+source. Additional indexes on company_id+signal_date (composite) and signal_type. Verify the dedup constraint is enforced.

- **StartupTracking is a 1:1 extension of Company**: Each startup_tracking row has a unique company_id (enforced by both `unique=True` on the column and a unique index `ix_st_company`) with fields for watching flag (Boolean, default False), description (Text), vertical (String(100)), sub_category (String(100)), and denormalized funding aggregates: funding_stage (String(50)), total_raised_usd (BigInteger), last_funding_date (Date), round_count (Integer, default 0), plus ARR estimates: estimated_arr_usd (BigInteger), arr_signal_date (Date), arr_confidence (SmallInteger). ID prefix is `st`. A partial index on watching (`ix_st_watching`) filters to `watching = true`. Verify 1:1 relationship with Company.

- **All three are shared entities**: FundingRound, GrowthSignal, and StartupTracking inherit BaseEntity only (no TenantBuMixin). They are global data not scoped to any tenant. Verify no tenant_id or bu_id columns exist.

### CRUD Layer

- **Standard CRUD for all three entities**: Each entity has a full CRUD stack (repository, service, controller, schemas) with hand-written controllers following the shared-entity pattern. Each controller provides five endpoints: list (GET), create (POST, 201), get by ID (GET /{id}), update (PATCH /{id}), and delete (DELETE /{id}, 204). Verify all five endpoints exist per entity.

- **Shared entity routes at root level**: Controllers route at root-level paths without tenant/BU path parameters:
  - `/funding-rounds` (tag: `funding-rounds`)
  - `/growth-signals` (tag: `growth-signals`)
  - `/startup-trackings` (tag: `startup-trackings`)
  Verify endpoints are accessible at root-level URLs.

- **Read/write service separation**: Each controller creates separate read and write service dependencies using `DbSessionType.READ` and `DbSessionType.WRITE` respectively. List and get-by-ID use read sessions; create, update, and delete use write sessions.

- **Pagination**: List endpoints accept limit/offset query parameters and return `total`, `limit`, `offset`, and `page_count` in responses.

### Test Layer

- **Unit tests for all three entities**: Repository, service, and controller wiring tests exist under `backend/tests/linkedout/` for `funding_round/`, `growth_signal/`, and `startup_tracking/`. Each has `repositories/`, `services/`, and `controllers/` subdirectories. Verify test files exist for all three layers per entity.

- **No integration tests**: Integration tests do not currently exist for the funding module. Integration tests under `backend/tests/integration/linkedout/` cover other modules but not funding_round, growth_signal, or startup_tracking.

> Edge: StartupTracking denormalized fields (funding_stage, total_raised_usd, etc.) must be kept in sync with FundingRound data. No automatic sync exists — updates are manual or via pipeline.

## Decisions

### Shared entities over scoped entities — 2026-03-27
**Chose:** No tenant/BU scoping for funding data
**Over:** TenantBuMixin scoping
**Because:** Funding rounds and growth signals are public company data, not private to any user or tenant. Multiple users may track the same startup.

### Denormalized aggregates on StartupTracking — 2026-03-27
**Chose:** Denormalized funding_stage, total_raised_usd, round_count on startup_tracking
**Over:** Always joining funding_round for aggregates
**Because:** Dashboard and list views need these fields frequently. Denormalization avoids expensive aggregation queries. Staleness is acceptable since funding data changes infrequently.

### Hand-written controllers over CRUDRouterFactory — 2026-03-28
**Chose:** Hand-written controller functions
**Over:** CRUDRouterFactory
**Because:** Shared entities (no tenant/BU path params) do not fit the CRUDRouterFactory pattern which assumes scoped routes. Hand-written controllers give full control over route paths and response shapes.

## Not Included

- Automatic denormalization sync between FundingRound and StartupTracking
- Startup discovery pipeline (feeds into these tables but is separate)
- Funding data scraping or API integration
- Watchlist management UI endpoints beyond CRUD
- Integration tests (unit tests only)
- Bulk create endpoints (not present in current controllers)
