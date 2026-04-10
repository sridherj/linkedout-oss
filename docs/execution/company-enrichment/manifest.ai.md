# Company Enrichment Execution Plan — Manifest

**Goal:** linkedin-ai-production
**Phase:** 2 — Company Enrichment (PDL + Wikidata Waterfall)
**Source plan:** `docs/plan/linkedin-ai-production/2026-03-28-company-enrichment-port.md`
**Created:** 2026-03-28
**Estimated total effort:** ~8-10h across 4 sub-phases
**Target directory:** `./`

## Sub-Phases

| # | Name | Plan Steps | Est. Effort | Depends On |
|---|------|-----------|-------------|------------|
| 1 | Schema Extension | SP1 — Add pdl_id/wikidata_id columns | 1h | — |
| 2 | Utility Functions | SP2 — company_utils + wikidata_utils | 2-3h | — |
| 3 | Enrichment Script | SP3 — PDL scan + Wikidata gap-fill | 4-5h | SP-1, SP-2 |
| 4 | CLI Wiring + Gate | SP4 — CLI command, spec updates, E2E verification | 1h | SP-3 |

## Execution Flow (DAG)

```
SP-1 (Schema Extension) ──────┐
                               ├──► SP-3 (Enrichment Script) ──► SP-4 (CLI Wiring + Gate)
SP-2 (Utility Functions) ─────┘
```

## Parallelization Rules

- **SP-1 and SP-2** can run in parallel (no shared files, no dependency between them)
- **SP-3** requires both SP-1 and SP-2 (uses pdl_id/wikidata_id columns from SP-1, uses utility functions from SP-2)
- **SP-4** requires SP-3 (wires CLI to the enrichment script, runs E2E verification)

## Critical Path

```
SP-2 → SP-3 → SP-4
```
SP-1 (Schema Extension) is off the critical path — shorter than SP-2 and runs in parallel.

## Key Artifacts

- **SP-1 output:** Alembic migration adding `pdl_id` and `wikidata_id` to `company` table; updated `CompanyEntity`; data model spec update
- **SP-2 output:** `src/dev_tools/company_utils.py`, `src/dev_tools/wikidata_utils.py`, unit tests, live service test, `cleanco` dependency
- **SP-3 output:** `src/dev_tools/enrich_companies.py` with full PDL + Wikidata waterfall
- **SP-4 output:** `rcv2 db enrich-companies` CLI command, spec updates, integration tests, E2E verification

## Cross-Phase Execution Order

This is **Phase 2 of 3** in the linkedin-ai-production goal.

```
Phase 1: Classify Roles ──► V1 Pipeline GATE ──► Phase 2: Company Enrichment ──► Phase 3: Affinity V2
                                                         ^^^^ THIS PLAN
```

**Prerequisite gate:** Phase 1 Sub-phase 4 (V1 Pipeline) must have exited 0 for all three commands (`classify-roles`, `backfill-seniority`, `compute-affinity`).

**Phase 2 GATE:** SP-4 is the gate for this phase. The enrichment must complete successfully and coverage checks must show improvement before Phase 3 begins.

## Resolved Design Questions

| Question | Resolution |
|----------|-----------|
| `size_tier` values (4 vs 5 tiers) | Use 5 tiers: `tiny, small, mid, large, enterprise` |
| Transaction strategy (single vs dual) | Two transactions: PDL commits first, then Wikidata separately |
| PDL file location | Required `--pdl-file` CLI flag, no default path |
| pandas dependency | Use `csv.DictReader` + `itertools.islice` — no pandas |

## Important Context for All Sub-Phases

- **Code directory:** `./`
- **DB session pattern:** `db_session_manager.get_session(DbSessionType.WRITE)` (same as `classify_roles.py`)
- **SQL style:** `sqlalchemy.text()` with `:param` named parameters (not psycopg `%s`)
- **Company IDs:** nanoid strings with `co_` prefix (not integers)
- **COALESCE semantics:** Enrichment never overwrites existing data
- **Idempotency:** `enrichment_sources` array check prevents duplicate enrichment runs
- **Reference scripts (old):** `second-brain/agents/startup_enrichment/enrich_companies.py`, `company_utils.py`, `wikidata_utils.py`

## Estimated Total Effort

~8-10 hours across 4 sub-phases. SP-1 and SP-2 can run in parallel (~3h wall time). SP-3 is the heaviest (~4-5h). SP-4 is lightweight wiring (~1h).
