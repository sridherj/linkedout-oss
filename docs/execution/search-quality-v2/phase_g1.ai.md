# Phase G.1: Session Resume via Turn History (Frontend)

**Effort:** 1 session
**Dependencies:** Phase D.4 complete (backend API must be stable)
**Working directory:** `<linkedout-fe>`
**Read first:** `<linkedout-fe>/CLAUDE.md`
**Shared context:** `./docs/execution/search-quality-v2/_shared_context.md`

---

## Objective

Update the frontend to resume sessions by fetching turn history from the new `search_turn` API instead of reading `result_snapshot` and `conversation_state` from the session entity. Remove `ExcludedBanner` and all exclusion state handling.

## What to Do

### 1. Read current frontend implementation

Read these files to understand what exists:
- `<linkedout-fe>/src/hooks/useStreamingSearch.ts`
- `<linkedout-fe>/src/hooks/useSession.ts`
- `<linkedout-fe>/src/components/search/SearchPageContent.tsx`
- `<linkedout-fe>/src/types/conversation.ts`
- `<linkedout-fe>/src/types/session.ts`

### 2. Update `useSession.ts`

- Fetch turn history from new endpoint: `GET /search-sessions/{id}/turns`
- Returns turns ordered by `turn_number` with `results` and `user_query` per turn
- On resume: `restoreResults(latestTurn.results)` and `restoreTurns(turns)`
- Turns come structured from the API — no parsing needed

### 3. Update `useStreamingSearch.ts`

- Remove `exclusionState` from state
- Remove `exclusion_state` parsing from SSE `conversation_state` event handler
- Session resume now reads turns from new API (via `useSession.ts`)

### 4. Update `SearchPageContent.tsx`

- Remove `ExcludedBanner` import and usage
- Replace all `latestSession.result_snapshot` reads with turn-based restore
- Remove `parseConversationTurns(conversation_state.messages)` — turns come from API

### 5. Delete `ExcludedBanner.tsx`

**DELETE:** `<linkedout-fe>/src/components/search/ExcludedBanner.tsx`

No more exclusion state from backend.

### 6. Update types

**File:** `<linkedout-fe>/src/types/conversation.ts`
- Remove `ExclusionState` type

**File:** `<linkedout-fe>/src/types/session.ts`
- Remove `result_snapshot`, `conversation_state`, `excluded_ids` from session type
- Add `turns` endpoint reference or turn type

### 7. Update or delete parseConversationTurns

**File:** `<linkedout-fe>/src/lib/parseConversationTurns.ts`

Turns come structured from API — this parser may no longer be needed. Rewrite or delete depending on whether any other code uses it.

## Verification

```bash
cd <linkedout-fe>

# Type check
npx tsc --noEmit

# Lint
npm run lint

# Tests (will update in G.3, but verify nothing crashes)
npm test -- --watchAll=false
```

## SSE Protocol Change

The `conversation_state` SSE event payload changes:
- **Before:** `{result_summary_chips, suggested_actions, exclusion_state, result_metadata, facets}`
- **After:** `{result_summary_chips, suggested_actions, result_metadata, facets}` — `exclusion_state` removed
