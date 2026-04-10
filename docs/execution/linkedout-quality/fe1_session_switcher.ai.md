# FE1: Session Switcher & Session Resume

## Context
Backend session persistence is complete (SP5). The API endpoints are live. This sub-phase builds the frontend session management UI.

## Important: File Resolution
- **Frontend code lives at:** `<linkedout-fe>`
- **Backend code and specs live at:** `.` (also accessible via `.`)
- If a referenced file is not found at one location, check `.`, `.`, or `<prior-project>`
- **Leverage the `/ui-ux-pro-max` skill** for all UI implementation work

## Design Reference
- **HTML mockup:** `<linkedout-fe>/docs/design/session-history-new-search.html`
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md`
- **Frontend design spec (if exists):** `<linkedout-fe>/docs/specs/`

## Backend API Contract
- `GET /sessions` → `[{id, initial_query, status, last_active_at, result_count, turn_count}]`
- `GET /sessions/{id}` → full session state
- `GET /sessions/latest` → most recent active session
- `POST /sessions` → creates new session, archives current
- **Backend spec:** `./docs/specs/search_sessions.collab.md`
- **Backend contracts:** `./src/linkedout/intelligence/contracts.py`

## Frontend Patterns (match these)
- **API client:** `<linkedout-fe>/src/lib/api-client.ts` — uses `apiFetch<T>(path, options)` with `NEXT_PUBLIC_API_URL` base
- **Data fetching:** TanStack React Query (`@tanstack/react-query`) — see `useQueryClient` usage in `<linkedout-fe>/src/hooks/useStreamingSearch.ts`
- **Streaming search:** `<linkedout-fe>/src/hooks/useStreamingSearch.ts` — SSE via `POST /api/search/stream` with `tenant_id`, `bu_id`, `app_user_id` hardcoded
- **Types:** `<linkedout-fe>/src/types/search.ts` — `ProfileResult`, `SearchEvent`, `SearchEventType`
- **UI primitives:** `<linkedout-fe>/src/components/ui/` — `button.tsx`, `badge.tsx`, `input.tsx`, `card.tsx`
- **Styling:** Tailwind with design system tokens (berry-accent, bg-primary, text-primary, etc.)
- **Components are "use client"** with Next.js App Router

## Existing Frontend Files to Modify/Extend
- `<linkedout-fe>/src/components/search/SearchBar.tsx` — currently a simple form with input + clear + ⌘K. Add session switcher dropdown alongside search input
- `<linkedout-fe>/src/components/search/SearchPageContent.tsx` — currently loads empty hero when no query. Change to load existing session results by default via `GET /sessions/latest`
- `<linkedout-fe>/src/hooks/useStreamingSearch.ts` — may need session_id integration into search requests

## Activities

### FE1.1 Session Switcher Dropdown Component
- New component: `SessionSwitcher.tsx` in `<linkedout-fe>/src/components/search/`
- Scrollable dropdown list showing: query text, status tag (Active/Archived), relative timestamp, result count, turn count, resume button
- Integrate into search bar row alongside search input + "New Search" button

### FE1.2 Active Session Label
- Dot indicator + "Active session · Turn N" label
- Displayed when a session is active
- Updates on each turn

### FE1.3 Session Resume on Page Load
- Search page loads most recent active session results by default (via `GET /sessions/latest`)
- Not an empty search box — user sees their last session's results
- Session switcher shows the active session selected

### FE1.4 New Search Flow
- "New Search" button archives current session (`POST /sessions`) and resets UI to empty search state
- Session switcher updates to show newly archived session

### FE1.5 API Integration
- Create API client hooks for session endpoints (React Query or SWR, match existing patterns in the frontend codebase)
- Wire session state into search flow

## Verification
- [ ] Session switcher renders with mock data
- [ ] Clicking a past session loads its results
- [ ] "New Search" archives current and resets
- [ ] Page load shows most recent active session
- [ ] Design matches HTML mockup at `<linkedout-fe>/docs/design/session-history-new-search.html`
- [ ] Follows design system at `<linkedout-fe>/docs/design/linkedout-design-system.md`
