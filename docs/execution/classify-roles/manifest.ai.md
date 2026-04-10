# Phase 1 Execution Plan — Classify Roles: Manifest

**Goal:** linkedin-ai-production
**Source plan:** 2026-03-28-classify-roles-port-and-wiring.md
**Created:** 2026-03-28
**Output directory:** .

## Sub-Phases

| # | File | Description | Dependencies | Can Parallel With |
|---|------|-------------|-------------|-------------------|
| 1 | sub-phase-1-pure-classification.ai.md | Pure classification functions (classify_seniority, classify_function) + 75 parametrized tests | None | Nothing (first wave) |
| 2 | sub-phase-2-db-operations.ai.md | DB operations: title extraction, in-memory classification, role_alias upsert, experience/crawled_profile bulk updates | Sub-Phase 1 | Nothing (sequential) |
| 3 | sub-phase-3-cli-wiring.ai.md | CLI command wiring (`rcv2 db classify-roles`), spec update, end-to-end verification | Sub-Phase 2 | Nothing (sequential) |
| 4 | sub-phase-4-v1-pipeline-gate.ai.md | V1 Pipeline GATE: run classify-roles → backfill-seniority → compute-affinity, validate all exit 0 | Sub-Phase 3 | Nothing (gate — blocks Phase 2 and Phase 3) |

## Execution Flow (DAG)

```
Sub-Phase 1 (Pure Classification)
       │
       ▼
Sub-Phase 2 (DB Operations)
       │
       ▼
Sub-Phase 3 (CLI Wiring)
       │
       ▼
Sub-Phase 4 (V1 Pipeline GATE)
       │
       ▼
Phase 2 + Phase 3 unblocked
```

## Parallelization Rules

- **Fully sequential** — no parallelism possible. Each sub-phase depends on the previous.
- Sub-Phase 4 is a **GATE** — Phase 2 (Company Enrichment) and Phase 3 (Affinity V2) cannot start until all three pipeline commands exit 0.

## Critical Path

Sub-Phase 1 → Sub-Phase 2 → Sub-Phase 3 → Sub-Phase 4

## Design Review Flags

| Sub-phase | Flag | Action |
|-----------|------|--------|
| SP2 | Raw SQL INSERT must include all BaseEntity fields (id, is_active, version, created_at, updated_at) | Ensure INSERT template includes all required columns |
| SP2 | Old script uses psycopg COPY protocol; must adapt to sqlalchemy.text() batch INSERT | Use parameterized batch INSERT instead of COPY |
| SP2 | `has_enriched_data = TRUE` filter in crawled_profile update | Confirmed: field exists in entity |
| SP3 | CLI spec version bump required when adding new command | Include `/taskos-update-spec` delegation |

## Estimated Total Effort

| Sub-Phase | Estimated Time |
|-----------|---------------|
| 1 | ~2 hours |
| 2 | ~3-4 hours |
| 3 | ~1 hour |
| 4 | ~30 minutes |
| **Total** | **~6.5-7.5 hours** |
