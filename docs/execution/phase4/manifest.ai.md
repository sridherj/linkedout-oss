# Phase 4 Execution Plan — Manifest

**Goal:** linkedin-ai-production
**Phase:** 4 — Intelligence: Search Engine + Affinity Scoring
**Source plan:** `.taskos/phase4_detailed_plan.ai.md`
**Created:** 2026-03-28
**Estimated total effort:** ~10-14h across 6 sub-phases

## Sub-Phases

| # | Name | Plan Sections | Est. Effort | Depends On |
|---|------|---------------|-------------|------------|
| 1 | Query Tools + Schema Context | 4.1, 4.4 | 2-3h | — |
| 2 | Affinity Scoring Engine | 4.5 | 2-3h | — |
| 3 | SearchAgent Core | 4.2 | 2-3h | SP-1 |
| 4 | SSE Endpoint + Why This Person | 4.3, 4.6 | 2-3h | SP-3 |
| 5 | Supplementary Features | 4.7, 4.8, 4.9 | 2-3h | SP-1, SP-4 |
| 6 | Comprehensive Testing | 4.10 | 2-3h | SP-1 through SP-5 |

## Execution Flow (DAG)

```
SP-1 (Query Tools) ────► SP-3 (SearchAgent) ────► SP-4 (SSE + Explainer)
                                                         ↓
SP-2 (Affinity) ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─► SP-5 (Supplementary)
                                                         ↓
                                                   SP-6 (Testing)
```

## Parallelization Rules

- **SP-1 and SP-2** can run in parallel (no shared files or dependencies)
- **SP-3** requires SP-1 (tools must exist before SearchAgent can use them)
- **SP-4** requires SP-3 (endpoint wraps SearchAgent; explainer integrates into agent flow)
- **SP-5** requires SP-1 (vector tool for People Like X) and SP-4 (endpoint pattern for controllers)
- **SP-6** requires all prior sub-phases (comprehensive test suite spans all components)

## Critical Path

```
SP-1 → SP-3 → SP-4 → SP-5 → SP-6
```
SP-2 (Affinity) is off the critical path and can run any time before SP-6.

## Key Artifacts

- **SP-1 output:** `src/linkedout/intelligence/tools/sql_tool.py`, `vector_tool.py`, `schema_context.py` — the two query tools and schema context builder
- **SP-2 output:** `src/linkedout/intelligence/scoring/affinity_scorer.py` — affinity computation + Dunbar tiers
- **SP-3 output:** `src/linkedout/intelligence/agents/search_agent.py`, `contracts.py`, `prompts/search_system.md` — the agentic query engine
- **SP-4 output:** `src/linkedout/intelligence/controllers/search_controller.py`, `explainer/why_this_person.py` — SSE endpoint + "Why This Person"
- **SP-5 output:** "People Like X" and "Warm Intro Paths" endpoints added to search controller, search history integration
- **SP-6 output:** Unit tests, integration tests (PostgreSQL), live LLM tests across all Phase 4 components

## Cross-Phase Reconciliation Items

| ID | Item | Affects |
|----|------|---------|
| C1 | `EmbeddingClient` must exist in `LLMClient` (Phase 2 dependency) | SP-1 vector tool |
| C2 | `BaseAgent` must exist (Phase 3 or earlier) | SP-3 SearchAgent |
| C3 | `SearchHistoryService` CRUD must exist | SP-5 history integration |
| C4 | pgvector extension must be enabled in PostgreSQL | SP-1 vector tool, SP-6 integration tests |

## Estimated Total Effort

~10-14 hours across 6 sub-phases. SP-1 through SP-4 form the core experience (~8-10h). SP-5 and SP-6 add supplementary features and test coverage (~4-6h).
