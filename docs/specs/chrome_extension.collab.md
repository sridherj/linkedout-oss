---
feature: Chrome Extension
module: extension
linked_files:
  - extension/entrypoints/background.ts
  - extension/entrypoints/voyager.content.ts
  - extension/entrypoints/bridge.content.ts
  - extension/entrypoints/sidepanel/App.tsx
  - extension/entrypoints/sidepanel/components/
  - extension/entrypoints/options/App.tsx
  - extension/lib/voyager/client.ts
  - extension/lib/voyager/parser.ts
  - extension/lib/voyager/types.ts
  - extension/lib/backend/client.ts
  - extension/lib/backend/search.ts
  - extension/lib/backend/types.ts
  - extension/lib/profile/mapper.ts
  - extension/lib/profile/url.ts
  - extension/lib/profile/current-user.ts
  - extension/lib/mutual/extractor.ts
  - extension/lib/rate-limiter.ts
  - extension/lib/config.ts
  - extension/lib/settings.ts
  - extension/lib/log.ts
  - extension/lib/messages.ts
  - extension/lib/constants.ts
  - extension/wxt.config.ts
  - extension/package.json
version: 1
last_verified: "2026-04-09"
---

# Chrome Extension

## Intent

The LinkedOut Chrome Extension enriches LinkedIn profiles by extracting structured data via LinkedIn's Voyager API and saving it to the LinkedOut backend. It operates as a Chrome side panel with two enrichment modes (auto and manual), respects self-imposed rate limits to avoid LinkedIn detection, and provides a "Best Hop" feature that finds optimal introduction paths through mutual connections. Built with the WXT framework (v0.20) using React 19 for the side panel and options page UI.

---

## Behaviors

### WXT Framework Setup

**Manifest V3 via WXT**: The extension uses WXT (`wxt.config.ts`) which generates a Manifest V3 Chrome extension. The `@wxt-dev/module-react` module enables React JSX in entrypoints. Permissions declared: `sidePanel`, `storage`, `activeTab`, `tabs`. Host permission: `https://www.linkedin.com/*`. Verify the manifest is generated correctly by running `wxt build`.

**Entrypoint conventions**: WXT auto-discovers entrypoints by filename convention. `background.ts` becomes the service worker. `voyager.content.ts` injects as a MAIN world content script. `bridge.content.ts` injects as an ISOLATED world content script. `sidepanel/` and `options/` directories each have `index.html` + `main.tsx` + `App.tsx`. Verify all entrypoints are recognized by WXT via `defineBackground`, `defineContentScript`, or directory structure.

**Content script matching**: Both content scripts match `*://www.linkedin.com/in/*`. The MAIN world script (`voyager.content.ts`) explicitly sets `world: 'MAIN'` and `runAt: 'document_idle'`. The ISOLATED world script (`bridge.content.ts`) defaults to ISOLATED world and also runs at `document_idle`. Verify both scripts inject on LinkedIn profile pages.

### Enrichment Trigger Model

**Display/Enrich split**: Every profile navigation triggers two concerns: (1) **Display** — always fetch Voyager data and show the profile card in the side panel, regardless of mode, and (2) **Enrich** — save to backend, gated by enrichment mode. The content script always fetches Voyager data autonomously when it detects a profile page. The service worker decides whether to enrich based on mode.

**Auto mode navigation trigger**: User enables auto mode via the header toggle. User navigates to a LinkedIn profile page. The content script fetches Voyager data, the service worker displays the profile and automatically saves to backend. Verify the profile appears in the backend with `data_source: 'extension'`.

**Manual mode navigation trigger**: User is in manual mode (default). User navigates to a LinkedIn profile page. The content script fetches Voyager data while the service worker simultaneously runs a freshness check against the backend (`GET /crawled-profiles?linkedin_url=...`). No backend write occurs. The side panel shows the profile card with the correct badge: "Not saved" with a "Save to LinkedOut" button (profile not in backend), "Up to date" (profile fresh within configurable staleness threshold, default 30 days), or "Stale" with an "Update Profile" button (profile older than threshold). Verify the freshness check runs in parallel with the Voyager fetch (started at `URL_CHANGED` time, consumed in `processVoyagerData`) and the correct badge appears without a flash.

**Manual mode fetch button**: User clicks "Fetch" on a displayed profile in manual mode. The service worker enriches to backend using the already-parsed Voyager data from `lastParsedResult` cache (no re-fetch from LinkedIn). Verify the profile is saved and the status transitions to "Saved today" without an additional Voyager API call.

**Side panel open trigger**: User opens the side panel while on a LinkedIn profile page, in either mode. The side panel establishes a port via `browser.runtime.connect({ name: 'sidepanel' })`. If the service worker has a cached `lastParsedResult` for the current profile, it sends it immediately with the resolved freshness status. Otherwise, it queries the active tab URL and sends `fetching` status. Verify the side panel populates with profile data regardless of enrichment mode. Error hardening state (offline, challenge) is also re-sent on connect.

**Full-page navigation sync**: User clicks a link that triggers a full page navigation. The old content script is destroyed with the page. The new content script injects at `document_idle`, detects the profile URL, and calls `handleUrlChange(location.href)`. The service worker's `tabs.onUpdated` listener detects URL changes as a fallback (in case the content script is slow) and clears stale side panel state so the user sees a loading skeleton. Verify the side panel updates to the new profile after a full-page navigation.

**SPA navigation detection**: User navigates between LinkedIn profiles via in-page navigation (no full page reload). The MAIN world content script detects URL changes via monkey-patched `history.pushState`/`replaceState` and a `popstate` listener, with configurable debounce (default 500ms via `config.urlDebounceMs`). The content script fetches Voyager data and reports to the service worker. Verify the side panel updates to the new profile.

**Rapid navigation debounce**: User navigates quickly between multiple profiles. The content script debounces URL changes (500ms default). The `debouncedUrlChange` function resets the `lastFetchedProfileId` dedup on each call so the final navigation always fetches. The service worker cancels in-flight pipeline operations via `cancelPipeline()` on each navigation and drops stale Voyager responses (profileId mismatch check in `processVoyagerData`). Verify only the last profile's data appears in the side panel.

**Tabs.onUpdated fallback**: The service worker registers a `browser.tabs.onUpdated` listener that fires on URL changes for the active tab. This catches SPA navigations that the content script might miss (timing, guard). It only fires if the URL differs from `currentTabUrl` to avoid double-processing. Verify this fallback keeps the side panel in sync even if the content script is slow to report.

> Edge: Double injection is prevented via a `window.__linkedout` flag in MAIN world. If the content script is injected twice, the second injection is a no-op.

> Edge: `tabs.onUpdated` fires before the new content script is ready on full-page navigations. The service worker must NOT attempt to trigger a fetch via the content script from this listener — it only updates state and clears the side panel. The content script triggers its own fetch when ready.

### Rate Limiting

**Hourly limit enforcement**: The extension tracks Voyager API calls using ISO timestamps in `chrome.storage.local` under key `rateLimitTimestamps`. When hourly count reaches the configurable limit (default 30), further enrichment is blocked. The `canProceed()` function counts timestamps within the last 60 minutes. Verify the profile shows "Rate limited" badge and no backend write occurs.

**Daily limit enforcement**: Same timestamp array as hourly, with a configurable daily cap (default 150). When daily count reaches the limit, further enrichment is blocked even if the hourly window has room. The `canProceed()` function checks both limits. Verify the extension remains blocked until timestamps age out.

**Rate limit display**: The side panel shows two side-by-side progress bars (hourly and daily) via `RateLimitBar` component with Fragment Mono counts. Bar color thresholds: green below 50%, yellow at 50-80%, red above 80% (determined by `getColor()` function). Verify the bars update after each enrichment operation via `RATE_LIMIT_UPDATE` messages.

**Sliding window pruning**: The `record()` function prunes timestamps older than 24 hours on each call. The `canProceed()` function counts within 1-hour and 24-hour windows. Verify that after waiting one hour, the hourly counter resets while daily counter retains unexpired entries.

> Edge: Rate limit state persists across browser restarts via `chrome.storage.local`. Reopening the browser does not reset counters.

> Edge: Rate limits gate backend enrichment only, not Voyager fetches. The content script always fetches Voyager data for display regardless of rate limit status. Only the `enrichProfile` pipeline in the service worker checks `canProceed()`.

### Freshness and Staleness

**Navigation-time freshness check**: On every profile navigation (in `handleUrlChanged`), the service worker starts a `freshnessPromise = checkFreshness()` call in parallel with the content script's Voyager fetch. This is a read-only `GET` request — no writes. The result determines the initial badge status. If the backend is unreachable, the promise catches the error and returns `{ exists: false, offline: true }`, which triggers the offline bar. Verify the freshness check does not block profile card rendering.

**New profile detection**: Extension checks backend via `GET /crawled-profiles?linkedin_url={normalized_url}&limit=1`. If `crawled_profiles` array is empty, the profile is new. Extension creates it via `POST /crawled-profiles`. Verify side panel shows "Saved today" badge.

**Fresh profile skip**: If the backend profile's `last_crawled_at` is within the staleness threshold (configurable via `config.stalenessDays`, default 30), the extension skips the save. If `has_enriched_data` is false on a fresh profile, enrichment is backfilled silently. Verify side panel shows "Up to date" badge and no write request is made.

**Stale profile update**: If `last_crawled_at` is older than the staleness threshold (computed as `staleDays >= config.stalenessDays`), the extension updates via `PATCH /crawled-profiles/{id}` with fresh Voyager data. In manual mode, the badge shows "Stale" with staleness days. Verify the update replaces the backend record and enrichment runs after update.

**Missing last_crawled_at**: If a backend profile has no `last_crawled_at`, the client treats it as stale by defaulting to `stalenessDays + 1`.

**URL normalization agreement**: Both extension (`lib/profile/url.ts`) and backend normalize LinkedIn URLs identically: lowercase slug, no trailing slash, no query params, strip country prefixes, canonical `https://www.linkedin.com/in/<slug>`. Verify exact-match lookups succeed for URLs with varied casing, trailing slashes, or query parameters.

> Edge: Race condition in check-then-create (two tabs enriching same profile simultaneously). On 409 unique constraint violation (`BackendError` with status 409), the extension retries with a freshness check and falls back to update.

### Status State Machine

**Status transitions**: The `ProfileStatusUpdate.status` field tracks pipeline phase. The `ProfileBadgeStatus` type defines the user-visible badge. The valid badge states are:

| Badge State | Visual | Trigger | Next States |
|-------------|--------|---------|-------------|
| loading | Skeleton | Profile page detected, fetch started | not_saved, saved_today, up_to_date, stale, rate_limited, save_failed, challenge_detected |
| not_saved | "Not saved" + "Save to LinkedOut" button | Freshness check: profile not in backend | saved_today (after save), save_failed, rate_limited |
| saved_today | "Saved today" | Successful POST or PATCH to backend | (terminal for session) |
| up_to_date | "Up to date" | Backend profile is fresh (within staleness threshold) | (terminal for session) |
| stale | "Stale" with days count | Backend profile older than staleness threshold | saved_today (after update), save_failed, rate_limited |
| rate_limited | "Rate limited" | Hourly or daily self-imposed limit reached | not_saved, saved_today (when limits reset and user retries) |
| save_failed | "Save failed" | Backend unreachable or returns error | saved_today (on retry), save_failed |
| challenge_detected | "Challenge detected" | LinkedIn returns challenge/CAPTCHA page | saved_today (on retry after challenge clears) |

> Note: The pipeline `status` values (`idle`, `fetching`, `ready`, `saving`, `done`, `error`, `skipped`) are internal phases. `ready` is transient in both modes. In auto mode, the service worker immediately proceeds to enrichment. In manual mode, the service worker awaits the parallel freshness check and transitions to `not_saved`, `up_to_date`, or `stale`.

### Cross-Context Message Contracts

**Execution contexts**: The extension operates across five isolated contexts: MAIN world content script (`voyager.content.ts`), ISOLATED world content script (`bridge.content.ts`), service worker (`background.ts`), side panel (`App.tsx`), and options page (`options/App.tsx`).

**MAIN to bridge relay**: MAIN world dispatches `CustomEvent` on the document with `linkedout:` prefixed event names. Bridge listens and forwards via `browser.runtime.sendMessage`. Event types forwarded: `URL_CHANGED`, `VOYAGER_DATA_READY`, `VOYAGER_DATA_ERROR`, `MUTUAL_EXTRACTION_PROGRESS`, `MUTUAL_CONNECTIONS_READY`, `EXTRACTION_SPEED_CHANGED`.

**Bridge to MAIN relay**: Bridge receives `browser.runtime.onMessage` from service worker and dispatches `CustomEvent` to MAIN world. Message types relayed: `RETRY_FETCH` (re-sense after challenge), `EXTRACT_MUTUAL_CONNECTIONS` (Best Hop extraction request), `SET_EXTRACTION_SPEED` (speed multiplier change).

**Service worker to side panel**: Service worker sends push-based updates via `broadcastToSidePanel` (which calls `browser.runtime.sendMessage`). Message types: `PROFILE_STATUS_UPDATE`, `RATE_LIMIT_UPDATE`, `LOG_UPDATED`, `OFFLINE_STATUS_UPDATE`, `CHALLENGE_STATUS_UPDATE`, `BEST_HOP_RESULT`, `BEST_HOP_THINKING`, `BEST_HOP_COMPLETE`, `BEST_HOP_ERROR`, `MUTUAL_EXTRACTION_PROGRESS`, `EXTRACTION_SPEED_CHANGED`. No polling from side panel.

**Side panel to service worker**: Side panel sends requests via `browser.runtime.sendMessage`. Message types: `ENRICH_PROFILE` (manual save/update trigger), `FIND_BEST_HOP` (initiate Best Hop flow), `CANCEL_BEST_HOP`, `SET_EXTRACTION_SPEED`, `RETRY_AFTER_CHALLENGE`.

**Side panel connect signal**: When the side panel opens, it establishes a port via `browser.runtime.connect({ name: 'sidepanel' })`. The service worker's `onConnect` handler clears the error badge, re-sends offline/challenge state, and either sends cached profile data or queries the active tab URL.

**Content script autonomy**: The MAIN world content script is an autonomous sensor. It always fetches Voyager data when it detects a profile page (on injection or SPA navigation) and reports via `VOYAGER_DATA_READY`. The service worker never commands the content script to fetch (except for `RETRY_FETCH` after a challenge clears). This eliminates timing bugs from cross-context fetch coordination.

**Full message type union**: All 22 message types are defined in `lib/messages.ts` as a discriminated union (`ExtensionMessage`) keyed on the `type` field.

> Edge: Bridge is a pure relay with zero business logic. It exists solely because MAIN world cannot access `chrome.*` APIs.

### Backend API Contracts

**Freshness check**: `GET /crawled-profiles?linkedin_url={normalized_url}&limit=1` — returns `{ crawled_profiles: [...] }`. Extension checks `last_crawled_at` against staleness threshold.

**Create profile**: `POST /crawled-profiles` — body matches `CrawledProfilePayload` (mapped from Voyager data via `toCrawledProfilePayload`). Hardcoded fields: `data_source: 'extension'`, `source_app_user_id: config.userId`. Returns `{ crawled_profile: { id, ... } }`.

**Update profile**: `PATCH /crawled-profiles/{id}` — body matches partial `CrawledProfilePayload`. Updates `last_crawled_at` and all Voyager-sourced fields.

**Enrich profile**: `POST /crawled-profiles/{id}/enrich` — body matches `EnrichProfilePayload` (experiences, educations, skills arrays, mapped via `toEnrichPayload`). Backend creates structured rows, rebuilds `search_vector`, resolves company/role aliases, generates embedding, and sets `has_enriched_data = true`. Extension calls this after every successful create or update, and as a backfill when a fresh profile has `has_enriched_data = false`. Enrichment failures are caught and logged but never prevent the "Saved today" badge.

**Recent activity**: `GET /crawled-profiles?data_source=extension&sort_by=created_at&sort_order=desc&limit={N}` — for populating the recent activity list (via `getRecentActivity`, configurable limit default 20).

**Best Hop search**: `POST /tenants/{tenantId}/bus/{buId}/best-hop` — SSE stream. Body includes `target_name`, `target_url`, and `mutual_urls` (all URLs normalized). Returns streaming `data:` events with types: `thinking`, `result`, `done`, `error`, `explanations` (ignored), `heartbeat`/`session`/`conversation_state` (skipped). Results are ranked incrementally by the client.

**Authentication**: All requests include `X-App-User-Id: {config.userId}` header (via `getHeaders()`). CORS is handled by backend's `allow_origins=['*']`. Tenant/BU/user IDs are configurable via the options page (defaults: `tenant_sys_001`, `bu_sys_001`, `usr_sys_001`).

> Edge: Crawled-profile endpoints (CRUD + enrich + recent) are unscoped (no tenant/BU prefix). Only the best-hop endpoint is tenant/BU-scoped.

### Voyager API Client

**Single call per profile**: The extension makes exactly one Voyager API call per profile visit via `fetchVoyagerProfile()` using the `FullProfileWithEntities-93` decoration ID. All UI fields (Open to Work, connection count, location, headline, avatar, premium status) are extracted from that single response. Verify no additional Voyager endpoints are called for profile enrichment.

**CSRF token extraction**: The Voyager client extracts the CSRF token from the `JSESSIONID` cookie via regex: `document.cookie.match(/JSESSIONID="?([^";]+)"?/)`. The token is sent as the `csrf-token` header.

**Same-origin fetch**: Voyager calls run in MAIN world using `fetch()` with `credentials: 'include'`, which automatically includes LinkedIn session cookies. The `accept` header is set to `application/vnd.linkedin.normalized+json+2.1`.

**Error classification**: The Voyager client classifies errors into three typed exceptions: `VoyagerCsrfError` (HTTP 403), `VoyagerRateLimitError` (HTTP 429), `VoyagerChallengePage` (non-JSON content-type response). These map to the `VoyagerDataError.errorType` enum: `csrf`, `rate_limit`, `challenge`, `unknown`.

**Missing fields accepted**: If a field is absent from the Voyager response (varies by decoration and profile privacy), it is left empty in the UI and stored as null in the backend payload. The parser (`parseVoyagerProfile`) uses fallback chains (e.g., `locationName` falls back to `geoLocationName`). Verify the UI degrades gracefully with missing data.

### Voyager Response Parser

**Comprehensive entity extraction**: The parser (`lib/voyager/parser.ts`) extracts 12 entity types from the Voyager `included[]` array: Profile, Position, Education, Skill, Geo, Industry, Company, Certification, Language, Project, VolunteerExperience, Course, Honor. Each entity type has a corresponding `com.linkedin.voyager.dash.` type constant.

**Geo resolution**: The parser resolves the profile's `geoLocation.geoUrn` to a Geo entity in `included[]`, then parses city/state/country from the `defaultLocalizedNameWithoutCountryName` or `defaultLocalizedName` fields. Country name is resolved from a separate country Geo entity via `*country` or `countryUrn`.

**Company resolution**: Companies are parsed from `included[]` with industry resolved via nested URN lookup and employee count range extracted from `employeeCountRange`. The mapper (`toEnrichPayload`) uses `resolveCompany()` to link position `companyUrn` values to their company details (URL, universalName).

**Profile picture extraction**: Avatar URL is assembled from the `profilePicture.displayImageReference.vectorImage` field: `rootUrl` + the largest artifact's `fileIdentifyingUrlPathSegment`.

### Profile Mapper (Two-Step Transform)

**Parser + mapper separation**: Voyager-to-backend mapping is split into two steps: (1) `parseVoyagerProfile()` produces a typed `VoyagerProfile` from raw JSON, (2) `toCrawledProfilePayload()` and `toEnrichPayload()` produce backend-compatible payloads. This isolates change impact: if Voyager format changes, only the parser changes; if the backend schema changes, only the mapper changes.

**CrawledProfilePayload mapping**: The mapper derives `current_company_name` and `current_position` from the first position without an `endDate`. Location fields are mapped from resolved geo data. `raw_profile` stores the full parsed profile as JSON.

**EnrichProfilePayload mapping**: Experiences include `company_linkedin_url` and `company_universal_name` resolved from company entities. Date fields are split into `start_year`/`start_month`/`end_year`/`end_month` via `parseYear()`/`parseMonth()` helpers. `is_current` is set to `true` for positions without an `endDate`.

### Runtime Configuration

**Unified config module**: `lib/config.ts` provides a unified configuration system backed by `browser.storage.local` under key `linkedout_config`. Configuration is loaded once at startup via `initConfig()` and cached. The cache is auto-invalidated on storage changes via `browser.storage.onChanged` listener.

**Options page**: The extension has a dedicated options page (`entrypoints/options/`) that exposes configurable settings: Backend URL (default `http://localhost:8001`), staleness threshold (default 30 days), hourly rate limit (default 30), daily rate limit (default 150), enrichment mode (default manual), and advanced settings (tenant ID, BU ID, user ID). The options page includes a "Test Connection" button that hits `GET /health` on the configured backend URL.

**Internal tuning values**: Non-user-facing config values with defaults: `minFetchDelayMs` (2000), `maxFetchDelayMs` (5000), `maxLogEntries` (200), `mutualMaxPages` (10), `urlDebounceMs` (500), `recentActivityLimit` (20), `mutualFirstPageDelayBaseMs` (1000), `mutualFirstPageDelayRangeMs` (1500).

**Legacy migration**: `initConfig()` migrates the pre-options-page `enrichmentMode` key from top-level storage into the unified config object.

### Error Handling

**Backend offline**: Service worker fetch to backend fails (network error). `BackendUnreachable` error is thrown. Side panel shows full-width offline bar via `OFFLINE_STATUS_UPDATE` message. Profile badge shows "Save failed". The `markBackendReachable()` helper clears the offline flag on any successful backend response. Verify the extension retries on next user-initiated action but does not auto-retry.

**LinkedIn challenge detection**: Voyager API returns non-JSON content-type (challenge/CAPTCHA page). The `VoyagerChallengePage` error is thrown. The service worker sets `challengeActive = true`, sends `CHALLENGE_STATUS_UPDATE` to side panel, and shows "Challenge detected" badge. All further profile fetches are paused (the `challengeActive` flag is cleared only on successful Voyager response or explicit retry). Verify no further Voyager calls are made until user clicks Retry.

**LinkedIn 429 response**: Voyager API returns HTTP 429. The `VoyagerRateLimitError` is thrown. The service worker does NOT count LinkedIn 429s against its own rate limit counters — it logs as `rate_limited` with reason "LinkedIn 429" and shows a warning. Verify the self-imposed rate limit counters remain unchanged.

**CSRF token expiry**: Voyager API returns HTTP 403. The `VoyagerCsrfError` is thrown. The extension surfaces an error suggesting the user refresh the LinkedIn page to renew the session. Verify no retry loop occurs.

**Retry after challenge**: User clicks "Retry" in the challenge banner. Side panel sends `RETRY_AFTER_CHALLENGE` to service worker, which clears the challenge flag, sends `RETRY_FETCH` to the content script via bridge, and the MAIN world content script resets `lastFetchedProfileId = null` and re-fetches the current profile.

**Error badge**: The service worker maintains an `errorCount` on the extension icon badge (red background). Each log entry with `action: 'error'` increments the count. The badge is cleared when the side panel connects (opens).

### Activity Log

**Local storage**: Activity log entries are stored in `chrome.storage.local` under key `activityLog` as a capped array (configurable max via `config.maxLogEntries`, default 200). The `appendLog()` function performs upsert semantics: if an entry with the same `linkedinUrl` already exists, it is replaced and moved to the top. Oldest entries are dropped when cap is exceeded. Data source is local decisions only — not backend queries.

**Entry types**: Each `LogEntry` contains: `timestamp` (ISO), `action` (one of `fetched`, `saved`, `updated`, `skipped`, `rate_limited`, `error`, `best_hop`, `api_call`), `profileName`, `profileHeadline`, `linkedinUrl`, `reason` string, and optional fields for API calls (`method`, `path`, `statusCode`, `durationMs`) and rate limits (`limitName`, `retryAfterMs`, `currentCount`, `limitMax`).

**Activity tab display**: Full log view via `ActivityLog` component with sticky summary bar (saved/skipped/errors counts with color-coded numbers), filter chips (All / Saved / Skipped / Errors), and chronological entries newest-first. Each entry shows timestamp, colored icon circle, profile name + headline, and reason line. Tapping an entry opens the LinkedIn profile URL in a new tab via `window.open()`.

**Tab badge**: Activity tab shows unread count badge (entries added since user last viewed the Activity tab). The `unreadCount` state increments on each `LOG_UPDATED` message and clears when the user switches to the Activity tab.

**Recent activity on Profile tab**: Compact list below Best Hop section via `RecentActivity` component showing recent enrichments from log entries. "View all" link navigates to the Activity tab. Updated in real-time via `LOG_UPDATED` push messages.

### Side Panel Layout

**Header**: "LinkedOut" text in Fraunces serif font (purple #8558AC, left), Auto toggle with Fragment Mono label (right). Toggle persists via `setEnrichmentMode()` which writes to unified config. Verify toggling updates enrichment behavior immediately.

**Tabs**: Two tabs below header — "Profile" (default active) and "Activity" (with unread badge) via `TabBar` component.

**Profile tab content** (when on a profile page): `ProfileCard`, `RateLimitBar`, `StatusBanner` (error/warning, dismissible), `FetchButton` (manual mode only, hidden in auto mode), `BestHopPanel`, `RecentActivity`.

**Profile tab empty state** (when not on a profile page): Centered empty state with link icon, "Navigate to a LinkedIn profile" title, and "Open a LinkedIn profile page to get started" description. Recent activity list is not shown in empty state.

**Activity tab content**: Summary bar (sticky), filter chips, chronological log entries.

**Loading state**: `Skeleton` component matching profile card layout shown while Voyager fetch is in progress and no profile data is cached.

**Offline bar**: `OfflineBar` component — full-width red bar shown when `isOffline` is true, hidden when backend becomes reachable.

**Challenge banner**: `ChallengeBanner` component — shown when `challengeActive` is true, with explanatory message and retry button.

**Footer**: Centered "LinkedOut Extension v0.1" text in Fragment Mono.

### Best Hop Flow

**Mutual connection extraction via Voyager API**: User clicks "Find Best Hop" on a saved profile. The extension fetches mutual connections using LinkedIn's Voyager `search/dash/clusters` endpoint (not HTML scraping — LinkedIn search pages are client-rendered). The `extractMutualConnectionUrls()` function paginates at 10 results per page (`MUTUAL_PAGE_SIZE`), throttled with configurable random delay (default 2-5s, divided by speed multiplier), max pages configurable (default 10). First page has a separate delay range (default 1000ms + random 0-1500ms). Profile URLs are extracted from `included[]` entities via `navigationUrl` matching. Current user and target profile slugs are excluded from results.

**Extraction speed control**: The side panel can send `SET_EXTRACTION_SPEED` with multiplier values of 1, 2, 4, or 8. The multiplier divides the random delay between pages. Speed resets to 1x at the start of each extraction. On LinkedIn 429 during extraction, speed auto-downshifts to 1x via `onSpeedDownshift` callback.

**SSE search stream**: After extraction, mutual connection URLs are sent to the backend `best-hop` endpoint via SSE POST. The service worker's `streamBestHop()` consumes the stream line-by-line, parsing `data:` prefixed JSON events. Results are ranked incrementally (client-side `resultRank` counter). The `BestHopResult` message includes rank, name, role, affinity score, reasoning, and LinkedIn URL. Verify results render progressively as they arrive via `BEST_HOP_RESULT` messages.

**Cancellation**: Cancel is available during both extraction and SSE phases. Extraction uses an `AbortController` passed to the extractor's fetch calls and sleep delays. SSE uses a separate `bestHopAbort` controller passed to the fetch signal. Verify cancellation is immediate — the `AbortError` is caught and partial results are reported.

**Zero mutual connections**: If extraction finds no mutual connections, a `BEST_HOP_COMPLETE` with `totalResults: 0` is sent to the side panel. Verify no backend request is made.

**Best Hop panel**: `BestHopPanel` component on Profile tab. Disabled when no profile is loaded or profile has no `entityUrn`.

> Edge: Mutual connection pagination stops immediately if LinkedIn returns 429, 403, or non-OK response, and reports partial results with a `challenge` stop reason.

> Edge: Mutual connection page fetches for Best Hop are separate from the profile Voyager call and are user-initiated, not automatic.

### Enrichment Dedup Guard

**In-flight dedup**: The service worker maintains an `enrichingIds` Set to prevent duplicate `enrichProfile` backend calls while one is in-flight for the same crawled profile ID. If an enrichment is already running for a given ID, the duplicate call is silently skipped.

### Current User Detection

**DOM-based slug extraction**: `getCurrentUserSlug()` in `lib/profile/current-user.ts` extracts the logged-in user's LinkedIn slug from the page DOM. It checks three selectors in order: (1) nav "Me" dropdown link with `data-control-name="identity_welcome_message"`, (2) `.global-nav__me-content a[href*="/in/"]`, (3) `a.global-nav__primary-link[href*="/in/"]`. Falls back to `meta[name="currentUser"]`. The slug is lowercased. Used to exclude the current user from Best Hop mutual connection results.

---

## Decisions

| # | Date | Decision | Over | Because |
|---|------|----------|------|---------|
| 1 | 2026-04-04 | Manual mode is the default enrichment mode | Auto mode default | Users often open many tabs from Sales Navigator or Google search; auto mode would enrich all of them, burning rate limits and risking LinkedIn bans |
| 2 | 2026-04-04 | Voyager API calls run in MAIN world content script | Service worker with `chrome.cookies` | Same-origin fetch in MAIN world automatically includes LinkedIn session cookies; service worker approach is fragile with httpOnly cookies and missing referer context |
| 3 | 2026-04-04 | Content script is an autonomous sensor; service worker is the enrichment brain | Service worker commands content script fetches | Content script always fetches Voyager when it detects a profile page (knows when it's ready). Service worker decides what to do with the data (display-only vs enrich). Eliminates timing bugs from cross-context fetch coordination |
| 4 | 2026-04-05 | Dedicated `POST /crawled-profiles/{id}/enrich` endpoint for structured data | Inline enrichment in CRUD payload | Separates profile creation (flat fields) from enrichment (experience/education/skill rows). Extension calls enrich after every save. Fresh-but-unenriched profiles are backfilled automatically. Enrichment failures are logged but never block the "Saved today" badge |
| 5 | 2026-04-04 | Two-step Voyager-to-backend transform (parser + mapper) | Single transform function | Isolates change impact: if Voyager format changes, only parser changes; if backend schema changes, only mapper changes |
| 6 | 2026-04-04 | Push-based side panel updates (no polling) | Periodic polling from side panel | Service worker sends messages after each state change, avoiding unnecessary network/CPU usage |
| 7 | 2026-04-04 | Self-imposed rate limits at 30/hr and 150/day (configurable) | No limits or LinkedIn's limits only | LinkedIn triggers challenge/CAPTCHA around 900 contiguous requests; conservative self-imposed limits provide large safety margin |
| 8 | 2026-04-04 | WXT framework for extension tooling | Raw Manifest V3 boilerplate | WXT provides HMR during dev, auto-manifest generation, and entrypoint conventions that eliminate boilerplate |
| 9 | 2026-04-09 | Options page for runtime configuration | Hardcoded constants | Backend URL, rate limits, staleness threshold, and tenant/BU/user IDs are configurable without rebuilding. Test Connection button validates backend reachability |
| 10 | 2026-04-09 | Mutual connection extraction via Voyager search API | HTML scraping of search result pages | LinkedIn search pages are client-rendered (RSC), so HTML scraping returns an empty shell. The Voyager `search/dash/clusters` endpoint returns structured JSON matching what LinkedIn's own frontend renders |

---

## Not Included

- **Background sync/periodic enrichment** — no scheduled or background profile refreshes
- **Bulk operations** — no batch scrape of multiple profiles at once
- **Profile photo download/storage** — avatar displayed from LinkedIn CDN only
- **LinkedIn InMail or messaging integration** — read-only data extraction
- **Non-LinkedIn profile sources** — extension operates only on `linkedin.com/in/` pages
- **Offline mode with local cache** — extension requires backend connectivity to save profiles (Voyager data is cached in-memory for the current session only)
- **User authentication flow** — configurable tenant/BU/user IDs via options page (single-user tool, no login)
- **Firefox support** — WXT config includes Firefox build scripts but the extension is Chrome-only (sidePanel API is Chrome-specific)
- **Design system HTML** — no standalone design system document; styles are inline React CSSProperties in each component
