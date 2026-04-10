# Sub-Phase 1: Scaffold + Layout + Search Bar

**Goal:** linkedin-ai-production
**Phase:** 5a — Search UI (Frontend)
**Depends on:** Nothing (first sub-phase)
**Estimated effort:** 1.75h
**Source plan steps:** 1, 2, 3

---

## Objective

Set up the Next.js 15 project scaffold with shadcn/ui, apply the Berry Fields Soft design tokens, build the app shell with navigation, and create the sticky search bar with URL-driven state. This sub-phase produces a navigable app skeleton that all subsequent sub-phases build on.

## Context

- **Code directory:** `<linkedout-fe>/`
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md` — **READ THIS FIRST** before any UI decisions
- A scaffold may already exist from Spike S9. Evaluate whether to restructure or start fresh based on design spec.
- No Zustand — all navigation state lives in URL params.
- No Vercel AI SDK — will be removed if present from spike.

## Pre-Flight Checks

Before starting, verify:
- [ ] Design system file exists at `<linkedout-fe>/docs/design/linkedout-design-system.md`
- [ ] Check if `<linkedout-fe>/` already has a Next.js scaffold from S9
- [ ] FastAPI backend runs at `http://localhost:8000` (for proxy verification)

## Files to Create/Modify

```
<linkedout-fe>/
├── next.config.ts                    # API proxy rewrites
├── .env.local                        # NEXT_PUBLIC_API_URL, PROFILE_IMAGES_DIR
├── vitest.config.ts                  # Test configuration
├── src/
│   ├── app/
│   │   ├── layout.tsx                # Root layout with TanStack Query provider
│   │   ├── page.tsx                  # Search page (main entry)
│   │   ├── search/page.tsx           # Search results (may merge with page.tsx)
│   │   ├── import/page.tsx           # Placeholder
│   │   └── history/page.tsx          # Placeholder
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx          # Top bar, nav, footer
│   │   │   └── MobileNav.tsx         # Hamburger menu
│   │   ├── search/
│   │   │   └── SearchBar.tsx         # Sticky search input
│   │   └── ui/                       # shadcn/ui components
│   ├── lib/
│   │   ├── api-client.ts             # Fetch wrapper with base URL + error handling
│   │   └── utils.ts                  # CN utility + future helpers
│   └── types/                        # TypeScript types directory
├── package.json                      # Updated with test scripts
└── globals.css                       # Berry Fields Soft tokens replacing shadcn defaults
```

---

## Step 1: Project Scaffold + Configuration (Plan Step 1)

**Tasks:**
1. If S9 scaffold exists, evaluate it against design spec. Restructure or start fresh as needed.
2. If starting fresh, scaffold Next.js 15:
   ```bash
   npx create-next-app@latest <linkedout-fe> --typescript --tailwind --app --src-dir
   ```
3. Initialize shadcn/ui:
   ```bash
   cd <linkedout-fe> && npx shadcn@latest init
   ```
4. Install dependencies:
   ```bash
   npm install @tanstack/react-query
   npm install -D vitest @testing-library/react @testing-library/jest-dom @vitejs/plugin-react jsdom
   ```
5. **Do NOT install:** `zustand`, `ai`, `@ai-sdk/anthropic` — these are explicitly excluded.
6. Configure `next.config.ts` — proxy `/api/backend/:path*` to `http://localhost:8000/:path*`
7. Set up `.env.local`:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   PROFILE_IMAGES_DIR=<data-dir>/images
   ```
8. Create `vitest.config.ts` with React plugin and jsdom environment.
9. Add `"test": "vitest run"` and `"test:watch": "vitest"` scripts to `package.json`.
10. Apply design system tokens from `linkedout-design-system.md`:
    - Replace shadcn default oklch tokens with Berry Fields Soft hex tokens in `globals.css`
    - **Skip dark mode cleanup** — just apply the light theme tokens
    - Configure fonts and typography per design spec
11. Create `src/lib/api-client.ts` — thin fetch wrapper with base URL from env, error handling, auth header injection slot.

**Verification:**
- [ ] `npm run dev` → app loads at localhost:3000
- [ ] Design tokens (colors, fonts) match design spec
- [ ] `npm test` → vitest runs (even if no tests yet)

---

## Step 2: Layout Shell + Navigation (Plan Step 2)

**Tasks:**
1. Build root layout (`src/app/layout.tsx`):
   - TanStack Query provider (wrap with `QueryClientProvider`)
   - Apply design system fonts + global styles
2. Build app shell (`src/components/layout/AppShell.tsx`):
   - Top bar: logo ("LinkedOut"), navigation links (Search, Import, History)
   - Style per design system
   - Footer: minimal
3. Build mobile nav (`src/components/layout/MobileNav.tsx`):
   - Hamburger menu for mobile breakpoints
   - Opens/closes navigation overlay
4. Navigation links: Search (`/`), Import (`/import`), Search History (`/history`)
5. Create placeholder pages for `/import` and `/history` (just titles + AppShell)

**Verification:**
- [ ] Navigation between pages works (/, /import, /history)
- [ ] Mobile hamburger menu opens/closes
- [ ] Layout matches design spec

---

## Step 3: Sticky Search Bar (Plan Step 3)

**Tasks:**
1. Create `src/components/search/SearchBar.tsx`:
   - shadcn/ui `Input` + `Button`
   - `position: sticky; top: 0; z-index: 50` — never scrolls out of view
   - Placeholder: `"e.g., engineers at YC startups, based in SF"`
   - Keyboard shortcut: `Cmd+K` / `Ctrl+K` to focus
   - Search icon, clear button when query exists
   - Loading spinner slot (wired in SP-2)
2. On submit: write query to URL params (`?q=<query>`) via `useRouter` + `useSearchParams`
3. Query value always driven from URL state (not component-local state)
4. Submit on Enter/click only — no debounce needed

**Verification:**
- [ ] Typing + Enter → URL updates to `?q=<query>`
- [ ] Back button restores previous query
- [ ] Cmd+K focuses the search input
- [ ] Sticky behavior works on scroll
- [ ] Clear button clears query and URL param

---

## Completion Criteria

- [ ] `npm run dev` serves the app at localhost:3000
- [ ] Design tokens match the design system spec
- [ ] Three pages navigable: /, /import, /history
- [ ] Search bar is sticky, URL-driven, and supports Cmd+K
- [ ] Mobile hamburger nav works
- [ ] `npm test` runs successfully (vitest configured)
- [ ] No Zustand, no Vercel AI SDK in dependencies
