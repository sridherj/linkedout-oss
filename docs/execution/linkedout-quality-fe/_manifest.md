# Execution Manifest: LinkedOut Quality Frontend

## How to Execute

Each sub-phase runs in a **separate Claude context**. For each sub-phase:
1. Start a new Claude session
2. Tell Claude: "Read `./docs/execution/linkedout-quality-fe/_shared_context.md` then execute `./docs/execution/linkedout-quality-fe/spN_name/plan.md`"
3. After completion, update the Status column below

**Important:** Use the `/ui-ux-pro-max` skill for all UI implementation work (component creation, styling).

## Sub-Phase Overview

| # | Sub-phase | Directory/File | Depends On | Status | Notes |
|---|-----------|---------------|-----------|--------|-------|
| 0 | Backend: Wire run_turn() into SSE | `sp0_backend_conversation_wiring/` | -- | Not Started | **Backend repo** (`.`), prerequisite for SP3 |
| 1 | Result Cards + Highlight Chips | `sp1_result_cards/` | -- | Not Started | Foundation -- all other FE SPs depend on this |
| 2a | Session Switcher & Resume | `sp2a_session_switcher/` | 1 | Not Started | |
| 2b | Profile Slide-Over Panel | `sp2b_profile_slideover/` | 2a | Not Started | |
| 3 | Conversation Thread & Follow-Up | `sp3_conversation_thread/` | 2b, 0 | Not Started | Requires SP0 backend wiring |

Status: Not Started -> In Progress -> Done -> Verified -> Skipped

## Dependency Graph (UPDATED — fully sequential + backend prereq)

```
SP0 (Backend: wire run_turn) ──────────────────────┐
                                                    v
SP1 (Result Cards) → SP2a (Session Switcher) → SP2b (Profile Slide-Over) → SP3 (Conversation Thread)
```

SP0 can run in parallel with SP1/SP2a/SP2b (different repo). SP3 requires BOTH SP2b and SP0 to be complete.

## Execution Order

**Backend (separate orchestration against `.`):**
0. **SP0:** Wire run_turn() into SSE controller

**Frontend (sequential against `<linkedout-fe>`):**
1. **SP1:** Result Cards + Highlight Chips
2. **SP2a:** Session Switcher & Resume
3. **SP2b:** Profile Slide-Over Panel
4. **SP3:** Conversation Thread & Follow-Up (requires SP0 complete)

## Key Files Modified Per Sub-Phase

| File | SP1 | SP2a | SP2b | SP3 |
|------|-----|------|------|-----|
| `types/search.ts` | M | | | |
| `types/session.ts` | | C | | |
| `types/profile-detail.ts` | | | C | |
| `types/conversation.ts` | | | | C |
| `profile/HighlightChip.tsx` | C | | | |
| `profile/ProfileCard.tsx` | M | | | |
| `profile/ProfileCardUnenriched.tsx` | M | | | |
| `profile/ProfileCardSkeleton.tsx` | M | | | |
| `profile/ProfileSlideOver.tsx` | | | C | |
| `profile/tabs/*.tsx` | | | C | |
| `search/SearchBar.tsx` | | M | | |
| `search/SearchPageContent.tsx` | M | M | M | M |
| `search/ResultsList.tsx` | M | | M | M |
| `search/SessionSwitcher.tsx` | | C | | |
| `search/ActiveSessionLabel.tsx` | | C | | |
| `search/ConversationThread.tsx` | | | | C |
| `search/FollowUpBar.tsx` | | | | C |
| `search/HintChips.tsx` | | | | C |
| `search/ExcludedBanner.tsx` | | | | C |
| `hooks/useStreamingSearch.ts` | M | M | | M |
| `hooks/useSession.ts` | | C | | |
| `hooks/useProfileDetail.ts` | | | C | |
| `api/search/stream/route.ts` | | M | | |

C = Create, M = Modify

## Progress Log

(Update after each sub-phase)
