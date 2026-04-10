# Shared Context: LinkedOut Quality Frontend

## Source Documents
- Plan: `./docs/execution/linkedout-quality/fe_plan.md`
- Design System: `<linkedout-fe>/docs/design/linkedout-design-system.md`
- Intelligence Spec: `./docs/specs/linkedout_intelligence.collab.md`
- Sessions Spec: `./docs/specs/search_sessions.collab.md`
- Backend Contracts: `./src/linkedout/intelligence/contracts.py`

## Project Background

LinkedOut is an AI-powered warm network intelligence tool. Users search their own LinkedIn connections with natural language queries. The backend is fully implemented with 345 passing tests, including session persistence, multi-turn conversation, profile detail endpoints, and highlighted attributes on result cards.

This frontend phase builds 4 features on top of the existing Next.js/React frontend: enhanced result cards with LLM-driven highlight chips (FE4/SP1), session management (FE1/SP2a), profile slide-over panel (FE3/SP2b), and conversation thread UI (FE2/SP3). The backend APIs are live and tested -- the frontend consumes them.

## Codebase Conventions

- **Framework:** Next.js App Router, all page components are `"use client"` with Suspense boundary at page level
- **Styling:** Tailwind CSS with design system tokens (`berry-accent`, `bg-primary`, `text-primary`, `pastel-lavender`, `pastel-peach`, `pastel-sage`, etc.)
- **Data fetching:** TanStack React Query (`@tanstack/react-query`), `QueryClientProvider` in `<linkedout-fe>/src/app/providers.tsx`
- **API client:** `apiFetch<T>(path, options)` in `<linkedout-fe>/src/lib/api-client.ts` -- `NEXT_PUBLIC_API_URL` base
- **SSE streaming:** Custom `useStreamingSearch` hook at `<linkedout-fe>/src/hooks/useStreamingSearch.ts` -- `POST /api/search/stream` proxied via Next.js route handler to backend
- **Multi-tenancy:** Hardcoded `tenant_id: "tenant_sys_001"`, `bu_id: "bu_sys_001"`, `app_user_id: "usr_sys_001"`
- **Fonts:** Fraunces (serif, display/body/ui) + Fragment Mono (monospace, data/scores)
- **Icons:** lucide-react
- **UI primitives:** `<linkedout-fe>/src/components/ui/` -- `button.tsx`, `badge.tsx`, `input.tsx`, `card.tsx`
- **Toasts:** sonner (`toast.success`, `toast.error`)
- **Component naming:** PascalCase files, `"use client"` directive at top, functional components with named exports

## Key File Paths

| File | Role |
|------|------|
| `<linkedout-fe>/src/app/page.tsx` | Search page entry -- wraps `SearchPageContent` in `AppShell` + `Suspense` |
| `<linkedout-fe>/src/app/providers.tsx` | `QueryClientProvider` + `Toaster` |
| `<linkedout-fe>/src/app/layout.tsx` | Root layout with Fraunces + Fragment Mono fonts |
| `<linkedout-fe>/src/app/api/search/stream/route.ts` | SSE proxy to backend search endpoint |
| `<linkedout-fe>/src/components/search/SearchPageContent.tsx` | Main search page orchestrator (hero/thinking/results/enrichment) |
| `<linkedout-fe>/src/components/search/SearchBar.tsx` | Search input with Cmd+K, sticky positioning |
| `<linkedout-fe>/src/components/search/ResultsList.tsx` | Renders ProfileCard/ProfileCardUnenriched list with sorting, pagination |
| `<linkedout-fe>/src/components/search/FacetPanel.tsx` | Client-side facet filtering (location/company/seniority/function) |
| `<linkedout-fe>/src/components/search/ThinkingState.tsx` | Animated thinking indicator with 3 steps |
| `<linkedout-fe>/src/components/profile/ProfileCard.tsx` | Enriched profile card: avatar, name, badges (AffinityBadge, DunbarBadge), headline, location, role, why_this_person, footer |
| `<linkedout-fe>/src/components/profile/ProfileCardUnenriched.tsx` | Unenriched card: checkbox, initials avatar, name, role, enrich button |
| `<linkedout-fe>/src/components/profile/ProfileCardSkeleton.tsx` | Loading skeleton for cards |
| `<linkedout-fe>/src/components/profile/InitialsAvatar.tsx` | Generates colored initials avatar |
| `<linkedout-fe>/src/hooks/useStreamingSearch.ts` | SSE streaming hook with buffer + RAF flush + TanStack cache |
| `<linkedout-fe>/src/hooks/useSearchHistory.ts` | Legacy search history hook (GET search-histories) |
| `<linkedout-fe>/src/hooks/useEnrichment.ts` | Enrichment mutation hook |
| `<linkedout-fe>/src/types/search.ts` | `ProfileResult`, `SearchEvent`, `SearchEventType` types |
| `<linkedout-fe>/src/lib/api-client.ts` | `apiFetch<T>` with `ApiError` class |

## Data Schemas & Contracts

### ProfileResult (current frontend type)
```typescript
export interface ProfileResult {
  connection_id: string;
  crawled_profile_id: string;
  full_name: string;
  headline: string | null;
  current_position: string | null;
  current_company_name: string | null;
  location_city: string | null;
  location_country: string | null;
  linkedin_url: string | null;
  public_identifier: string | null;
  affinity_score: number | null;
  dunbar_tier: string | null;
  similarity_score: number | null;
  connected_at: string | null;
  has_enriched_data: boolean;
  why_this_person?: string | null;
}
```

### HighlightedAttribute (backend, needs frontend type)
```python
class HighlightedAttribute(BaseModel):
    text: str  # e.g. "IC -> PM in 18 mo"
    color_tier: int  # 0=lavender, 1=rose, 2=sage
```

### ProfileExplanation (backend, includes highlighted_attributes)
```python
class ProfileExplanation(BaseModel):
    explanation: str
    highlighted_attributes: list[HighlightedAttribute]  # max 3
```

### ConversationTurnResponse (backend)
```python
class ConversationTurnResponse(BaseModel):
    message: str
    result_summary_chips: list[ResultSummaryChip]  # {text, type: count|filter|sort|removal}
    suggested_actions: list[SuggestedAction]  # {type: narrow|rank|exclude|broaden|ask, label}
    exclusion_state: ExclusionState  # {excluded_count, excluded_description, undoable}
    result_metadata: ResultMetadata  # {count, sort_description}
    facets: list[FacetGroup]  # {group, items: [{label, count}]}
    results: list[SearchResultItem]
    query_type: str
    turn_transcript: list[dict]
```

### ProfileDetailResponse (backend, slide-over panel)
```python
class ProfileDetailResponse(BaseModel):
    connection_id: str
    crawled_profile_id: str
    full_name: str
    headline: Optional[str]
    current_position: Optional[str]
    current_company_name: Optional[str]
    location: Optional[str]
    linkedin_url: Optional[str]
    profile_image_url: Optional[str]
    has_enriched_data: bool
    why_this_person_expanded: Optional[str]
    key_signals: list[KeySignal]  # {icon, label, value, color_tier}
    experiences: list[ExperienceItem]  # {role, company, start_date, end_date, duration_months, is_current}
    education: list[EducationItem]  # {school, degree, field_of_study, start_year, end_year}
    skills: list[SkillItem]  # {name, is_featured}
    affinity: Optional[AffinityDetail]  # {score, tier, tier_description, sub_scores: [{name, value, max_value}]}
    connected_at: Optional[str]
    tags: list[str]
    suggested_questions: list[str]  # 3 items for Ask tab
```

### Session API Endpoints (route prefix: `/search-sessions`, NOT `/sessions`)
All require `X-App-User-Id` header.
- `GET /tenants/{tid}/bus/{bid}/search-sessions` -- paginated list (`{search_sessions: [...], total, limit, offset, page_count}`)
- `GET /tenants/{tid}/bus/{bid}/search-sessions/latest` -- most recent active (`{search_session: {...}}`, 404 if none)
- `GET /tenants/{tid}/bus/{bid}/search-sessions/{id}` -- single by ID
- `POST /tenants/{tid}/bus/{bid}/search-sessions` -- create new session
- `PATCH /tenants/{tid}/bus/{bid}/search-sessions/{id}` -- update session
- `PATCH /tenants/{tid}/bus/{bid}/search-sessions/{id}/turn` -- save turn data

### Profile Detail Endpoint
- `GET /tenants/{tid}/bus/{bid}/search/profile/{connection_id}` -- returns `ProfileDetailResponse` directly (no wrapper)
- Requires `X-App-User-Id` header
- Optional `?query=` param for skill relevance highlighting

### SSE Stream Events (current)
The search endpoint (`POST /tenants/{tid}/bus/{bid}/search`) streams these events:
1. `{"type": "thinking", "message": "Starting search..."}`
2. `{"type": "session", "payload": {"session_id": "..."}}`
3. `{"type": "result", "payload": {ProfileResult}}` (one per profile)
4. `{"type": "thinking", "message": "Generating explanations..."}`
5. `{"type": "explanations", "payload": {"connection_id": {"explanation": "...", "highlighted_attributes": [{text, color_tier}]}}}` — **structured objects, not plain strings**
6. `{"type": "done", "payload": {"total": N, "query_type": "...", "answer": "...", "session_id": "..."}}`
7. `{"type": "heartbeat"}` (sent during long waits)

**Note:** `ConversationTurnResponse` fields (`result_summary_chips`, `suggested_actions`, `exclusion_state`, `result_metadata`, `facets`) are NOT in the SSE stream yet. SP3 requires a backend change to wire these in.

## Pre-Existing Decisions

1. **DAG:** SP1 (result cards) first, then SP2a (sessions) and SP2b (profile panel) in parallel, then SP3 (conversation thread) after SP2a.
2. **Backend is done:** All APIs are implemented and tested. No backend changes needed.
3. **Use `/ui-ux-pro-max` skill** for all UI implementation work.
4. **Design system compliance:** Read the design system doc before any visual work. All colors must use design system tokens.
5. **Highlight chip colors:** color_tier 0 = lavender (pastel-lavender bg, #5B4A7A text), 1 = rose (pastel-peach bg, #8B4A5E text), 2 = sage (pastel-sage bg, #6B5A42 text).
6. **Slide-over responsive widths:** 520px default, 600px at >=1400px, 680px at >=1800px.
7. **Existing patterns must be preserved:** AffinityBadge/DunbarBadge in ProfileCard, apiFetch client, TanStack React Query, SSE streaming via useStreamingSearch.

## HTML Mockups

Each sub-phase has an HTML mockup that serves as the visual specification:

| Sub-phase | HTML Mockup Path |
|-----------|-----------------|
| SP1 (Result Cards) | `<linkedout-fe>/docs/design/result-cards-highlighted-attributes.html` |
| SP2a (Session Switcher) | `<linkedout-fe>/docs/design/session-history-new-search.html` |
| SP2b (Profile Slide-over) | `<linkedout-fe>/docs/design/profile-slideover-panel.html` |
| SP3 (Conversation Thread) | `<linkedout-fe>/docs/design/conversation-history-followup.html` |

## Relevant Specs
- `docs/specs/linkedout_intelligence.collab.md` -- intelligence module behavior, search flow, profile explanations, key signals
- `docs/specs/search_sessions.collab.md` -- session lifecycle, context engineering, session API behaviors

## Sub-Phase Dependency Summary

| Sub-phase | Type | Depends On | Blocks | Can Parallel With |
|-----------|------|-----------|--------|-------------------|
| SP1 (Result Cards) | Sub-phase | -- | SP2a, SP2b | -- |
| SP2a (Session Switcher) | Sub-phase | SP1 | SP3 | SP2b |
| SP2b (Profile Slide-over) | Sub-phase | SP1 | -- | SP2a |
| SP3 (Conversation Thread) | Sub-phase | SP2a | -- | -- |
