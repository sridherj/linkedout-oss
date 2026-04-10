# Sub-phase 2b: Profile Slide-Over Panel

> **Pre-requisite:** Read `./docs/execution/linkedout-quality-fe/_shared_context.md` before starting this sub-phase.

## Objective

Build a profile slide-over panel that opens when a user clicks a result card. The panel fetches detailed profile data via `GET /search/profile/{connection_id}` and renders 4 tabs (Overview, Experience, Affinity, Ask) with an always-visible "Ask about {name}" footer input. Non-selected result cards dim to 0.45 opacity when the panel is open. This is the primary deep-dive UI for understanding a profile match.

## Dependencies
- **Requires completed:** SP1 (Result Cards) -- cards must have `onClick` prop and `selectedProfileId` state in `SearchPageContent`
- **Assumed codebase state:** `ProfileCard` has `onClick`, `SearchPageContent` has `selectedProfileId` state, `ProfileResult` type has `highlighted_attributes`

## Scope
**In scope:**
- Create `ProfileSlideOver.tsx` panel component with shell, header, tabs, body, footer
- Create tab content components: `OverviewTab.tsx`, `ExperienceTab.tsx`, `AffinityTab.tsx`, `AskTab.tsx`
- Create `useProfileDetail.ts` hook (TanStack React Query)
- Create TypeScript types for profile detail response
- Wire panel open/close into `SearchPageContent` using `selectedProfileId` state from SP1
- Dim non-selected cards to 0.45 opacity when panel is open
- Panel animation: slide in from right, 0.25s ease-out
- Close: X button, click-outside, Escape key
- Responsive widths: 520px default, 600px at >=1400px, 680px at >=1800px
- Visually match HTML mockup at `<linkedout-fe>/docs/design/profile-slideover-panel.html`

**Out of scope (do NOT do these):**
- Session management (SP2a)
- Conversation thread (SP3)
- Backend changes
- Modifying ProfileCard styling (already done in SP1)
- Ask tab sending actual questions to the backend (wire the UI, but the actual question flow can be a follow-up)

## Files to Create/Modify

| File | Action | Current State |
|------|--------|---------------|
| `<linkedout-fe>/src/types/profile-detail.ts` | Create | Does not exist |
| `<linkedout-fe>/src/hooks/useProfileDetail.ts` | Create | Does not exist |
| `<linkedout-fe>/src/components/profile/ProfileSlideOver.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/profile/tabs/OverviewTab.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/profile/tabs/ExperienceTab.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/profile/tabs/AffinityTab.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/profile/tabs/AskTab.tsx` | Create | Does not exist |
| `<linkedout-fe>/src/components/search/SearchPageContent.tsx` | Modify | Has `selectedProfileId` state from SP1 |
| `<linkedout-fe>/src/components/search/ResultsList.tsx` | Modify | Needs dimming logic when panel is open |

## Detailed Steps

### Step 2b.1: Create Profile Detail Types

Create `<linkedout-fe>/src/types/profile-detail.ts`:

```typescript
export interface KeySignal {
  icon: string;        // emoji or icon name
  label: string;       // short uppercase label
  value: string;       // full sentence explanation
  color_tier: number;  // 0=purple, 1=rose, 2=sage
}

export interface ExperienceItem {
  role: string;
  company: string;
  start_date: string | null;
  end_date: string | null;
  duration_months: number | null;
  is_current: boolean;
  company_industry: string | null;
  company_size_tier: string | null;
}

export interface EducationItem {
  school: string;
  degree: string | null;
  field_of_study: string | null;
  start_year: number | null;
  end_year: number | null;
}

export interface SkillItem {
  name: string;
  is_featured: boolean;
}

export interface AffinitySubScore {
  name: string;
  value: number;
  max_value: number;
}

export interface AffinityDetail {
  score: number | null;
  tier: string | null;
  tier_description: string | null;
  sub_scores: AffinitySubScore[];
}

export interface ProfileDetailResponse {
  connection_id: string;
  crawled_profile_id: string;
  full_name: string;
  headline: string | null;
  current_position: string | null;
  current_company_name: string | null;
  location: string | null;
  linkedin_url: string | null;
  profile_image_url: string | null;
  has_enriched_data: boolean;
  why_this_person_expanded: string | null;
  key_signals: KeySignal[];
  experiences: ExperienceItem[];
  education: EducationItem[];
  skills: SkillItem[];
  affinity: AffinityDetail | null;
  connected_at: string | null;
  tags: string[];
  suggested_questions: string[];
}
```

### Step 2b.2: Create useProfileDetail Hook

Create `<linkedout-fe>/src/hooks/useProfileDetail.ts`:

```typescript
"use client";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { ProfileDetailResponse } from "@/types/profile-detail";

const TENANT_ID = "tenant_sys_001";
const BU_ID = "bu_sys_001";

export function useProfileDetail(connectionId: string | null) {
  return useQuery({
    queryKey: ["profile-detail", connectionId],
    queryFn: () =>
      apiFetch<ProfileDetailResponse>(
        `/tenants/${TENANT_ID}/bus/${BU_ID}/search/profile/${connectionId}`
      ),
    enabled: !!connectionId,
    staleTime: 5 * 60 * 1000,  // 5 min cache
  });
}
```

### Step 2b.3: Create ProfileSlideOver Shell

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/profile/ProfileSlideOver.tsx`

Design from HTML mockup (`profile-slideover-panel.html`):

**Structure:**
```
[Backdrop (fixed, inset-0, bg-black/20, backdrop-blur-[1px])]
[Panel (fixed, top-0 right-0 bottom-0, width varies)]
  [Header]
    [Identity: 52px avatar + name + headline + location + connected_at]
    [Badges: AffinityBadge + DunbarBadge]
    [Actions: LinkedIn button + Close button]
    [Tabs: Overview | Experience | Affinity | Ask (with "New" badge)]
  [Body (flex-1, overflow-y-auto)]
    [Tab content]
  [Footer (sticky bottom)]
    [Ask input + send button + suggestion chips]
```

**Key CSS:**
- Panel width: `w-[min(520px,90vw)]`, `@media(min-width:1400px) w-[min(600px,42vw)]`, `@media(min-width:1800px) w-[min(680px,38vw)]`
- Animation: `@keyframes slideIn { from { transform: translateX(40px); opacity: 0 } to { transform: translateX(0); opacity: 1 } }` with `animate-[slideIn_0.25s_ease-out]`
- Panel: `bg-bg-surface border-l border-border shadow-[-8px_0_32px_rgba(168,122,208,0.08)]`
- Close: X button in bg-subtle rounded-md, hover bg-pastel-peach
- Scrollbar styling for panel body

Props:
```typescript
interface ProfileSlideOverProps {
  connectionId: string;
  onClose: () => void;
}
```

Internal state: `activeTab: "overview" | "experience" | "affinity" | "ask"` defaulting to `"overview"`.

Fetch data via `useProfileDetail(connectionId)`. Show loading skeleton while fetching, error state for failures.

After delegation, review:
- Animation works (slide in from right)
- Close works via X button, click-backdrop, Escape key
- Tabs switch content
- Responsive widths at breakpoints
- Ask footer always visible regardless of tab

### Step 2b.4: Create Overview Tab

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/profile/tabs/OverviewTab.tsx`

Sections from mockup:
1. **Why This Person** -- accent-left-border box:
   - `border-l-[3px] border-berry-accent bg-berry-accent-light rounded-[10px] px-3.5 py-3`
   - Section label: `font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-tertiary`
   - Uses `why_this_person_expanded`

2. **Key Signals** (labeled "AI") -- expanded rows:
   - Each signal: icon (28px rounded-md box) + label (mono uppercase) + value (full sentence)
   - Color-coded by `color_tier`: 0=pastel-lavender, 1=pastel-peach, 2=pastel-sage
   - Border row with hover: `border border-border rounded-lg p-2.5 hover:border-pastel-lavender-mid`

3. **Experience Timeline** -- vertical line + dots:
   - First item: dot with accent border + accent-light bg
   - Other items: dot with border-border bg
   - Connecting line: 1px solid border between dots
   - Current role: "Current" badge (pastel-mint bg)

4. **Education** -- school icon + name + degree + dates

5. **Skills** -- grid of tags:
   - Featured skills: `bg-pastel-lavender text-[#5B4A7A] border-pastel-lavender-mid`
   - Regular skills: `bg-bg-subtle text-text-secondary border-border`

### Step 2b.5: Create Experience Tab

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/profile/tabs/ExperienceTab.tsx`

Full career timeline. Same visual pattern as Overview tab's experience section but with more detail:
- Company industry and size tier shown
- Duration in months converted to "X yr Y mo" format
- Current role highlighted

### Step 2b.6: Create Affinity Tab

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/profile/tabs/AffinityTab.tsx`

From mockup:
1. **Large affinity score:** `font-mono text-[2.5rem] text-berry-accent` + "/100" label
2. **Sub-score breakdown:** Horizontal bars:
   - Label + value on top row
   - 4px track (bg-subtle) with fill (berry-accent) animated
   - Width = `(value / max_value) * 100%`
3. **Dunbar tier info box:** pastel-lavender bg, explains the tier

### Step 2b.7: Create Ask Tab

-> Delegate: `/ui-ux-pro-max` -- Create `<linkedout-fe>/src/components/profile/tabs/AskTab.tsx`

Content area for Ask tab. For now, shows the 3 suggestion chips from `suggested_questions`. Clicking a chip populates the footer input.

The Ask footer input is rendered by `ProfileSlideOver.tsx` itself (always visible regardless of tab), not by `AskTab.tsx`. The tab content just shows suggestion chips and any future conversation.

### Step 2b.8: Wire Panel into SearchPageContent

Edit `<linkedout-fe>/src/components/search/SearchPageContent.tsx`:

1. Import `ProfileSlideOver`
2. Use `selectedProfileId` state (already added in SP1)
3. Render panel conditionally:
   ```tsx
   {selectedProfileId && (
     <ProfileSlideOver
       connectionId={selectedProfileId}
       onClose={() => setSelectedProfileId(null)}
     />
   )}
   ```

### Step 2b.9: Dim Cards When Panel Open

Edit `<linkedout-fe>/src/components/search/ResultsList.tsx`:

1. Add `selectedProfileId?: string | null` to `ResultsListProps`
2. Pass `className` to cards when panel is open:
   - Selected card: `border-berry-accent shadow-[0_0_0_2px_theme(colors.berry-accent-light)]`
   - Non-selected cards: `opacity-[0.45]`
3. Wrap each card in a div with conditional opacity

## Verification

### Automated Tests (permanent)

No new test files (visual verification).

### Validation Scripts (temporary)

```bash
cd <linkedout-fe> && npx tsc --noEmit
cd <linkedout-fe> && npm run dev
```

### Manual Checks

1. Click a result card -- panel slides in from right
2. Panel header shows: large avatar, name, headline, location, badges, LinkedIn link, close button
3. Overview tab: why_this_person_expanded, key signals (3 rows, color-coded), experience timeline, education, skills
4. Experience tab: full timeline with connecting lines and "Current" badge
5. Affinity tab: large score, sub-score bars, Dunbar tier info
6. Ask tab: suggestion chips render
7. Footer "Ask about {name}" input is visible on all tabs
8. Close panel: X button, click backdrop, Escape key
9. Non-selected cards dim to 0.45, selected card has accent border + shadow
10. Resize browser: panel width changes at 1400px and 1800px breakpoints
11. Compare visually against `<linkedout-fe>/docs/design/profile-slideover-panel.html`

### Success Criteria
- [ ] Panel slides in with 0.25s ease-out animation
- [ ] All 4 tabs render with correct data from `ProfileDetailResponse`
- [ ] Key signals color-coded by `color_tier`
- [ ] Experience timeline has vertical connecting lines and "Current" badge
- [ ] Affinity sub-score bars animate
- [ ] Ask footer input always visible
- [ ] Suggestion chips in Ask tab populate footer input on click
- [ ] Cards dim to 0.45 when panel open, selected card highlighted
- [ ] Close via X, backdrop click, Escape
- [ ] Responsive widths: 520px / 600px / 680px at breakpoints
- [ ] Loading skeleton while fetching profile detail
- [ ] TypeScript compiles with no errors
- [ ] Visual match to HTML mockup

## Execution Notes

- The backend endpoint path may be `/search/profile/{connection_id}` or `/intelligence/profile/{connection_id}`. Check the backend routes by reading `./src/linkedout/intelligence/controllers/search_controller.py`.
- The `profile_image_url` field may be null for most profiles. Fall back to `InitialsAvatar` (reuse from `ProfileCard.tsx`).
- Key signals `icon` field contains emoji strings (e.g., "🎯"). Render as-is in the icon box.
- The Ask tab's "send question" functionality can be a stub for now -- log to console or show a toast. Full wiring comes with conversation integration.
- Escape key handler: add `useEffect` with `keydown` listener, check `e.key === "Escape"`.
- Backdrop click: `onClick` on backdrop div calls `onClose`. Panel click needs `e.stopPropagation()`.
- The `tabs/` directory is new. Create it: `<linkedout-fe>/src/components/profile/tabs/`.

**Spec-linked files:** Read `./docs/specs/linkedout_intelligence.collab.md` sections on profile detail response for exact field semantics.
