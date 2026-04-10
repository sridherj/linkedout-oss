# Phase 3 Execution Plan — Manifest

**Goal:** linkedin-ai-production
**Phase:** 3 — Import Pipeline + User-Triggered Enrichment
**Source plan:** `.taskos/phase3_detailed_plan.ai.md`
**Created:** 2026-03-28
**Estimated total effort:** ~12-16h across 4 sub-phases

## Sub-Phases

| # | Name | Plan Sections | Est. Effort | Depends On |
|---|------|---------------|-------------|------------|
| 1 | Converter Framework + All Converters | 3.1.1, 3.1.2, 3.1.3, 3.1.4 | 3-4h | — |
| 2 | Import Pipeline (Endpoint + Dedup + Merge) | 3.2.1, 3.2.2, 3.2.3, 3.2.4 | 4-5h | SP-1 |
| 3 | Enrichment Pipeline (Trigger + Worker + Apify + Post-Enrichment) | 3.3.1, 3.3.2, 3.3.3, 3.3.4 | 4-5h | SP-2 |
| 4 | BYOK Key Management + Stats + Import History | 3.4.1, 3.5.1, 3.5.2 | 2-3h | SP-3 |

## Execution Flow (DAG)

```
SP-1 (Converter Framework + All Converters)
  |
  v
SP-2 (Import Pipeline: Endpoint + Dedup + Merge)
  |
  v
SP-3 (Enrichment Pipeline: Trigger + Worker + Apify Client + Post-Enrichment)
  |
  v
SP-4 (BYOK + Stats + Import History)
```

## Parallelization Rules

- **SP-1 through SP-4** are strictly sequential — each depends on the previous
- **Within SP-1:** 3.1.2 (LinkedIn CSV), 3.1.3 (Google converters x3), and 3.1.4 (Registry) can run in parallel once 3.1.1 (framework) is done
- **Within SP-2:** 3.2.2 (normalization utils) can be built in parallel with 3.2.1 (import endpoint)
- **Within SP-3:** 3.3.3 (Apify client) can be built in parallel with 3.3.1 (trigger endpoint)
- **Within SP-4:** 3.4.1 (BYOK), 3.5.1 (stats), and 3.5.2 (import history) are independent and can run in parallel

## Cross-Phase Reconciliation (Applied)

These decisions from the plan review and cross-phase analysis are baked into the sub-phase instructions:

| ID | Decision | Impact |
|---|----------|--------|
| C1 | URL normalization lives in `shared/utils/` | SP-2 imports from `shared/utils/` instead of creating local duplicate |
| C2 | `connection.sources` Text→ARRAY migration moved to Phase 2 | Original Sub-Phase 3.0 removed — migration already applied |
| C4 | Enrichment cost estimate computed client-side | No backend estimate endpoint needed in SP-4 |
| C11 | Shared `CompanyMatcher` from Phase 2 | SP-3 reuses `CompanyMatcher` instead of defining its own |

## Key Artifacts

- **SP-1 output:** `src/linkedout/import_pipeline/converters/` — base, registry, 4 converters + unit tests
- **SP-2 output:** `src/linkedout/import_pipeline/` — service, controller, dedup, merge, normalize + unit & integration tests
- **SP-3 output:** `src/linkedout/enrichment_pipeline/` — controller, tasks, apify_client, post_enrichment + unit & integration tests
- **SP-4 output:** BYOK key management endpoints, enrichment stats endpoint, import history endpoint + tests

## New Dependencies

```toml
# pyproject.toml additions (install during SP-1)
rapidfuzz = ">=3.0"           # Fuzzy name matching for dedup (SP-2)
phonenumbers = ">=8.13"       # Phone normalization to E.164 (SP-1)
cryptography = ">=42.0"       # Fernet for BYOK key encryption (SP-4)
python-multipart = ">=0.0.9"  # File upload support for FastAPI (SP-2)
```

## Estimated Total Effort

~12-16 hours across 4 sub-phases (4 sessions).
