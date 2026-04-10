# Phase G.2: Frontend Owns Session Lifecycle

**Effort:** ~1 hour
**Dependencies:** Phase G.1 complete
**Working directory:** `<linkedout-fe>`
**Read first:** `<linkedout-fe>/CLAUDE.md`
**Shared context:** `./docs/execution/search-quality-v2/_shared_context.md`

---

## Objective

Make the frontend fully own session lifecycle decisions. "New Search" just resets local state — no backend archive call. Follow-up sends `session_id`. Remove all pivot detection handling.

## What to Do

### 1. Simplify "New Search" button

**File:** `<linkedout-fe>/src/components/search/SearchPageContent.tsx`

"New Search" button handler:
- Call `reset()` on the streaming hook
- Clear `activeSessionId`
- Do NOT call backend to archive the old session
- Backend doesn't enforce "one active session"

### 2. Follow-up sends session_id

Ensure the search request includes `session_id` when continuing a conversation. Backend reads turn history from that session.

### 3. First search omits session_id

When there's no active session, the request omits `session_id`. Backend creates a new session and returns the new `session_id` in the SSE `session` event.

### 4. Remove T10 pivot detection handling

Remove any frontend code that:
- Handles `start_new_search` from backend
- Swaps sessions mid-stream
- Detects pivot via SSE events

If backend sends a new `session` event, just update `sessionId` — but this shouldn't happen in the new flow except on first search.

## Verification

```bash
cd <linkedout-fe>

# Type check
npx tsc --noEmit

# Lint
npm run lint

# Tests
npm test -- --watchAll=false
```

## Transitions Affected (from search_conversation_flow spec)

| Transition | Change |
|---|---|
| T7 (Undo/Remove Filter) | No more `filter_results`/`start_new_search` tools. LLM re-queries. Frontend flow unchanged — still a follow-up. |
| T10 (Pivot Detection) | **REMOVED.** User clicks "New Search" explicitly. |
| T11 (New Search) | Simplified: just `reset()` + clear session ID. No backend archive call. |
