# SPIKE: Session Switcher Visibility Inconsistency (FINDING-005)

**Date:** 2026-04-02
**Status:** Root cause identified + fix applied
**Complexity:** Trivial fix (conditional render prop omission)

## Reported Behavior

At 960px viewport, the session switcher ("19 sessions" + "New Search" buttons) appeared on initial load. At 1440px, those buttons disappeared from the DOM. On a subsequent reload, "20 sessions" + "+ New Search" appeared at both sizes. The session count changed (19 vs 20) between loads, and the styling appeared inconsistent.

## Root Cause

**Two separate `<SearchBar>` renders in `SearchPageContent.tsx` — only one receives the session switcher prop.**

### The two code paths

1. **Results view** (line 265-273): Renders when `!showEmpty && !hasConversationTurns`
   ```tsx
   <SearchBar
     isLoading={isStreaming}
     onNewSearch={handleNewSearch}
     sessionSwitcher={sessionSwitcherNode}
   />
   ```
   → Gets `sessionSwitcher` and `onNewSearch` props → session switcher and "New Search" button are visible.

2. **Hero/empty view** (line 316-317): Renders when `showEmpty` is true
   ```tsx
   <SearchBar isLoading={isStreaming} />
   ```
   → Gets **neither** prop → session switcher and "New Search" button are **never** rendered.

### Why this is timing-dependent

The `showEmpty` flag is:
```tsx
const showEmpty = !mounted || (!query && !hasResumedResults);
```

- `mounted` starts `false` (SSR guard), becomes `true` after first useEffect
- `hasResumedResults` depends on `latestSession` loading via `useLatestSession()` (async React Query)
- `latestSession` must load AND have a non-empty `result_snapshot` AND status `"active"` for `resumedResults` to be set (lines 110-120)

**Timeline on page load (no query param):**
1. First render: `mounted=false` → `showEmpty=true` → hero SearchBar (no session switcher)
2. After mount: `mounted=true`, `latestSession` still loading → `showEmpty=true` → hero SearchBar (no session switcher)
3. `latestSession` resolves → if it has active results → `resumedResults` set → `showEmpty=false` → results SearchBar (session switcher visible)
4. If `latestSession` has NO result_snapshot or is not "active" → `showEmpty` stays true → session switcher never appears

The viewport-size correlation observed in the design review is **coincidental** — different network/render timings at different viewport sizes caused the observer to catch different states of this race.

### Session count discrepancy (19 vs 20)

The `useSessionList()` hook has `staleTime: 30_000` (30 seconds). Each search creates a new session. Between the two loads, a new session was created, so the count incremented.

### "Competing component versions" (plain text vs pill styling)

There is only one `SessionSwitcher` component with one style (berry-accent pill with green dot). The "plain text" appearance was likely the observer catching the page in the hero state (where no session switcher renders at all), vs the results state (where the styled component appears).

## Fix Applied

**Passed `sessionSwitcherNode` and `onNewSearch` to the hero SearchBar.**

In `linkedout-fe/src/components/search/SearchPageContent.tsx`, changed the hero SearchBar from:
```tsx
<SearchBar isLoading={isStreaming} />
```
to:
```tsx
<SearchBar
  isLoading={isStreaming}
  onNewSearch={sessions.length > 0 ? handleNewSearch : undefined}
  sessionSwitcher={sessionSwitcherNode}
/>
```

This ensures the session switcher is visible in both the hero and results views whenever sessions exist.

### Design consideration

The hero view may need slight layout adjustment to accommodate the session switcher buttons alongside the search input in the centered hero layout. The results-view SearchBar is in a full-width sticky bar with `max-w-2xl` — this works fine. The hero SearchBar is inside a `max-w-md` container, so the session switcher + "New Search" button may need to be positioned differently (e.g., above or below the search input rather than inline).

## Remaining Work

- Visual QA: verify at 960px, 1440px, and 375px viewports with 0 sessions and >0 sessions
- Layout polish if the hero `max-w-md` container doesn't accommodate the inline buttons well

## Files Involved

- `src/components/search/SearchPageContent.tsx` — fix applied (hero SearchBar now receives session switcher props)
- `src/components/search/SearchBar.tsx` — receives props, no changes needed
- `src/components/search/SessionSwitcher.tsx` — renders the switcher, no changes needed
- `src/hooks/useSession.ts` — data fetching, no changes needed
