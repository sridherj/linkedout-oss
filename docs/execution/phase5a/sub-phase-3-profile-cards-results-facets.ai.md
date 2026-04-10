# Sub-Phase 3: Profile Cards + Results + Pagination + Facets

**Goal:** linkedin-ai-production
**Phase:** 5a — Search UI (Frontend)
**Depends on:** SP-2 (streaming hook, types, thinking state must exist)
**Estimated effort:** 3h
**Source plan steps:** 6, 7, 8

---

## Objective

Build the core search results experience: enriched and unenriched profile cards, initials avatar fallback, profile image serving, the results list with pagination, and the faceted refinement panel. This is the most important sub-phase — it produces the primary UI that users interact with.

## Context

- **Frontend:** `<linkedout-fe>/`
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md` — **READ THIS** before building any cards
- Profile images stored at `<data-dir>/images/{public_identifier}.jpg`
- Backend result cap: 100 results max. Client-side pagination over this set.
- Client-side filtering only (no re-query on facet change)
- URL params are source of truth for page, sort, and filter state
- `useStreamingSearch` hook (from SP-2) provides `results`, `isStreaming`, `isComplete`

## Pre-Flight Checks

Before starting, verify:
- [ ] SP-2 complete: streaming hook works, results accumulate from stub backend
- [ ] Profile images directory exists at `<data-dir>/images/`
- [ ] Design system spec read and understood

## Files to Create

```
<linkedout-fe>/src/
├── components/
│   ├── profile/
│   │   ├── ProfileCard.tsx              # Enriched profile card
│   │   ├── ProfileCardUnenriched.tsx     # CSV-only profile card
│   │   ├── ProfileCardSkeleton.tsx       # Shimmer loading placeholder
│   │   └── InitialsAvatar.tsx            # Fallback avatar (2-letter, deterministic color)
│   └── search/
│       ├── ResultsList.tsx               # Results container + count header + sort
│       ├── Pagination.tsx                # Numbered page navigation
│       └── FacetPanel.tsx                # Sidebar filters
├── app/
│   └── api/
│       └── images/
│           └── [identifier]/
│               └── route.ts              # Profile image serving API route
└── lib/
    └── utils.ts                          # Add initials generation + deterministic color hash
```

---

## Step 1: Profile Image Serving (Plan Step 6, task 5)

Create `src/app/api/images/[identifier]/route.ts`:
- Reads from `PROFILE_IMAGES_DIR` env var (default: `<data-dir>/images`)
- Looks for `{identifier}.jpg` (or `.png`, `.webp`)
- If found: return image with `Cache-Control: public, max-age=86400`
- If not found: return 404
- Consider using `next/image` optimization for automatic resizing/WebP

---

## Step 2: Initials Avatar (Plan Step 6, task 4)

Create `src/components/profile/InitialsAvatar.tsx`:
- Takes `name: string`, generates 2-letter initials (first letter of first + last name)
- Background color from deterministic hash of name (6-8 pastel colors from design system)
- 40px circle matching profile image size
- Add `getInitials(name)` and `getColorFromName(name)` to `src/lib/utils.ts`

---

## Step 3: Enriched Profile Card (Plan Step 6, task 1)

Create `src/components/profile/ProfileCard.tsx`:

**Desktop layout (left to right):**
- Avatar (40px circle) — profile image from API route, or InitialsAvatar fallback
- Name + headline
- Location (city, country)
- Affinity score badge (color-coded: green ≥80, yellow 50-79, gray <50)
- Dunbar tier badge (inner_circle, active, familiar, acquaintance)

**Below:**
- Current role line (company + position)
- "Why This Person" explanation (1-line, may be null initially — populated from `explanations` SSE event)
- Connection date

**Action row:**
- LinkedIn external link (new tab, `ExternalLink` icon)
- Save button (Phase 5a scope — placeholder for now)
- Overflow menu (future actions — placeholder)

**Mobile:** Stack vertically — avatar + name + headline on row 1, details below, actions full-width

**Image fallback:** Load image from `/api/images/{public_identifier}`. On error (404), render `InitialsAvatar`.

---

## Step 4: Unenriched Profile Card (Plan Step 6, task 2)

Create `src/components/profile/ProfileCardUnenriched.tsx`:
- Simplified card for connections with `has_enriched_data === false`
- Shows CSV-only data: name, company, title
- No affinity score, no "Why This Person", no profile image
- Prominent "Enrich" button (wired in SP-5, placeholder for now)
- Visual indicator: muted/grayed styling to distinguish from enriched cards

---

## Step 5: Skeleton Card (Plan Step 6, task 3)

Create `src/components/profile/ProfileCardSkeleton.tsx`:
- Shimmer placeholder matching card layout dimensions
- Shown during streaming while awaiting next result

---

## Step 6: Results List + Sort (Plan Step 7, task 1)

Create `src/components/search/ResultsList.tsx`:
- Maps `results[]` → `ProfileCard` or `ProfileCardUnenriched` based on `has_enriched_data`
- Result count header: "Showing 1-20 of 142 results"
- Sort controls: Affinity (default), Name (A-Z), Connection Date (newest first)
- Sort state in URL: `?sort=affinity|name|date`
- During streaming: show skeleton cards for remaining expected results

---

## Step 7: Numbered Pagination (Plan Step 7, task 2)

Create `src/components/search/Pagination.tsx`:
- shadcn/ui pagination component
- URL pattern: `?q=<query>&page=2&sort=affinity`
- Page size: 20 results desktop, 10 mobile
- Numbered pages with ellipsis for large sets (e.g., 1 2 3 ... 5)
- All page state serialized to URL params
- Back button works between pages

---

## Step 8: Faceted Refinement Panel (Plan Step 8)

Create `src/components/search/FacetPanel.tsx`:

**Filter state lives in URL params** (no Zustand). Facet selections serialized as: `?location=SF,NYC&company=Google&seniority=Senior`.

**Facets derived from current result set (dynamic, not static):**
- Location (multi-select chip group — top cities from results)
- Company (multi-select — top companies from results)
- Seniority Level (IC, Senior, Staff, Director, VP, C-Suite)
- Function Area (Engineering, Product, Sales, HR, etc.)

**Behavior:**
- On facet change: filter in-memory result list client-side (<50ms, no re-query)
- Active filter count badge
- "Clear all" button
- Facet values update when result set changes (new query)

**Layout:**
- **Desktop:** Left sidebar panel (240px wide)
- **Mobile:** Hidden behind "Refine" button → slides in as right-side tray overlay (detailed styling in SP-6)

---

## Step 9: Wire Everything on Search Page

Update `src/app/page.tsx` (or `search/page.tsx`) to compose:
- SearchBar (from SP-1, wired to hook in SP-2)
- ThinkingState (from SP-2)
- FacetPanel (sidebar)
- ResultsList with ProfileCards
- Pagination

Layout: sticky search bar at top, facet sidebar left, results + pagination in main content area.

---

## Completion Criteria

- [ ] Enriched profile card shows: name, headline, company, location, affinity badge, dunbar badge, why this person, connection date
- [ ] Profile image loads from local path via API route; initials fallback works on 404
- [ ] Unenriched card shows CSV data + Enrich button (placeholder)
- [ ] LinkedIn URL opens in new tab
- [ ] Skeleton cards show during streaming
- [ ] Cards look correct on mobile (375px viewport)
- [ ] Sort toggle re-orders results client-side
- [ ] Page navigation updates URL and shows correct slice
- [ ] Back button works between pages
- [ ] Selecting a location filter instantly narrows results (client-side)
- [ ] Multiple facets compose (AND logic)
- [ ] Clear all resets to full result set
- [ ] Facet values update on new query
