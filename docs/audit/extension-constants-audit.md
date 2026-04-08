# Extension Constants Audit

**Phase:** 4 — Constants Externalization
**Date:** 2026-04-08
**Status:** Complete

This audit catalogs every hardcoded constant in the Chrome extension codebase. Each constant includes its current value, purpose, fragility assessment, and a recommendation for Phase 4.

---

## Voyager Decoration IDs

> **WARNING:** These are LinkedIn internal API identifiers. They can change without notice when LinkedIn updates their API. Any change will break profile fetching or mutual connection extraction until the ID is updated. These MUST remain hardcoded (not user-configurable) but should be prominently documented so breakage is easy to diagnose.

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/lib/constants.ts` | 13-14 | `'com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93'` | Voyager decoration ID for full profile data — used by `fetchVoyagerProfile()` to request enriched profile JSON | **fragile** — LinkedIn can change the version suffix (`-93`) at any time | keep in constants.ts |
| `extension/lib/mutual/extractor.ts` | 15 | `'com.linkedin.voyager.dash.deco.search.SearchClusterCollection-186'` | Voyager decoration ID for search/clusters endpoint — used to fetch mutual connection search results | **fragile** — LinkedIn can change the version suffix (`-186`) at any time | keep in constants.ts |

**Breakage risk:** When LinkedIn bumps a decoration ID version, the Voyager API returns 400 or empty results. The extension should log the decoration ID in error messages to make debugging fast. Consider adding a version-check heuristic or fallback notification.

---

## System IDs (Single-User OSS)

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/lib/constants.ts` | 4 | `'tenant_sys_001'` | System tenant ID — sent in API paths | stable | keep in constants.ts |
| `extension/lib/constants.ts` | 5 | `'bu_sys_001'` | System business unit ID — sent in API paths | stable | keep in constants.ts |
| `extension/lib/constants.ts` | 6 | `'usr_sys_001'` | System user ID — sent in `X-App-User-Id` header | stable | keep in constants.ts |

These match `fixed_data.py` in the backend. Single-user OSS — not configurable per the shared context constraints.

---

## Rate Limiting & Timing

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/lib/constants.ts` | 9 | `2000` | PAGE_DELAY_MIN_MS — minimum random delay between page fetches (ms) | stable | externalize to config.ts |
| `extension/lib/constants.ts` | 10 | `5000` | PAGE_DELAY_MAX_MS — maximum random delay between page fetches (ms) | stable | externalize to config.ts |
| `extension/lib/config.ts` | 20 | `30` | hourlyLimit — max Voyager fetches per hour | stable | already externalized (config.ts DEFAULTS, overridable via storage) |
| `extension/lib/config.ts` | 21 | `150` | dailyLimit — max Voyager fetches per day | stable | already externalized (config.ts DEFAULTS, overridable via storage) |
| `extension/lib/rate-limiter.ts` | 36 | `60 * 60 * 1000` | One hour in milliseconds (derived, not a constant) | stable | keep inline (arithmetic clarity) |
| `extension/lib/rate-limiter.ts` | 37 | `24 * 60 * 60 * 1000` | One day in milliseconds (derived, not a constant) | stable | keep inline (arithmetic clarity) |

---

## Freshness & Staleness

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/lib/config.ts` | 19 | `30` | stalenessDays — number of days after which a cached profile is considered stale and re-fetched | stable | already externalized (config.ts DEFAULTS, overridable via storage) |
| `extension/lib/backend/client.ts` | 99 | `stalenessDays + 1` | Fallback staleness when `last_crawled_at` is null — treats missing timestamp as stale | stable | keep inline (derives from config) |

---

## Backend API Configuration

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/lib/config.ts` | 18 | `'http://localhost:8001'` | Default backend URL (fallback when VITE_BACKEND_URL not set) | stable | already externalized (config.ts DEFAULTS, VITE_BACKEND_URL build var, overridable via storage) |
| `extension/lib/backend/client.ts` | 40-43 | `{'Content-Type': 'application/json', 'X-App-User-Id': APP_USER_ID}` | Default request headers | stable | keep inline (structural, not configurable) |
| `extension/lib/backend/client.ts` | 86 | `'1'` | limit parameter for freshness check | stable | keep inline (functional, always 1) |
| `extension/lib/backend/client.ts` | 144 | `20` | Default limit for getRecentActivity() | stable | externalize to config.ts |

---

## Mutual Connection Extraction

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/lib/mutual/extractor.ts` | 13 | `10` | PAGE_SIZE — results per Voyager search page | **fragile** — LinkedIn could change their pagination size | keep in constants.ts (must match LinkedIn's API) |
| `extension/lib/mutual/extractor.ts` | 14 | `10` | MAX_PAGES — maximum pages to scrape for mutual connections | stable | externalize to config.ts |
| `extension/lib/mutual/extractor.ts` | 117 | `1000 + Math.random() * 1500` | First-page delay (1000-2500ms) — shorter than normal delay for first request | stable | externalize to config.ts (or derive from PAGE_DELAY_MIN_MS) |

---

## Content Script Constants

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/entrypoints/voyager.content.ts` | 41 | `500` | URL_DEBOUNCE_MS — debounce timer for SPA navigation detection (ms) | stable | externalize to config.ts |
| `extension/entrypoints/voyager.content.ts` | 129 | `1 \| 2 \| 4 \| 8` | Extraction speed multiplier options | stable | keep inline (type constraint, not configurable) |
| `extension/entrypoints/voyager.content.ts` | 19-27 | `'linkedout:url-changed'`, etc. | Custom DOM event names for MAIN ↔ bridge communication | stable | keep inline (structural protocol constants) |

---

## Activity Log

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/lib/log.ts` | 7 | `200` | MAX_ENTRIES — maximum activity log entries in browser.storage.local | stable | externalize to config.ts |
| `extension/lib/log.ts` | 6 | `'activityLog'` | STORAGE_KEY — browser.storage.local key for log entries | stable | keep inline (internal storage key) |

---

## Storage Keys

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/lib/rate-limiter.ts` | 6 | `'rateLimitTimestamps'` | Storage key for rate limit timestamps | stable | keep inline (internal storage key) |
| `extension/lib/log.ts` | 6 | `'activityLog'` | Storage key for activity log entries | stable | keep inline (internal storage key) |
| `extension/lib/config.ts` | 30 | `'linkedout_config'` | Storage key for runtime config overrides | stable | keep inline (internal storage key) |

---

## Voyager API Details

| File | Line | Value | Description | Fragility | Recommendation |
|------|------|-------|-------------|-----------|----------------|
| `extension/lib/voyager/client.ts` | 44 | `'https://www.linkedin.com/voyager/api/identity/dash/profiles'` | Voyager profile API base URL | **fragile** — LinkedIn could change their internal API paths | keep inline (tightly coupled to LinkedIn implementation) |
| `extension/lib/voyager/client.ts` | 51 | `'application/vnd.linkedin.normalized+json+2.1'` | Voyager Accept header value | **fragile** — LinkedIn could change their response format version | keep inline |
| `extension/lib/voyager/client.ts` | 29 | `JSESSIONID` cookie regex | CSRF token extraction pattern from LinkedIn cookies | **fragile** — LinkedIn could change session cookie format | keep inline |
| `extension/lib/mutual/extractor.ts` | 125 | `'https://www.linkedin.com/voyager/api/search/dash/clusters'` | Voyager search API base URL | **fragile** | keep inline |
| `extension/lib/mutual/extractor.ts` | 127-130 | `'MEMBER_PROFILE_CANNED_SEARCH'`, `'SEARCH_SRP'`, etc. | Voyager search query parameter constants | **fragile** | keep inline |
| `extension/lib/mutual/extractor.ts` | 137 | `'application/vnd.linkedin.normalized+json+2.1'` | Voyager search Accept header | **fragile** | keep inline |

---

## Summary

### What goes to `config.ts` (externalize)

These constants should be moved to the `ExtensionConfig` interface in `config.ts` with defaults matching current values, overridable via `browser.storage.local`:

1. `PAGE_DELAY_MIN_MS` (2000) — from constants.ts
2. `PAGE_DELAY_MAX_MS` (5000) — from constants.ts
3. `MAX_PAGES` (10) — from mutual/extractor.ts
4. `MAX_ENTRIES` (200) — from log.ts
5. `URL_DEBOUNCE_MS` (500) — from voyager.content.ts
6. `getRecentActivity` default limit (20) — from backend/client.ts
7. First-page delay base (1000) and range (1500) — from mutual/extractor.ts

### What stays in `constants.ts`

These are true constants that should never be configured at runtime:

1. `TENANT_ID`, `BU_ID`, `APP_USER_ID` — system identity (single-user OSS)
2. `VOYAGER_DECORATION_ID` — LinkedIn internal (fragile, but not user-tunable)

### What stays inline

These are structural/protocol constants that are implementation details:

1. DOM event names (`linkedout:url-changed`, etc.)
2. Storage keys (`rateLimitTimestamps`, `activityLog`, `linkedout_config`)
3. Request headers and content types
4. Voyager API URLs and query parameters (fragile LinkedIn internals)
5. Speed multiplier type constraint (`1 | 2 | 4 | 8`)
6. Arithmetic time constants (`60 * 60 * 1000`)
7. Mutual extractor `PAGE_SIZE` (10) — must match LinkedIn's pagination

### Already externalized in `config.ts`

1. `backendUrl` — `'http://localhost:8001'` (VITE_BACKEND_URL override)
2. `stalenessDays` — `30`
3. `hourlyLimit` — `30`
4. `dailyLimit` — `150`

### Fragility Summary

| Fragility | Count | Notes |
|-----------|-------|-------|
| **fragile** | 8 | Voyager decoration IDs (2), API URLs (2), Accept headers (2), CSRF pattern (1), search params (1) |
| stable | 24 | All other constants |
| **Total** | **32** |

All fragile constants are LinkedIn internal API details. They cannot be user-configured (wrong values break everything), but should be:
1. Prominently documented with breakage symptoms
2. Logged in error messages when failures occur
3. Easy to find and update (kept together in constants.ts or at file top)
