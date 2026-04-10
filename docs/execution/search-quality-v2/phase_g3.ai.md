# Phase G.3: Frontend Test Updates

**Effort:** ~1 hour
**Dependencies:** Phase G.2 complete
**Working directory:** `<linkedout-fe>`
**Read first:** `<linkedout-fe>/CLAUDE.md`
**Shared context:** `./docs/execution/search-quality-v2/_shared_context.md`

---

## Objective

Update all frontend tests that reference removed concepts: exclusion state, result_snapshot, conversation_state.messages, pivot detection, parseConversationTurns.

## What to Do

### 1. Update streaming search tests

**File:** `<linkedout-fe>/src/__tests__/hooks/useStreamingSearch.test.ts`

- Remove all tests referencing `exclusionState` / `ExclusionState`
- Update `restoreResults` / `restoreTurns` tests for turn-based flow
- Remove tests for `exclusion_state` in SSE `conversation_state` event

### 2. Update SearchPageContent regression tests

**File:** `<linkedout-fe>/src/__tests__/components/search/SearchPageContent.regression-001.test.tsx`

- Remove `result_snapshot` references
- Update session resume tests to use turn-based approach
- Remove tests for pivot detection / session swaps

### 3. Review split-panel bug tests

**File:** `<linkedout-fe>/src/__tests__/hooks/useStreamingSearch.split-panel-bugs.test.ts`

- Review `restoreResults` tests — may need updates for turn-based flow
- Update any references to old session data shape

### 4. Search for any remaining test references

```bash
cd <linkedout-fe>
grep -r "exclusionState\|ExclusionState\|result_snapshot\|conversation_state\.messages\|parseConversationTurns\|pivot\|start_new_search" src/__tests__/ --include='*.ts' --include='*.tsx'
```

Fix any remaining references found.

## Verification

```bash
cd <linkedout-fe>

# All tests pass
npm test -- --watchAll=false

# Type check clean
npx tsc --noEmit

# Lint clean
npm run lint
```
