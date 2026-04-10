# Sub-phase 2a: Session Switcher & Session Resume
./docs/execution/linkedout-quality-fe
> **Pre-requisite:** Read `/_shared_context.md` before starting this sub-phase.

## Objective

Build session management into the search page: a session switcher dropdown alongside the search bar, a "New Search" button, an active session label, and automatic session resume on page load. Users should land on their most recent active session's results instead of an empty search box. This enables multi-turn conversation persistence across browser sessions.

## Dependencies
- **Requires completed:** SP1 (Result Cards) -- cards must render highlighted_attributes and have onClick handler
- **Assumed codebase state:** `ProfileResult` type has `highlighted_attributes`, `ProfileCard` has `onClick` prop, `useStreamingSearch` handles structured explanations

## Scope
**In scope:**
- Create `SessionSwitcher.tsx` dropdown component
- Create `useSession.ts` hook for session CRUD (TanStack React Query)
- Create session TypeScript types
- Add active session label component
- Modify `SearchBar.tsx` to include session switcher + "New Search" button
- Modify `SearchPageContent.tsx` to load latest session on mount
- Modify `useStreamingSearch.ts` to accept/pass `session_id`
- Modify SSE proxy route to forward `session_id`
- Visually match HTML mockup at `<linkedout-fe>/docs/design/session-history-new-search.html`

**Out of scope (do NOT do these):**
- Profile slide-over panel (SP2b)
- Conversation thread UI (SP3)
- Follow-up input bar (SP3)
- Backend changes
- Changing card styling (SP1 already done)

## Files to Create/Modify

| File | Action | Current State |
|------|--------|---------------|
| `<linkedout-fe>/src/types/session.ts` | Create | Does not exist |
| `<linkedout-fe>/src/hooks/useSession.ts` | Create | Does not exist |
| `<linkedout-fe>/src/components/search/SessionSwitcher.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/search/ActiveSessionLabel.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/search/SearchBar.tsx` | Modify | Simple form with input + clear + Cmd+K |
| `<linkedout-fe>/src/components/search/SearchPageContent.tsx` | Modify | Loads empty hero when no query |
| `<linkedout-fe>/src/hooks/useStreamingSearch.ts` | Modify | No session_id support |
| `<linkedout-fe>/src/app/api/search/stream/route.ts` | Modify | No session_id forwarding |

## Detailed Steps

### Step 2a.1: Create Session Types

Create `<linkedout-fe>/src/types/session.ts`:

```typescript
export interface SearchSession {
  id: string;
  initial_query: string;
  status: "active" | "archived";
  turn_count: number;
  last_active_at: string;
  result_count?: number;
  result_snapshot?: Record<string, unknown>[];
  conversation_state?: {
    messages: Record<string, unknown>[];
    structured_summary?: Record<string, unknown>;
  };
}

export interface SessionListItem {
  id: string;
  initial_query: string;
  status: "active" | "archived";
  turn_count: number;
  last_active_at: string;
  result_count?: number;
}
```

### Step 2a.2: Create useSession Hook

Create `<linkedout-fe>/src/hooks/useSession.ts`:

Use TanStack React Query (matching existing pattern from `useSearchHistory.ts`).

```typescript
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { SearchSession, SessionListItem } from "@/types/session";

const TENANT_ID = "tenant_sys_001";
const BU_ID = "bu_sys_001";
const APP_USER_ID = "usr_sys_001";
const BASE = `/tenants/${TENANT_ID}/bus/${BU_ID}`;

export function useSessionList() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: () => apiFetch<SessionListItem[]>(`${BASE}/sessions?app_user_id=${APP_USER_ID}`),
    staleTime: 30_000,
  });
}

export function useLatestSession() {
  return useQuery({
    queryKey: ["sessions", "latest"],
    queryFn: () => apiFetch<SearchSession>(`${BASE}/sessions/latest?app_user_id=${APP_USER_ID}`),
    staleTime: 30_000,
    retry: false,  // 404 = no active session, don't retry
  });
}

export function useSessionDetail(sessionId: string | null) {
  return useQuery({
    queryKey: ["sessions", sessionId],
    queryFn: () => apiFetch<SearchSession>(`${BASE}/sessions/${sessionId}?app_user_id=${APP_USER_ID}`),
    enabled: !!sessionId,
    staleTime: 30_000,
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<SearchSession>(`${BASE}/sessions`, {
        method: "POST",
        body: JSON.stringify({ app_user_id: APP_USER_ID }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}
```

**Important:** The exact API response shape depends on the backend. Read the sessions spec at `./docs/specs/search_sessions.collab.md` and adjust field names if needed.

### Step 2a.3: Create SessionSwitcher Component

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/search/SessionSwitcher.tsx`

Design from HTML mockup (`session-history-new-search.html`):

**Trigger button:**
- `session-btn` style: border pill with dot indicator + "N sessions" + chevron-down icon
- Active state: border-berry-accent, bg-berry-accent-light, text-berry-accent-dark
- Dot: 7px berry-accent circle

**Dropdown panel (absolute positioned below trigger):**
- Panel: border rounded-xl, bg-bg-surface, shadow
- Header: "Your search sessions" label + "View all history" link
- Scrollable list (max-height 340px)
- Each session item:
  - Icon: search icon in 32px rounded-lg box (accent-light for current, bg-subtle for past)
  - Query text (font-size 0.875rem, weight 500)
  - Meta row: status tag (Active=pastel-mint, Archived=bg-subtle) + relative time + result count + turn count
  - Current session: highlighted bg (accent-light)
  - Past sessions: resume button (play icon)

Props: `{ sessions: SessionListItem[]; activeSessionId: string | null; onResume: (id: string) => void; onToggle: () => void; isOpen: boolean }`

After delegation, review:
- Dropdown closes on click-outside
- Session items show correct status tags
- Resume button triggers `onResume`
- Visual match to mockup

### Step 2a.4: Create ActiveSessionLabel Component

Create `<linkedout-fe>/src/components/search/ActiveSessionLabel.tsx`:

```tsx
"use client";

interface ActiveSessionLabelProps {
  query: string;
  turnCount: number;
}

export function ActiveSessionLabel({ query, turnCount }: ActiveSessionLabelProps) {
  const shortQuery = query.length > 40 ? query.slice(0, 40) + "..." : query;
  return (
    <div className="flex items-center gap-2 mb-4">
      <span className="h-2 w-2 rounded-full bg-berry-accent" />
      <span className="font-mono text-xs text-text-secondary">
        Active session · {shortQuery}
      </span>
      <span className="font-mono text-xs text-text-tertiary">
        · Turn {turnCount} of this session
      </span>
    </div>
  );
}
```

### Step 2a.5: Modify SearchBar for Session Controls

-> Delegate: `/ui-ux-pro-max` -- Modify `<linkedout-fe>/src/components/search/SearchBar.tsx`

Changes from mockup:
1. Wrap the existing search input in a flex row with session controls
2. Add `SessionSwitcher` button to the right of the search input
3. Add "New Search" button (berry-accent bg, white text, plus icon):
   ```tsx
   <button
     type="button"
     onClick={onNewSearch}
     className="flex shrink-0 items-center gap-1.5 rounded-lg border-none bg-berry-accent px-3.5 py-2 font-ui text-sm font-medium text-white transition-colors hover:bg-berry-accent-hover"
   >
     <Plus className="size-3.5" />
     New Search
   </button>
   ```
4. New props: `onNewSearch?: () => void; sessionSwitcher?: React.ReactNode`

The search row layout from mockup:
```
[search-bar (flex-1)] [session-btn] [New Search btn]
```

After delegation, review:
- Search input still functions (submit, Cmd+K, clear)
- Session controls align properly
- "New Search" button styling matches mockup

### Step 2a.6: Modify SearchPageContent for Session Resume

Edit `<linkedout-fe>/src/components/search/SearchPageContent.tsx`:

Major changes:
1. Import `useLatestSession`, `useSessionList`, `useCreateSession`, `useSessionDetail`
2. Import `SessionSwitcher`, `ActiveSessionLabel`
3. On mount (no query param), fetch latest session via `useLatestSession`
4. If latest session exists, populate results from `result_snapshot` and show session UI
5. "New Search" handler: call `useCreateSession`, reset search state, clear URL query
6. "Resume session" handler: fetch session detail, populate results
7. Pass `SessionSwitcher` as a prop to `SearchBar`
8. Show `ActiveSessionLabel` above results when a session is active

**Session state management:**
```typescript
const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
const { data: latestSession } = useLatestSession();
const { data: sessions } = useSessionList();
const createSession = useCreateSession();

// On mount, if no query and latest session exists, show its results
useEffect(() => {
  if (!query && latestSession && latestSession.status === "active") {
    setActiveSessionId(latestSession.id);
    // Populate results from session's result_snapshot
    // This may require extending useStreamingSearch or using separate state
  }
}, [latestSession, query]);
```

### Step 2a.7: Modify useStreamingSearch for session_id

Edit `<linkedout-fe>/src/hooks/useStreamingSearch.ts`:

1. Add `session_id` to the search request body:
   ```typescript
   body: JSON.stringify({
     query,
     session_id: sessionId ?? undefined,
     tenant_id: "tenant_sys_001",
     bu_id: "bu_sys_001",
     app_user_id: "usr_sys_001",
   }),
   ```
2. Update `search` function signature: `async (query: string, sessionId?: string)`

### Step 2a.8: Update SSE Proxy Route

Edit `<linkedout-fe>/src/app/api/search/stream/route.ts`:

Forward `session_id` in the backend request body:
```typescript
body: JSON.stringify({ query, session_id: session_id ?? undefined }),
```

## Verification

### Automated Tests (permanent)

No new test files (frontend visual verification). Type checking is the automated gate.

### Validation Scripts (temporary)

```bash
# TypeScript compilation
cd <linkedout-fe> && npx tsc --noEmit

# Dev server starts
cd <linkedout-fe> && npm run dev
```

### Manual Checks

1. Open the app with no query -- should load most recent active session's results (not empty hero)
2. If no active session exists, show empty hero as before
3. Click session switcher button -- dropdown shows list of sessions with status tags
4. Click "Resume" on an archived session -- loads that session's results
5. Click "New Search" -- archives current session, shows empty search state
6. Session switcher updates to show newly archived session
7. Active session label shows below search bar with query text and turn count
8. Search with a query -- `session_id` is included in the request
9. Compare visually against HTML mockup at `<linkedout-fe>/docs/design/session-history-new-search.html`

### Success Criteria
- [ ] Session switcher dropdown renders with session list
- [ ] Each session shows: query, status tag, relative time, result count, turn count
- [ ] Current session highlighted in dropdown
- [ ] "New Search" archives current session and resets UI
- [ ] Page load shows most recent active session (not empty search)
- [ ] Resume button on archived sessions loads results
- [ ] Active session label shows with dot + query + turn count
- [ ] `session_id` forwarded in search requests
- [ ] TypeScript compiles with no errors
- [ ] Visual match to HTML mockup

## Execution Notes

- The backend `GET /sessions/latest` returns 404 if no active session exists. Handle this gracefully (show empty hero).
- Session `result_snapshot` is a JSONB array. It may need conversion to `ProfileResult[]` -- check the actual backend response format.
- The `useSearchHistory.ts` hook is a legacy hook for search-histories. Session management uses the new `/sessions` endpoints, not the old `/search-histories` ones. Do not modify `useSearchHistory.ts`.
- Keep the hardcoded tenant/bu/user IDs consistent: `tenant_sys_001`, `bu_sys_001`, `usr_sys_001`.
- Session switcher click-outside-to-close: use a ref + `useEffect` with `mousedown` listener.
- If the backend sessions API returns a different shape than expected, adjust the TypeScript types to match.

**Spec-linked files:** Read `./docs/specs/search_sessions.collab.md` for exact session API behavior and response shapes.
