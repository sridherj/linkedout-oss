# Chrome Extension

## Overview

The LinkedOut Chrome extension captures LinkedIn profile data as you browse. When you visit a LinkedIn profile, the extension reads the profile via LinkedIn's internal Voyager API (using your existing session cookies) and saves it to your local LinkedOut database through the backend API.

**What it does:**
- Captures LinkedIn profile data (experience, education, skills, connections) from profiles you visit
- Saves profiles to your local PostgreSQL database via the backend API on localhost
- Shows profile status (new, stale, up-to-date) in a side panel
- Supports a "Best Hop" feature that finds the strongest path to reach someone through mutual connections

**What it requires:**
- The LinkedOut backend API running on localhost (`linkedout start-backend`)
- Chrome 114+ (Manifest V3 with sidePanel API)
- A logged-in LinkedIn session in the same Chrome browser

**What it is NOT:**
- Not a scraper — it does not crawl profiles in bulk or navigate pages automatically
- Not automated collection — it only captures profiles you actively visit in your browser
- It mimics your normal browsing behavior, reading the same data LinkedIn already shows you

**Installation:** Run the `/linkedout-extension-setup` skill in Claude Code. It handles downloading the pre-built extension zip, extracting it, and guiding you through Chrome sideloading.

---

## Setup

### Recommended: Use the setup skill

Run `/linkedout-extension-setup` in Claude Code. It downloads the pre-built extension, extracts it, starts the backend, and walks you through sideloading.

### Manual Chrome sideloading

If you prefer to install manually:

1. Build the extension (or download the pre-built zip)
2. Navigate to `chrome://extensions` in Chrome
3. Enable **Developer mode** (toggle in the top-right corner)
4. Click **Load unpacked**
5. Select the built extension directory (e.g., `extension/.output/chrome-mv3/`)
6. The LinkedOut icon should appear in your extensions toolbar

### Start the backend

The extension requires the backend API running on localhost:

```bash
linkedout start-backend
```

This starts a FastAPI server on `http://localhost:8001`. The backend must be running whenever you use the extension.

---

## Usage

### Side panel

When you visit a LinkedIn profile (`linkedin.com/in/...`), click the LinkedOut extension icon to open the side panel. The side panel shows:

- **Profile status** — whether the profile is new, up-to-date, or stale (older than 30 days)
- **Fetch button** — click to capture the profile's full data (experience, education, skills)
- **Activity log** — recent extension activity (fetched, saved, updated, skipped, rate-limited profiles)
- **Best Hop** — find the strongest path to reach someone through mutual connections

### How data flows

1. You visit a LinkedIn profile in Chrome
2. The extension detects the navigation and reads profile data via LinkedIn's Voyager API (using your existing session)
3. The data is sent to the LinkedOut backend API on localhost
4. The backend saves it to your local PostgreSQL database
5. The profile is now available for queries via the `/linkedout` skill

Profiles captured by the extension include richer data than a CSV export: full work history with dates, education details, skills, and mutual connections.

---

## Voyager API Fragility

**The extension depends on LinkedIn's internal Voyager API. This is inherently fragile.**

The Voyager API is LinkedIn's private, internal API — not a public contract. LinkedIn can and does change it without notice. Here's what you need to know:

- **Decoration IDs change.** The extension uses decoration IDs like `com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93` to request profile data. When LinkedIn updates these IDs, the extension will stop returning data or return 400 errors. This has happened before and will happen again.

- **LinkedIn may detect automated requests.** Even though the extension uses your real browser session and cookies, LinkedIn's anti-automation systems may flag the requests. This can result in CAPTCHA challenges that you must solve manually before the extension can continue.

- **CSRF tokens expire.** The extension uses LinkedIn's CSRF token from your session. If your session goes stale, the extension will fail until you refresh the LinkedIn page.

- **Response format may change.** The Voyager API response structure can change, breaking the extension's parser even if the API call succeeds.

**When Voyager breaks:** If the extension stops working after a LinkedIn update, [file a GitHub issue](https://github.com/sridherj/linkedout-oss/issues). Include the error from the side panel. Maintainers will update the decoration IDs and parser.

**LinkedOut works without the extension.** All core functionality (queries, affinity scoring, seed data, CSV import) works with data already in the database. The extension is an optional enhancement for capturing richer profile data.

---

## Rate Limit Guidance

The extension enforces self-imposed rate limits to reduce the risk of LinkedIn detection:

| Limit | Default | Purpose |
|-------|---------|---------|
| Hourly | 30 profiles/hour | Prevents burst activity that looks automated |
| Daily | 150 profiles/day | Caps total daily usage to stay under LinkedIn's radar |

These are **self-imposed limits**, not LinkedIn-imposed. LinkedIn does not publish official rate limits for profile views, but aggressive crawling increases the risk of CAPTCHA challenges or account restrictions.

**Configurable via the extension options page** (right-click extension icon > Options):
- Adjust hourly and daily limits
- Set profile staleness threshold (default: 30 days — profiles older than this are re-fetched)

**If LinkedIn returns 429 (Too Many Requests):**
- The extension automatically backs off
- The side panel shows a "Rate limited" status
- This does **not** count against your self-imposed limits — it's LinkedIn telling you to slow down

**Recommendation:** Leave the defaults unless you have a specific reason to change them. Higher limits increase the risk of detection.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Backend is unreachable" | Backend not running | Run `linkedout start-backend` |
| Side panel shows nothing | Not on a LinkedIn profile page | Navigate to `linkedin.com/in/someone` |
| "LinkedIn challenge detected" | LinkedIn CAPTCHA | Solve CAPTCHA in LinkedIn tab, click Retry in the side panel |
| "CSRF token expired" | LinkedIn session stale | Refresh the LinkedIn page |
| Extension not visible in Chrome | Not sideloaded correctly | Re-follow sideloading instructions via `/linkedout-extension-setup` |
| Profiles not appearing in queries | Embeddings not generated | Run `linkedout embed` to generate embeddings |
| Error badge on extension icon | Background errors occurred | Open side panel to see details — badge clears when panel opens |
| Options page not accessible | Extension not fully loaded | Reload extension from `chrome://extensions` |
| Voyager returns 400 or empty data | LinkedIn changed decoration IDs | [File a GitHub issue](https://github.com/sridherj/linkedout-oss/issues) — maintainers will update the parser |

---

## Architecture

```
LinkedIn Tab                      Extension                         Backend (localhost:8001)
┌──────────────┐            ┌─────────────────────┐            ┌──────────────────┐
│ linkedin.com │            │ voyager.content.ts   │            │ FastAPI           │
│              │            │ (MAIN world)         │            │                   │
│  Voyager     │◄───fetch───│  • Voyager API calls │            │  /crawled-        │
│  API         │───JSON────►│  • SPA nav detection │            │   profiles        │
│              │            │  • Mutual extraction │            │                   │
│              │            │                      │            │  /crawled-        │
│              │            │ bridge.content.ts    │            │   profiles/:id/   │
│              │            │ (ISOLATED world)     │            │   enrich          │
│              │            │  • Event relay only  │            │                   │
│              │            │                      │            │  /health          │
│              │            │ background.ts        │            │                   │
│              │            │ (Service Worker)     │──fetch────►│                   │
│              │            │  • Orchestration hub │◄──JSON─────│                   │
│              │            │  • Rate limiting     │            │                   │
│              │            │  • Freshness checks  │            │                   │
│              │            │  • Error handling    │            │                   │
│              │            │                      │            └────────┬─────────┘
│              │            │ sidepanel/           │                     │
│              │            │  • Profile display   │               ┌────▼────┐
│              │            │  • Activity log      │               │PostgreSQL│
│              │            │  • Best Hop UI       │               │ (local)  │
│              │            │                      │               └─────────┘
│              │            │ options/             │
│              │            │  • Settings page     │
│              │            └─────────────────────┘
└──────────────┘
```

**Data flow:**

1. **Navigation:** When you visit a LinkedIn profile, `voyager.content.ts` (running in MAIN world on linkedin.com) detects the URL change via monkey-patched `history.pushState`/`replaceState`.
2. **Voyager fetch:** The content script calls LinkedIn's Voyager API using same-origin `fetch` with the page's CSRF token and session cookies.
3. **Bridge relay:** `bridge.content.ts` (ISOLATED world) relays messages between the MAIN world content script and the service worker via `CustomEvent` ↔ `chrome.runtime.sendMessage`.
4. **Orchestration:** `background.ts` (service worker) receives the Voyager data, checks rate limits, queries the backend for freshness, and decides whether to create/update the profile.
5. **Backend save:** The service worker sends the profile data to the backend API (`/crawled-profiles`), which writes it to PostgreSQL.
6. **Side panel:** The React-based side panel shows real-time profile status, activity log, and Best Hop results.

---

## Configuration Reference

### Options Page Settings

These settings are configurable from the extension options page (right-click extension icon > Options):

| Setting | Default | Description |
|---------|---------|-------------|
| Backend URL | `http://localhost:8001` | URL of the LinkedOut backend API |
| Staleness days | `30` | Profiles older than this are considered stale and re-fetched |
| Hourly limit | `30` | Max profiles captured per hour |
| Daily limit | `150` | Max profiles captured per day |
| Enrichment mode | `manual` | `manual` (click Fetch per profile) or `auto` (save on visit) |
| Tenant ID | `tenant_sys_001` | System tenant ID (advanced) |
| BU ID | `bu_sys_001` | System business unit ID (advanced) |
| User ID | `usr_sys_001` | System user ID (advanced) |

### Build-Time Configuration

| Setting | Default | Env Var | Notes |
|---------|---------|---------|-------|
| Backend URL | `http://localhost:8001` | `VITE_BACKEND_URL` | Baked into the extension at build time; overridable at runtime via options page |

### Backend Configuration (config.yaml / env vars)

| Setting | Default | Env Var | Config Key | Notes |
|---------|---------|---------|------------|-------|
| Backend port | `8001` | `LINKEDOUT_BACKEND_PORT` | `backend_port` | Port the backend binds to |
| Backend host | `localhost` | `LINKEDOUT_BACKEND_HOST` | `backend_host` | Host the backend binds to |
| Staleness days | `30` | `LINKEDOUT_STALENESS_DAYS` | — | Also configurable via extension options page |
| Hourly limit | `30` | `LINKEDOUT_RATE_LIMIT_HOURLY` | — | Also configurable via extension options page |
| Daily limit | `150` | `LINKEDOUT_RATE_LIMIT_DAILY` | — | Also configurable via extension options page |

### Runtime Storage

Extension settings are persisted in `browser.storage.local` under the key `linkedout_config`. The options page writes here, and all extension components read from it via `getConfig()` / `getConfigSync()`. Changes take effect immediately (no restart needed).
