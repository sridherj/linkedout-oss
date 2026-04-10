# Sub-Phase 3: Frontend — Dashboard Page

**Goal:** linkedin-ai-production
**Phase:** 5b — Network Dashboard
**Depends on:** SP-1 (Backend: Aggregation Endpoints), Phase 4.5 (Design System — gate satisfied)
**Estimated effort:** 1-2h
**Source plan sections:** 3.1–3.7

---

## Objective

Build the Network Dashboard page in the Next.js frontend at `<linkedout-fe>/`. This is the landing page after first import, showing 7 aggregate widgets (enrichment progress, industry breakdown, seniority distribution, location top-10, top companies, affinity tiers, network sources) plus an empty state with illustration.

## Context

- **Frontend directory:** `<linkedout-fe>/` (symlinked at `./linkedout-fe/`)
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md` — read this FIRST before any UI decisions
- **Backend endpoint:** `GET /tenants/{tid}/bus/{bid}/dashboard` with `X-App-User-Id` header (from SP-1)
- **Chart library:** Recharts (React + shadcn-compatible, lightweight)
- Use `/ui-ux-pro-max` and `/frontend-design` skills for UI implementation (per reconciliation C13)

## Pre-Flight Checks

Before starting, verify:
- [ ] Next.js app scaffold exists at `<linkedout-fe>/` (from Phase 5a or create minimal scaffold)
- [ ] Backend `GET /dashboard` endpoint is functional (SP-1 complete)
- [ ] Design system doc exists at `<linkedout-fe>/docs/design/linkedout-design-system.md`
- [ ] Dashboard illustrations available: `illust-11` (header), `illust-12` (empty state) — if not, use placeholder boxes

## Files to Create

```
linkedout-fe/
  app/
    dashboard/
      page.tsx                         # Dashboard page (server component)
      components/
        enrichment-progress.tsx        # Enrichment bar (X/Y enriched)
        stat-card.tsx                  # Reusable aggregate card
        tier-chart.tsx                 # Affinity tier donut/bar
        top-list.tsx                   # Top companies / locations list
        industry-chart.tsx             # Industry horizontal bar chart
        seniority-chart.tsx            # Seniority horizontal bar chart
        source-pills.tsx              # Network source pills with counts
        empty-dashboard.tsx           # Empty state with illustration + CTA
```

---

## Step 1: Read the Design System

**MANDATORY:** Read `<linkedout-fe>/docs/design/linkedout-design-system.md` before writing any component. All font choices, colors, spacing, and aesthetic direction are defined there. Do not deviate without explicit approval.

---

## Step 2: Install Dependencies

If not already installed:
- `recharts` — chart library for bar charts, pie charts
- Verify TanStack Query (`@tanstack/react-query`) is installed for data fetching

---

## Step 3: Data Fetching Hook

Create a custom hook or inline TanStack Query call:

```typescript
// Fetch dashboard data from backend
const { data, isLoading, error } = useQuery({
  queryKey: ['dashboard', tenantId, buId],
  queryFn: () => fetchDashboard(tenantId, buId),
  staleTime: 5 * 60 * 1000, // 5 minutes
});
```

- Backend URL: `GET /tenants/{tid}/bus/{bid}/dashboard`
- Include `X-App-User-Id` header
- Stale time: 5 minutes (dashboard data changes slowly)

---

## Step 4: Component Implementation

### 4.1 Empty State (`empty-dashboard.tsx`)
When `total_connections == 0`:
- Show `illust-12` illustration (or placeholder)
- Headline: "Your network dashboard is waiting"
- Subtext: "Import your LinkedIn connections to see your network at a glance"
- CTA button: "Import Contacts" → links to import page

### 4.2 Enrichment Progress (`enrichment-progress.tsx`)
- Progress bar: "4,231 of 5,892 enriched (72%)"
- Green fill proportional to `enriched_pct`
- Use design system colors and spacing

### 4.3 Stat Card (`stat-card.tsx`)
- Reusable card component for displaying a single aggregate section
- Props: `title`, `children` (chart/list content)
- Consistent card styling per design system

### 4.4 Seniority Chart (`seniority-chart.tsx`)
- Horizontal `BarChart` (Recharts) showing IC → C-Suite hierarchy
- Data from `seniority_distribution`

### 4.5 Industry Chart (`industry-chart.tsx`)
- Horizontal `BarChart` (Recharts) showing top 10 industries
- Data from `industry_breakdown`

### 4.6 Tier Chart (`tier-chart.tsx`)
- Donut chart or 4-segment bar for affinity tiers
- Labels: Inner Circle / Active / Familiar / Acquaintance
- Data from `affinity_tier_distribution`

### 4.7 Top List (`top-list.tsx`)
- Reusable ordered list with count badges
- Used for top companies AND top locations
- Data from `top_companies` and `location_top`

### 4.8 Source Pills (`source-pills.tsx`)
- Small pill badges with counts (LinkedIn, Gmail, Google, etc.)
- Data from `network_sources`

---

## Step 5: Page Layout (`page.tsx`)

Responsive grid layout (per design spec):
- **Top row:** Total connections (large headline number) + Enrichment progress bar
- **Middle row:** 2-column grid — Affinity tiers (left) + Seniority distribution (right)
- **Bottom row:** 2-column grid — Top companies (left) + Top locations (right)
- **Footer row:** Industry breakdown (full width) + Network sources (pills)
- **Mobile:** Single column stack

### States:
- **Loading:** Skeleton cards per design spec
- **Error:** Retry button
- **Empty:** Empty state component (when `total_connections == 0`)
- **Data:** Full dashboard grid

---

## Step 6: Navigation Integration

- Dashboard is the default landing page after login
- Navigation: Dashboard (active) | Search | Import
- If no connections, show empty state (directs to import)
- Ensure navigation routing is consistent with Phase 5a (if it exists)

---

## What NOT to Build

- No interactive filters (that's Phase 5a search)
- No real-time updates (no WebSocket/SSE)
- No map visualization for locations (ordered list only)
- No drill-down (clicking company doesn't filter search)
- No time-series charts
- No team-level dashboard (Phase 6)

---

## Verification

- [ ] Dashboard renders with all 7 widgets showing correct data from backend
- [ ] Empty state renders with illustration + CTA when `total_connections == 0`
- [ ] Responsive layout: 2-column grid on desktop, single column on mobile
- [ ] TanStack Query caches data (no re-fetch on tab return within 5 min)
- [ ] Loading state shows skeleton cards
- [ ] Error state shows retry button
- [ ] Navigation routes to dashboard by default
- [ ] All styling matches design system (colors, fonts, spacing)
- [ ] No console errors in browser dev tools
