# Sub-Phase 6: Mobile Responsiveness + Error States + Testing

**Goal:** linkedin-ai-production
**Phase:** 5a — Search UI (Frontend)
**Depends on:** SP-1 through SP-5 (all features must exist)
**Estimated effort:** 3.5h
**Source plan steps:** 13, 14, 15

---

## Objective

Polish the application with mobile responsiveness across all pages, implement error states and edge cases, and write comprehensive tests (unit, component, hook, and optionally e2e). This sub-phase is the quality gate before Phase 5a is considered complete.

## Context

- **Frontend:** `<linkedout-fe>/`
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md`
- All features from SP-1 through SP-5 must be functional
- Test infrastructure (vitest, testing-library) was set up in SP-1
- Minimum viewport: 375px (iPhone SE)

## Pre-Flight Checks

Before starting, verify:
- [ ] All prior sub-phases complete: search, streaming, cards, facets, history, import, enrichment, export all functional
- [ ] `npm run dev` serves the full app
- [ ] `npm test` runs vitest (may have no tests yet)

---

## Part A: Mobile Responsiveness Pass (Plan Step 13)

**Effort:** 0.5h

### Responsive Breakpoints

| Breakpoint | Width | Layout |
|-----------|-------|--------|
| Desktop | ≥1024px | Sidebar + content |
| Tablet | 768-1023px | Collapsible sidebar |
| Mobile | <768px | Stacked layout, hamburger nav |

### Tasks

1. **Profile cards:** Stack vertically on mobile. Ensure no horizontal scroll.
2. **Facet panel:** Becomes slide-in tray on mobile (behind "Refine" button). Right-side overlay that opens/closes without layout shift.
3. **Search bar:** Stays sticky on all breakpoints.
4. **Pagination:** Show fewer page numbers on mobile (1 ... 3 ... 5 instead of 1 2 3 4 5).
5. **Import zone:** Adapts to single-column layout.
6. **Touch targets:** All interactive elements ≥ 44px tap target.
7. **Navigation:** Hamburger menu on mobile (already in SP-1, verify it works with all pages).

### Verification
- [ ] 375px viewport: all pages usable, no horizontal scroll
- [ ] Facet tray opens/closes without layout shift
- [ ] Profile cards readable without horizontal scroll
- [ ] Touch targets ≥ 44px
- [ ] Pagination adapts for small screens

---

## Part B: Error States + Edge Cases (Plan Step 14)

**Effort:** 0.5h

### Tasks

1. **Search error state:** "Something went wrong" with retry button (when SSE stream errors)
2. **Empty results state:** Show "No Results" illustration + suggestion to broaden query
3. **Network error:** Toast notification + offline indicator
4. **Backend unreachable:** Full-page error: "Backend is starting up, please wait..." with auto-retry
5. **SSE stream interrupted:** Auto-retry once, then show error state with manual retry
6. **Invalid file upload:** Clear error message with expected format (.csv, .vcf)
7. **Empty history:** Friendly empty state on history page

### Files to Create/Modify

- Error boundary component (if not already present)
- Empty state components for each page
- Toast notification system (shadcn/ui Toast or Sonner)

### Verification
- [ ] Each error state renders the correct UI
- [ ] Retry buttons work
- [ ] No uncaught errors in console during normal use
- [ ] Empty states show appropriate messaging

---

## Part C: Testing (Plan Step 15)

**Effort:** 2.5h

### C1: Unit Tests (Vitest)

Test pure functions in `src/lib/`:
- `utils.ts`: `getInitials(name)` — handles single name, two names, empty, multi-word
- `utils.ts`: `getColorFromName(name)` — deterministic, returns valid hex
- `ExportMenu`: CSV formatting — correct columns, correct escaping, filter-respecting
- URL param serialization/deserialization helpers (if extracted)
- SSE event parsing logic (extract from hook into testable function)

### C2: Component Tests (React Testing Library)

- **ProfileCard:** renders enriched variant with all fields; handles null optional fields gracefully
- **ProfileCardUnenriched:** renders CSV data + Enrich button; correct muted styling
- **ProfileCardSkeleton:** renders shimmer elements
- **InitialsAvatar:** correct 2-letter initials; deterministic background color
- **SearchBar:** submit writes query to URL; Cmd+K focuses input; clear button clears
- **Pagination:** correct page links for various total counts; URL updates on page click
- **FacetPanel:** selecting a filter updates URL params; "Clear all" resets
- **ThinkingState:** steps appear/disappear based on streaming state

### C3: Hook Tests (`renderHook`)

- **useStreamingSearch:**
  - Handles stream events in sequence (thinking → results → explanations → done)
  - `abort()` closes connection
  - Error state on stream failure
  - Re-render batching works (results accumulated in ref, flushed on rAF)
  - Cached results returned for repeat queries within TTL

### C4: E2E Tests (Playwright — optional, time-permitting)

If time allows:
- Full search flow: type query → see thinking state → results stream in → paginate → filter → export CSV
- Import flow: upload CSV → progress indicator → completion
- Error states: backend unreachable → error page; empty results → illustration

### Test File Structure

```
<linkedout-fe>/src/
├── __tests__/                           # or colocated with components
│   ├── lib/
│   │   └── utils.test.ts
│   ├── components/
│   │   ├── profile/
│   │   │   ├── ProfileCard.test.tsx
│   │   │   ├── ProfileCardUnenriched.test.tsx
│   │   │   └── InitialsAvatar.test.tsx
│   │   └── search/
│   │       ├── SearchBar.test.tsx
│   │       ├── Pagination.test.tsx
│   │       ├── FacetPanel.test.tsx
│   │       ├── ThinkingState.test.tsx
│   │       └── ExportMenu.test.tsx
│   └── hooks/
│       └── useStreamingSearch.test.ts
```

### Verification
- [ ] `npm test` runs and all tests pass
- [ ] Component tests cover both enriched and unenriched profile card variants
- [ ] Hook tests verify streaming lifecycle (start, receive, complete, abort, error)
- [ ] Unit tests cover utility functions with edge cases

---

## Completion Criteria (Phase 5a Final Gate)

- [ ] All pages usable on 375px viewport
- [ ] All error states render correctly with retry functionality
- [ ] `npm test` passes with comprehensive coverage
- [ ] No uncaught errors in console during normal use
- [ ] App is ready for user demo
