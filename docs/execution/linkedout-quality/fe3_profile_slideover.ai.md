# FE3: Profile Slide-Over Panel

## Context
Backend profile detail endpoint is complete (SP6b). `GET /search/profile/{connection_id}` returns a `ProfileDetailResponse` with 4 tab sections: Overview, Experience, Affinity, Ask. This sub-phase builds the slide-over panel that opens when a user clicks a result card.

## Important: File Resolution
- **Frontend code lives at:** `<linkedout-fe>`
- **Backend code and specs live at:** `.` (also accessible via `.`)
- If a referenced file is not found at one location, check `.`, `.`, or `<prior-project>`
- **Leverage the `/ui-ux-pro-max` skill** for all UI implementation work

## Design Reference
- **HTML mockup:** `<linkedout-fe>/docs/design/profile-slideover-panel.html`
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md`

## Backend Contracts
- **Endpoint:** `GET /search/profile/{connection_id}` → `ProfileDetailResponse`
- **ProfileDetailResponse:** `./src/linkedout/intelligence/contracts.py`
  - `overview`: why_this_person_expanded, key_signals (icon + label + value, color-coded), experience_timeline, education, skills (featured in accent)
  - `experience`: full chronological list with company, title, dates, duration, is_current
  - `affinity`: score (float), tier, tier_description, sub_scores [{name, value, max_value}]
  - `ask`: suggested_questions (3 profile-specific, query-aware)
- **Profile tool:** `./src/linkedout/intelligence/tools/profile_tool.py`
- **Intelligence spec:** `./docs/specs/linkedout_intelligence.collab.md`

## Frontend Patterns (match these)
- **API client:** `<linkedout-fe>/src/lib/api-client.ts` — `apiFetch<T>(path, options)`
- **Data fetching:** TanStack React Query — use `useQuery` for profile detail fetch on card click
- **UI primitives:** `<linkedout-fe>/src/components/ui/` — button, badge, input, card
- **Styling:** Tailwind with design system tokens. Existing badge styles in ProfileCard: `DUNBAR_STYLES` map with pastel-lavender, pastel-sage, pastel-peach, bg-subtle
- **AffinityBadge:** already exists in ProfileCard.tsx (score-based color tiers: pastel-mint, pastel-peach, bg-subtle)
- **DunbarBadge:** already exists in ProfileCard.tsx
- **InitialsAvatar:** `<linkedout-fe>/src/components/profile/InitialsAvatar.tsx`

## Existing Frontend Files to Reference
- `<linkedout-fe>/src/components/profile/ProfileCard.tsx` — has avatar, name, badges (AffinityBadge, DunbarBadge), headline, location, why_this_person box, footer. Click handler needs to trigger slide-over
- `<linkedout-fe>/src/components/profile/ProfileCardUnenriched.tsx` — unenriched variant, reference for dimmed styling
- `<linkedout-fe>/src/components/profile/ProfileCardSkeleton.tsx` — loading skeleton pattern
- `<linkedout-fe>/src/components/search/ResultsList.tsx` — renders list of ProfileCard/ProfileCardUnenriched. Cards need to dim when panel open
- `<linkedout-fe>/src/types/search.ts` — `ProfileResult` type (needs extending for profile detail)

## Activities

### FE3.1 Slide-Over Shell & Animation
- New component: `ProfileSlideOver.tsx` in `<linkedout-fe>/src/components/profile/`
- Fixed panel on right side: 520px default, 600px on ≥1400px viewport, 680px on ≥1800px viewport
- Slides in with 0.25s ease-out animation
- Backdrop overlay on rest of page
- Non-selected result cards dim to 0.45 opacity
- Close button (X) in panel header + click-outside-to-close + Escape key

### FE3.2 Panel Header
- Large avatar (52px), name, headline
- Location + connected date
- Affinity score badge + Dunbar tier badge
- LinkedIn external link
- Close button

### FE3.3 Tab Navigation
- 4 tabs: Overview | Experience | Affinity | Ask
- "Ask" tab marked with "New" badge
- Tabs persist scroll position when switching

### FE3.4 Overview Tab
1. **Why This Person** — expanded version with accent-left-border, full paragraph including network proximity reasoning
2. **Key Signals** (labeled "AI") — 3 expanded rows: icon + label (mono uppercase) + value (full sentence). Color-coded backgrounds: purple (color_tier 0), rose (color_tier 1), sage (color_tier 2)
3. **Experience Timeline** — full chronological list, vertical line connecting dots, current role with "Current" badge
4. **Education** — school icon + name + degree + dates
5. **Skills** — grid of tags, featured skills in accent color

### FE3.5 Experience Tab
- Full career timeline with company logos (if available), title, dates, duration
- Current role highlighted with "Current" badge
- Vertical connecting line between entries

### FE3.6 Affinity Tab
- Large affinity score number (2.5rem, accent color)
- Sub-score breakdown as horizontal bars with labels and values
- Dunbar tier info box explaining the tier

### FE3.7 Ask Tab & Footer Input
- "Ask about {name}" input field + send button — **always visible in panel footer** regardless of active tab
- 3 suggestion chips from `suggested_questions` (clickable, populate input)
- Questions route through existing search/conversation endpoint
- Responses appear inline in the Ask tab

### FE3.8 API Integration
- Fetch profile detail on card click: `GET /search/profile/{connection_id}`
- Loading skeleton while fetching
- Error state for failed fetches

## Verification
- [ ] Panel slides in/out with animation
- [ ] All 4 tabs render with correct data
- [ ] Cards dim when panel is open
- [ ] Ask input is always visible in footer
- [ ] Responsive widths work at 1400px and 1800px breakpoints
- [ ] Design matches HTML mockup at `<linkedout-fe>/docs/design/profile-slideover-panel.html`
- [ ] Follows design system at `<linkedout-fe>/docs/design/linkedout-design-system.md`
