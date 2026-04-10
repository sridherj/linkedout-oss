# Sub-Phase 2: CRUD Entities

**Goal:** linkedin-ai-production
**Phase:** 2b — Startup Pipeline Compatibility
**Depends on:** SP-1 (Pipeline Code Audit — for column validation)
**Estimated effort:** 6-8h
**Source plan steps:** Steps 2a, 2b, 2c

---

## Objective

Create three new shared entities with full CRUD stacks (Entity → Repo → Service → Controller) in a new `src/linkedout/funding/` module. These entities support the startup pipeline's data model in LinkedOut.

## Context

All three entities are **shared** (no TenantBuMixin) because the pipeline is a global batch job that doesn't know about tenants. They all live in the same module since they're all company intelligence data.

Use the `crud-orchestrator-agent` for each entity. The three can run in parallel (no inter-dependencies).

---

## Entity Definitions

### 2a: FundingRoundEntity (prefix: `fr`)

**Module:** `src/linkedout/funding/`

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT (nanoid, `fr_xxx`) | From BaseEntity |
| `company_id` | String, NOT NULL | FK to `company.id` |
| `round_type` | String(50), NOT NULL | Seed, Series A, Series B, etc. |
| `announced_on` | Date, nullable | Date the round was announced |
| `amount_usd` | BigInteger, nullable | Round amount in whole USD |
| `lead_investors` | ARRAY(Text), nullable | Lead investor names |
| `all_investors` | ARRAY(Text), nullable | All investor names |
| `source_url` | String(500), nullable | URL of source article |
| `confidence` | SmallInteger, default=5 | Confidence score 1-10 |
| `source` | String | Inherited from BaseEntity — data origin |
| `notes` | Text | Inherited from BaseEntity |
| + BaseEntity columns | | created_at, updated_at, deleted_at, etc. |

**Indexes:**
- `ix_fr_company` on `company_id`
- `ix_fr_announced` on `announced_on`
- `ix_fr_round_type` on `round_type`
- `ix_fr_dedup` UNIQUE on `(company_id, round_type, amount_usd)` — dedup key

**Sort enum:** `FundingRoundSortEnum` — `announced_on`, `amount_usd`, `created_at`

### 2b: GrowthSignalEntity (prefix: `gs`)

**Module:** `src/linkedout/funding/` (same module)

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT (nanoid, `gs_xxx`) | From BaseEntity |
| `company_id` | String, NOT NULL | FK to `company.id` |
| `signal_type` | String(50), NOT NULL | arr, mrr, revenue, headcount, etc. |
| `signal_date` | Date, NOT NULL | Date signal was observed |
| `value_numeric` | BigInteger, nullable | Numeric value (USD, count) |
| `value_text` | Text, nullable | Human-readable description |
| `source_url` | String(500), nullable | URL where signal was found |
| `confidence` | SmallInteger, default=5 | Confidence score 1-10 |
| `source` | String | Inherited from BaseEntity |
| + BaseEntity columns | | |

**Indexes:**
- `ix_gs_company_date` on `(company_id, signal_date)`
- `ix_gs_signal_type` on `signal_type`
- `ix_gs_dedup` UNIQUE on `(company_id, signal_type, signal_date, source)` — dedup key

**Sort enum:** `GrowthSignalSortEnum` — `signal_date`, `signal_type`, `created_at`

### 2c: StartupTrackingEntity (prefix: `st`)

**Module:** `src/linkedout/funding/` (same module)

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT (nanoid, `st_xxx`) | From BaseEntity |
| `company_id` | String, NOT NULL, UNIQUE | 1:1 FK to `company.id` |
| `watching` | Boolean, default=False | Pipeline filter flag |
| `description` | Text, nullable | Startup description |
| `vertical` | String(100), nullable | AI Agents, Voice AI, Dev Tools, etc. |
| `sub_category` | String(100), nullable | Finer classification |
| `funding_stage` | String(50), nullable | Denormalized from funding_rounds |
| `total_raised_usd` | BigInteger, nullable | Denormalized sum |
| `last_funding_date` | Date, nullable | Denormalized latest |
| `round_count` | Integer, default=0 | Denormalized count |
| `estimated_arr_usd` | BigInteger, nullable | Revenue estimate |
| `arr_signal_date` | Date, nullable | When ARR was estimated |
| `arr_confidence` | SmallInteger, nullable | Confidence 1-10 |
| `source` | String | Inherited from BaseEntity |
| + BaseEntity columns | | |

**Indexes:**
- `ix_st_company` UNIQUE on `company_id` (1:1 relationship)
- `ix_st_watching` on `watching` WHERE `watching = true` (partial index for pipeline queries)
- `ix_st_vertical` on `vertical`

**Sort enum:** `StartupTrackingSortEnum` — `total_raised_usd`, `last_funding_date`, `created_at`

---

## Execution

1. Use `crud-orchestrator-agent` for FundingRound
2. Use `crud-orchestrator-agent` for GrowthSignal
3. Use `crud-orchestrator-agent` for StartupTracking
4. Order doesn't matter — can parallelize all three

## Completion Criteria

- [ ] All three entity files exist with correct columns and indexes
- [ ] All three repo/service/controller stacks exist
- [ ] Unit tests pass: `pytest src/linkedout/funding/ -v`
- [ ] Entities registered in Alembic `env.py`
- [ ] Module `__init__.py` properly exports all entities

## Verification

```bash
pytest src/linkedout/funding/ -v
# All tests green
```
