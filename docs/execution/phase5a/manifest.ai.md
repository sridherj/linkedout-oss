# Phase 5a Execution Plan — Manifest

**Goal:** linkedin-ai-production
**Phase:** 5a — Search UI (Frontend)
**Source plan:** `.taskos/phase5a_detailed_plan.ai.md`
**Created:** 2026-03-28
**Estimated total effort:** ~12h across 6 sub-phases
**Target directory:** `<linkedout-fe>/`
**Backend directory:** `./`

## Sub-Phases

| # | Name | Plan Steps | Est. Effort | Depends On |
|---|------|-----------|-------------|------------|
| 1 | Scaffold + Layout + Search Bar | 1, 2, 3 | 1.75h | — |
| 2 | SSE Streaming + Thinking State | 4, 5 | 1.5h | SP-1 |
| 3 | Profile Cards + Results + Facets | 6, 7, 8 | 3h | SP-2 |
| 4 | History + Import UI | 9, 10 | 1.75h | SP-1 |
| 5 | Enrichment + Export | 11, 12 | 1h | SP-3, SP-4 |
| 6 | Mobile Pass + Error States + Testing | 13, 14, 15 | 3.5h | SP-1 through SP-5 |

## Execution Flow (DAG)

```
SP-1 (Scaffold + Layout + Search Bar)
  │
  ├────► SP-2 (SSE Streaming + Thinking State) ────► SP-3 (Profile Cards + Results + Facets)
  │                                                         │
  └────► SP-4 (History + Import UI) ────────────────────────┤
                                                            ↓
                                                    SP-5 (Enrichment + Export)
                                                            ↓
                                                    SP-6 (Mobile + Errors + Testing)
```

## Parallelization Rules

- **SP-2 and SP-4** can run in parallel (both depend only on SP-1; no shared files)
- **SP-3** requires SP-2 (profile cards consume streaming hook output)
- **SP-5** requires SP-3 (enrichment integrates with profile cards) and SP-4 (import context needed)
- **SP-6** requires all prior sub-phases (mobile pass, error states, and tests span everything)

## Critical Path

```
SP-1 → SP-2 → SP-3 → SP-5 → SP-6
```
SP-4 (History + Import) is off the critical path and can run in parallel with SP-2/SP-3.

## Key Artifacts

- **SP-1 output:** Project scaffold, `layout.tsx`, `AppShell.tsx`, `SearchBar.tsx`, `api-client.ts`, design tokens, vitest config
- **SP-2 output:** `useStreamingSearch.ts`, `types/search.ts`, `api/search/stream/route.ts`, `ThinkingState.tsx`, backend test stub
- **SP-3 output:** `ProfileCard.tsx`, `ProfileCardUnenriched.tsx`, `InitialsAvatar.tsx`, `ResultsList.tsx`, `Pagination.tsx`, `FacetPanel.tsx`, `api/images/[identifier]/route.ts`
- **SP-4 output:** `history/page.tsx`, `SearchHistoryDialog.tsx`, `QuerySuggestions.tsx`, `import/page.tsx`, `FileUploadZone.tsx`, `ImportProgress.tsx`, `ImportHistory.tsx`
- **SP-5 output:** `EnrichmentPanel.tsx`, `EnrichmentProgress.tsx`, `ExportMenu.tsx`
- **SP-6 output:** Mobile responsive pass across all components, error state components, unit/component/hook/e2e tests

## Cross-Phase Reconciliation Items

| ID | Item | Affects |
|----|------|---------|
| C4 | Enrichment cost computed client-side (no backend endpoint) | SP-5 |
| C6 | Save search uses PATCH on search-histories/{id} (not separate POST) | SP-4 |
| C13 | Phase 4.5 Design System complete — gate satisfied | SP-1 |

## Important Context for All Sub-Phases

- **Code directory:** `<linkedout-fe>/` (symlinked at `./linkedout-fe`)
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md` — read before any UI work
- **Backend:** `./` — FastAPI backend for stub endpoints and API reference
- **No Zustand** — all state via URL params, TanStack Query, and React hooks
- **No Vercel AI SDK** — native fetch + ReadableStream for SSE
- **No dark mode** — skip dark mode cleanup, just apply Berry Fields Soft tokens
- **Backend result cap:** 100 results max via SSE; client-side pagination over this set
- **Profile images:** served from local dir via Next.js API route; initials-avatar fallback

## Estimated Total Effort

~12 hours across 6 sub-phases. SP-1 through SP-3 form the core search experience (~6.25h). SP-4 and SP-5 add secondary features (~2.75h). SP-6 adds polish and quality (~3.5h).
