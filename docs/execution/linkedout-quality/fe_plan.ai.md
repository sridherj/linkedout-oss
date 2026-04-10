# Frontend Execution Plan — LinkedOut Quality

## Goal
Implement the 4 frontend features that were designed in Phase 1+2 but not built: session management, conversation UI, profile detail panel, and enhanced result cards.

## Important: File Resolution
- **Frontend code lives at:** `<linkedout-fe>`
- **Backend code and specs live at:** `.` (also accessible via `.`)
- If a referenced file is not found at one location, check `.`, `.`, or `<prior-project>`
- **Leverage the `/ui-ux-pro-max` skill** for all UI implementation work
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md` — read before any visual work

## DAG (Build Order)
```
FE4 (result cards) -> FE1 (session switcher) -> FE2 (conversation thread)
FE4 (result cards) -> FE3 (profile slide-over)
```

- FE4 goes first: result cards are the foundation — every other feature builds on or interacts with cards
- FE1 before FE2: session management must exist before conversation thread can persist turns
- FE3 is independent of FE1/FE2 (only depends on card click handler from FE4)
- FE3 can run in parallel with FE1

## Sub-Phases

| ID | File | Summary | Depends On |
|----|------|---------|------------|
| FE4 | `fe4_result_cards.md` | Enhanced result cards with highlighted_attributes chips, color tiers, unenriched state | — |
| FE1 | `fe1_session_switcher.md` | Session switcher dropdown, "New Search" button, session resume on page load | FE4 |
| FE3 | `fe3_profile_slideover.md` | Profile slide-over panel with 4 tabs (Overview, Experience, Affinity, Ask) | FE4 |
| FE2 | `fe2_conversation_thread.md` | Conversation thread, follow-up bar, hint chips, excluded banner | FE1 |

## Shared Context
- Backend APIs are all implemented and tested (345 unit tests passing)
- Backend specs: `./docs/specs/linkedout_intelligence.collab.md` (v7), `./docs/specs/search_sessions.collab.md` (v2)
- Backend contracts: `./src/linkedout/intelligence/contracts.py`
- HTML mockups exist at `<linkedout-fe>/docs/design/` for all 4 features
- Existing frontend uses: Next.js App Router, TanStack React Query, Tailwind, SSE streaming search, `apiFetch` client
