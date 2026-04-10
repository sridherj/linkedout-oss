# Phase 3 Execution Plan — Manifest

**Goal:** linkedin-ai-production
**Phase:** 3 — Affinity V2 Enhancements
**Source plan:** `docs/plan/linkedin-ai-production/2026-03-28-affinity-v2-enhancements.md`
**Created:** 2026-03-28
**Estimated total effort:** ~4-5 sessions (~10-14h) across 5 sub-phases

## Sub-Phases

| # | Name | Plan Section | Est. Effort | Depends On |
|---|------|-------------|-------------|------------|
| SP-1 | Schema Migration | Sub-phase 1 | 0.5 session (~1h) | — |
| SP-2 | Career Overlap V2 | Sub-phase 2 | 1.5 sessions (~3-4h) | SP-1 |
| SP-3a | External Contact Signal | Sub-phase 3a | 1 session (~2-3h) | SP-1 |
| SP-3b | Embedding Similarity | Sub-phase 3b | 1 session (~2-3h) | SP-1 |
| SP-4 | V2 Weight Revision | Sub-phase 4 | 1 session (~2h) | SP-2, SP-3a, SP-3b |

## Execution Flow (DAG)

```
SP-1 (Schema Migration)
  ↓
  ├── SP-2 (Career Overlap V2)  ──┐
  ├── SP-3a (External Contact)  ──┼── SP-4 (V2 Weights + Integration)
  └── SP-3b (Embedding Sim)    ──┘
```

## Parallelization Rules

- **SP-2, SP-3a, SP-3b** can run in parallel after SP-1 completes
- **SP-4** requires SP-2, SP-3a, and SP-3b to all complete
- SP-1 is sequential (must run first)

## Cross-Phase Context

This is **Phase 3 of 3**. Runs after Phase 2 (Company Enrichment) completes.

```
Phase 1: Classify Roles ──> V1 Pipeline GATE ──> Phase 2: Company Enrichment ──> Phase 3: Affinity V2
                                                                                       ^^^^ THIS PHASE
```

**Prerequisite gates:** Phase 1 Sub-phase 4 (V1 Pipeline Gate) passed. Phase 2 completed successfully.

## Key Artifacts

- **SP-1 output:** Alembic migration adding `affinity_external_contact`, `affinity_embedding_similarity` to `connection` and `source_label` to `contact_source`. Updated `ConnectionEntity` and `ContactSourceEntity`.
- **SP-2 output:** Rewritten `_compute_career_overlap()` with `size_factor()` and `overlap_months()` pure functions; updated batch fetch methods; new and updated unit tests.
- **SP-3a output:** New `_compute_external_contact_score()` and `_batch_fetch_external_contacts()`; unit + integration tests.
- **SP-3b output:** New `_compute_embedding_similarity()` with pgvector `<=>` DB-side computation; unit + integration tests.
- **SP-4 output:** V2 weight constants, updated `_compute_affinity()` with 5-signal formula, `AFFINITY_VERSION = 2`, spec updates, all tests green.

## Design Review Flags

| Sub-phase | Flag | Resolution |
|-----------|------|------------|
| SP-2 | `log2` inverse for dampening | Use `1.0 / log2((employee_count or 500) + 2)` matching old script |
| SP-3a | Phone vs email thresholds | Phone=1.0, email=0.7, no stacking (RESOLVED) |
| SP-3b | Spec says 768-dim but entity has 1536 | Corrected to 1536-dim text-embedding-3-small (RESOLVED) |
| SP-4 | V2 weights are initial values | Ship as constants, eyeball session after first run (RESOLVED) |

## Key Risks

| Risk | Mitigation |
|------|------------|
| `estimated_employee_count` NULL for most companies | Phase 2 enrichment runs first; fallback to size_factor(500) |
| `contact_source` has 0 rows | Expected; signal produces 0.0; forward-looking |
| Experiences lack dates | `overlap_months` returns 0.0; check data coverage |
| V2 scores differ from V1 | `affinity_version` column distinguishes; Dunbar tiers are rank-based |
