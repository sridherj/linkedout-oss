# Phase 12: Chrome Extension Add-on — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Draft — pending SJ review
**Phase Dependencies:** Phases 2 (Env & Config), 3 (Logging), 4 (Constants), 6 (Code Cleanup), 8 (Skill System), 9 (Setup Flow)
**Decision Docs Referenced:**
- `docs/decision/cli-surface.md` — `linkedout start-backend` command spec
- `docs/decision/env-config-design.md` — `LINKEDOUT_BACKEND_PORT`, `LINKEDOUT_BACKEND_HOST`, `VITE_BACKEND_URL`, extension runtime config via `browser.storage.local`
- `docs/decision/logging-observability-strategy.md` — extension logging: `devLog()` utility, backend call logging, rate limit events, error badge
- `docs/decision/queue-strategy.md` — Procrastinate removed; enrichment runs synchronously (3-5s per profile via API)
- `docs/decision/2026-04-07-data-directory-convention.md` — `~/linkedout-data/` for logs, config, data

---

## Phase Overview

**Goal:** Make the Chrome extension an optional add-on that users can install after core setup. The extension enables LinkedIn profile crawling via the Voyager API and communicates with the backend API on localhost.

**What this phase delivers:**
1. A pre-built extension zip published as a GitHub Release asset (no Node.js needed for users)
2. A GitHub Actions pipeline that builds and zips the extension on every release
3. An options page for user-configurable settings (backend URL, rate limits, tenant IDs)
4. A `/linkedout-extension-setup` skill that guides users through download, sideloading, and backend startup
5. Backend server lifecycle management (`linkedout start-backend` with daemon mode and health checks)
6. Extension logging integrated with the Phase 3 observability strategy
7. Documentation on Voyager API fragility, rate limits, and troubleshooting

**What this phase does NOT deliver:**
- Chrome Web Store listing (deferred — requires review process)
- Multi-browser support (Firefox, Edge — deferred)
- Extension auto-update mechanism (users re-download zip via `/linkedout-upgrade`)

---

## Design Gate

> **GATE: SJ approval required before ANY implementation begins.**

### 12A. UX Design Doc

**Deliverable:** `docs/design/extension-setup-ux.md`

**Contents required (per plan.collab.md):**
- Every step `/linkedout-extension-setup` shows the user, with exact wording
- Sideloading instructions with screenshots (or screenshot placeholders with dimensions and descriptions)
- How backend server status is communicated to the user (running/stopped/error)
- Error messages for common failures:
  - Chrome too old (minimum version TBD — research Manifest V3 + sidePanel minimum)
  - Developer mode not enabled
  - Backend unreachable after start
  - Port conflict on 8001
  - Extension zip download failure
  - Extension loads but shows "Backend is unreachable" in side panel
- What the user sees when extension is working correctly (first successful crawl)
- How the user stops the backend when done

**File:** `docs/design/extension-setup-ux.md`
**Acceptance criteria:** SJ has reviewed and approved the UX doc.
**Complexity:** M
**Implementation target:** New file, no code changes.

---

## Task Breakdown

### 12B. Extension Build Pipeline

**Goal:** Automated CI that produces a sideloadable Chrome extension zip on every GitHub Release.

**Implementation:**

1. Create `.github/workflows/extension-build.yml`:
   - Trigger: `release` event (published) + manual `workflow_dispatch`
   - Matrix: Node.js 20 (LTS)
   - Steps:
     1. Checkout repo
     2. `cd extension && npm ci`
     3. `wxt build` (produces `extension/.output/chrome-mv3/`)
     4. `wxt zip` (produces `extension/.output/linkedout-extension-*.zip`)
     5. Upload zip as GitHub Release asset via `gh release upload`
   - Build-time env: `VITE_BACKEND_URL=http://localhost:8001` (default, per `docs/decision/env-config-design.md`)

2. Add `extension/.output/` to root `.gitignore` (already in `extension/.gitignore`, verify root)

**Files to create/modify:**
- Create: `.github/workflows/extension-build.yml`
- Modify: `.gitignore` (root) — ensure `extension/.output/` is excluded

**Acceptance criteria:**
- `wxt build && wxt zip` succeeds in CI
- Zip artifact is uploaded to the GitHub Release
- Zip can be sideloaded in Chrome and functions correctly

**Complexity:** S

---

### 12C. Extension Options Page

**Goal:** Let users configure the extension without rebuilding it. Settings are persisted to `browser.storage.local` per `docs/decision/env-config-design.md`.

**Implementation:**

1. Create `extension/entrypoints/options/index.html` — minimal HTML shell
2. Create `extension/entrypoints/options/main.tsx` — React mount
3. Create `extension/entrypoints/options/App.tsx` — settings form with fields:

| Setting | Default | Type | Notes |
|---------|---------|------|-------|
| Backend URL | `http://localhost:8001` | text input | From `VITE_BACKEND_URL` build-time default |
| Staleness threshold (days) | `30` | number input | Per `LINKEDOUT_STALENESS_DAYS` |
| Hourly rate limit | `30` | number input | Per `LINKEDOUT_RATE_LIMIT_HOURLY` |
| Daily rate limit | `150` | number input | Per `LINKEDOUT_RATE_LIMIT_DAILY` |
| Tenant ID | `tenant_sys_001` | text input | Advanced — collapsed by default |
| BU ID | `bu_sys_001` | text input | Advanced — collapsed by default |
| User ID | `usr_sys_001` | text input | Advanced — collapsed by default |
| Enrichment mode | `manual` | toggle | manual / auto |

4. Refactor `extension/lib/constants.ts` → `extension/lib/config.ts`:
   - Replace hardcoded exports with an async `getConfig()` function that reads from `browser.storage.local` with hardcoded fallbacks (pattern already specified in `docs/decision/env-config-design.md`)
   - Keep the old constant names as re-exports from `getConfig()` for backward compatibility during migration, then remove in a follow-up

5. Update all consumers of `constants.ts`:
   - `extension/lib/backend/client.ts` — `API_BASE_URL`, `APP_USER_ID`, `STALENESS_DAYS`
   - `extension/entrypoints/background.ts` — `STALENESS_DAYS`
   - `extension/lib/rate-limiter.ts` — `HOURLY_LIMIT`, `DAILY_LIMIT`
   - Any other files importing from `constants.ts`

6. Add `options` to `wxt.config.ts` manifest if needed (WXT auto-discovers `entrypoints/options/`)

7. Add a "Connection Test" button on the options page that:
   - Calls `GET {backendUrl}/health`
   - Shows green check + "Connected to LinkedOut backend v{version}" or red X + error message
   - Helps users validate their backend URL without leaving the options page

**Files to create:**
- `extension/entrypoints/options/index.html`
- `extension/entrypoints/options/main.tsx`
- `extension/entrypoints/options/App.tsx`
- `extension/lib/config.ts`

**Files to modify:**
- `extension/lib/constants.ts` (deprecate, re-export from config.ts, then remove)
- `extension/lib/backend/client.ts` (async config loading)
- `extension/entrypoints/background.ts` (async config loading)
- `extension/lib/rate-limiter.ts` (async config loading)
- `extension/lib/settings.ts` (may merge enrichment mode into unified config)
- `extension/wxt.config.ts` (if manual options registration needed)

**Acceptance criteria:**
- Options page is accessible via chrome://extensions → LinkedOut → Details → Extension options
- Changing backend URL takes effect on next API call (no extension reload needed)
- Connection test button provides immediate feedback
- Settings persist across extension reloads
- Default values match `docs/decision/env-config-design.md`

**Complexity:** M

---

### 12D. `/linkedout-extension-setup` Skill

**Goal:** A skill that guides the user through downloading the extension zip, sideloading it in Chrome, and starting the backend server.

**Dependencies:** 12A (UX design doc approved), 12B (build pipeline producing zip), 12C (options page), 12E (backend server management)

**Implementation:**

1. Create skill template: `skills/templates/linkedout-extension-setup.md.tmpl`
2. Generate per-host skills (Phase 8 skill system):
   - `skills/claude-code/linkedout-extension-setup.md`
   - `skills/codex/linkedout-extension-setup.md`
   - `skills/copilot/linkedout-extension-setup.md`

**Skill flow (from 12A UX design):**

1. **Prerequisites check:**
   - Verify Chrome is installed and version is sufficient (Manifest V3 + sidePanel API requires Chrome 114+)
   - Verify backend is configured (check `~/linkedout-data/config/config.yaml` exists)
   - Verify database is set up (run `linkedout status --json`, check DB connected)

2. **Download extension zip:**
   - Determine latest version from `linkedout version`
   - Download from GitHub Releases URL: `https://github.com/{owner}/{repo}/releases/download/v{version}/linkedout-extension-{version}.zip`
   - Save to `~/linkedout-data/extension/linkedout-extension-{version}.zip`
   - Verify checksum (from release manifest or inline SHA256)

3. **Sideloading instructions:**
   - Display step-by-step Chrome sideloading guide (text, since skills can't show images):
     1. Open `chrome://extensions`
     2. Enable "Developer mode" (top-right toggle)
     3. Click "Load unpacked" → navigate to extracted extension folder
     4. OR: Drag the `.zip` file directly onto the extensions page
   - Provide the path to the downloaded zip
   - Ask user to confirm when done

4. **Start backend server:**
   - Run `linkedout start-backend --background`
   - Verify backend is reachable: `curl -s http://localhost:8001/health`
   - If port conflict: suggest `linkedout start-backend --port 8002` and remind to update extension options

5. **Verify extension connection:**
   - Guide user: "Open any LinkedIn profile page. The LinkedOut side panel should appear when you click the extension icon."
   - If backend unreachable from extension: guide to options page → update backend URL

6. **Summary:**
   - Show what was set up and how to use it
   - Remind about `linkedout start-backend` being needed whenever extension is active
   - Point to extension documentation

**Files to create:**
- `skills/templates/linkedout-extension-setup.md.tmpl`
- `skills/claude-code/linkedout-extension-setup.md` (generated)
- `skills/codex/linkedout-extension-setup.md` (generated)
- `skills/copilot/linkedout-extension-setup.md` (generated)

**Acceptance criteria:**
- Skill successfully guides user from zero to working extension
- Skill handles common failure modes with actionable guidance
- Skill is idempotent — re-running on an already-setup system skips completed steps

**Complexity:** L

---

### 12E. Backend Server Management

**Goal:** Reliable start/stop of the backend API as a background service, with health checks and clear status communication.

**Implementation:**

1. Implement `linkedout start-backend` CLI command (per `docs/decision/cli-surface.md`):

   ```
   linkedout start-backend [OPTIONS]

   Options:
     --port PORT           Bind port (default: 8001, from LINKEDOUT_BACKEND_PORT)
     --host HOST           Bind host (default: 127.0.0.1, from LINKEDOUT_BACKEND_HOST)
     --background          Run as background daemon (write PID to ~/linkedout-data/state/backend.pid)
   ```

   **Idempotency (resolved decision):** Before starting, check if a process is already running on the target port. If so, kill it first. No "address already in use" errors. `start-backend` is always safe to re-run.

   **Foreground mode (default):** Runs uvicorn directly, logs to stdout + `~/linkedout-data/logs/backend.log`.

   **Background mode (`--background`):**
   - Check if port is in use → kill existing process if found (idempotent)
   - Fork process via `subprocess.Popen` with stdout/stderr redirected to `~/linkedout-data/logs/backend.log`
   - Write PID to `~/linkedout-data/state/backend.pid`
   - Wait up to 10s for health check (`GET /health`) to succeed
   - Print: `Backend started on http://localhost:8001 (PID: 12345)`
   - If health check fails: print error, kill process, exit 1

2. Implement `linkedout stop-backend` (user-facing convenience command in `--help`, not part of 13-command contract — resolved decision Q5):
   - Read PID from `~/linkedout-data/state/backend.pid`
   - Send SIGTERM, wait up to 10s, then SIGKILL if still running
   - Remove PID file
   - Confirm: `Backend stopped.`

3. Add backend status to `linkedout status`:
   - Check if `~/linkedout-data/state/backend.pid` exists AND process is running
   - Check if port is reachable: `GET http://localhost:{port}/health`
   - Report: `backend: running (PID 12345, port 8001)` or `backend: not running`

**Files to create:**
- `backend/src/linkedout/cli/commands/start_backend.py`
- `backend/src/linkedout/cli/commands/stop_backend.py` (internal)

**Files to modify:**
- `backend/src/linkedout/cli/cli.py` (register `start-backend` command)
- `backend/src/linkedout/cli/commands/status.py` (add backend status check)

**Acceptance criteria:**
- `linkedout start-backend` starts uvicorn, serves API on configured port
- `linkedout start-backend --background` daemonizes correctly, PID file written
- `linkedout status` reports backend running/not running
- Health check endpoint (`/health`) returns 200
- Port conflict produces clear error message with suggested resolution
- Process cleanup on SIGTERM is clean (no zombie processes)

**Complexity:** M

---

### 12F. Extension Logging Integration

**Goal:** Extension observability aligned with Phase 3 logging strategy (`docs/decision/logging-observability-strategy.md`).

**Implementation:**

1. **`devLog()` utility** (per decision doc section 13):
   Create `extension/lib/dev-log.ts`:
   ```typescript
   export function devLog(level: 'debug' | 'info' | 'warn' | 'error', component: string, message: string, data?: unknown): void
   ```
   - Only outputs in development mode (`import.meta.env.DEV`) or when `LINKEDOUT_DEBUG=true` in extension storage
   - Structured format: `[LinkedOut][{component}] {level}: {message}` + optional data
   - Components: `background`, `voyager`, `backend-client`, `side-panel`, `options`, `rate-limiter`

2. **Backend API call logging:**
   - Modify `extension/lib/backend/client.ts` → `request()` helper:
     - Log every fetch call: URL, method, status, duration_ms, error (if any)
     - Use `devLog('info', 'backend-client', ...)` for dev console
     - Append to activity log (existing `appendLog()`) for error cases only (don't spam activity log with successful calls)

3. **Rate limit event logging:**
   - Already logged in `extension/lib/rate-limiter.ts`. Verify entries include:
     - Which limit was hit (hourly vs daily)
     - Current count vs limit
     - Retry-after guidance

4. **Error aggregation badge:**
   - In `extension/entrypoints/background.ts`: track error count since last side panel open
   - Set badge text on extension icon: `browser.action.setBadgeText({ text: String(errorCount) })`
   - Clear badge when side panel opens (on `runtime.onConnect`)
   - Badge color: red (`#dc2626`)

5. **Correlation ID for extension → backend:**
   - Per decision doc: "nice-to-have but not critical for single-user local use"
   - **Defer to v2.** Do not implement in Phase 12.

**Files to create:**
- `extension/lib/dev-log.ts`

**Files to modify:**
- `extension/lib/backend/client.ts` (add devLog calls to `request()`)
- `extension/lib/rate-limiter.ts` (verify logging completeness)
- `extension/entrypoints/background.ts` (error badge logic)

**Acceptance criteria:**
- `devLog()` outputs structured logs in dev mode, silent in production
- Backend API errors are logged with status code, URL, and duration
- Error badge appears on extension icon when errors occur, clears on side panel open
- No console spam in production builds

**Complexity:** S

---

### 12G. Extension Documentation

**Goal:** Users understand the extension's capabilities, limitations, and troubleshooting steps.

**Implementation:**

1. Create `docs/extension.md` with sections:

   **a. Overview:**
   - What the extension does (LinkedIn profile crawling via Voyager API)
   - What it requires (backend API running on localhost)
   - What it's NOT (not a scraper, not automated bulk collection — it captures profiles you visit)

   **b. Voyager API fragility notes:**
   - The Voyager API is LinkedIn's internal API, not a public contract
   - Decoration IDs (currently `com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93`) can change without notice
   - LinkedIn may detect automated requests → CAPTCHA challenges
   - The extension mimics normal browser behavior but is inherently fragile
   - When Voyager changes: file a GitHub issue, maintainers will update the parser

   **c. Rate limit guidance (from `docs/decision/env-config-design.md`):**
   - Default: 30 profiles/hour, 150 profiles/day
   - These are self-imposed limits to avoid LinkedIn detection, not LinkedIn-imposed
   - Configurable via extension options page
   - If LinkedIn returns 429: extension auto-backs off, user sees "Rate limited" in side panel
   - Recommendation: leave defaults unless you have a specific reason to change

   **d. Troubleshooting:**
   | Symptom | Cause | Fix |
   |---------|-------|-----|
   | "Backend is unreachable" | Backend not running | Run `linkedout start-backend` |
   | Side panel shows nothing | Not on a LinkedIn profile page | Navigate to `linkedin.com/in/someone` |
   | "LinkedIn challenge detected" | LinkedIn CAPTCHA | Solve CAPTCHA in LinkedIn tab, click Retry |
   | "CSRF token expired" | LinkedIn session stale | Refresh the LinkedIn page |
   | Extension not visible in Chrome | Not sideloaded correctly | Re-follow sideloading instructions |
   | Profiles not appearing in `/linkedout` queries | Extension saves to DB but embeddings not generated | Run `linkedout embed` to generate embeddings for new profiles |

   **e. Architecture diagram:**
   ```
   LinkedIn Tab                Extension                    Backend (localhost:8001)
   ┌────────────┐         ┌──────────────┐              ┌───────────────┐
   │ Voyager    │◄────────│ content.ts   │              │ FastAPI       │
   │ API        │────────►│ (MAIN world) │              │               │
   └────────────┘         │              │              │ /crawled-     │
                          │ background.ts│─── fetch ───►│  profiles     │
                          │              │◄── JSON ─────│               │
                          │ side-panel/  │              │ /enrich       │
                          │ (React UI)   │              │               │
                          └──────────────┘              │ /health       │
                                                        └───────────────┘
                                                              │
                                                        ┌─────▼─────┐
                                                        │ PostgreSQL │
                                                        │ (local)    │
                                                        └───────────┘
   ```

2. Add extension section to main `README.md` (brief, links to `docs/extension.md`)

**Files to create:**
- `docs/extension.md`

**Files to modify:**
- `README.md` (add brief extension section with link)

**Acceptance criteria:**
- Voyager fragility is clearly communicated (users understand this is unofficial API)
- Every common error has a documented fix
- Architecture diagram is accurate against current codebase

**Complexity:** S

---

## Integration Points with Phase 0 Decisions

| Decision Doc | How Phase 12 Uses It |
|---|---|
| `cli-surface.md` | `linkedout start-backend` command spec (port, host, --background flags) |
| `env-config-design.md` | Extension config via `browser.storage.local` with `getConfig()` pattern. Backend URL from `VITE_BACKEND_URL` at build time, overridable at runtime. Config YAML for `backend_port`, `backend_host`. Tenant/BU/User IDs from config. |
| `logging-observability-strategy.md` | `devLog()` utility, backend call logging, error badge, no cross-boundary correlation IDs in v1 |
| `queue-strategy.md` | Extension enrichment endpoint blocks synchronously (3-5s per profile). Extension waits for response. Error logged to `~/linkedout-data/logs/`. |
| `2026-04-07-data-directory-convention.md` | Extension zip stored at `~/linkedout-data/extension/`. Backend PID file at `~/linkedout-data/state/backend.pid`. Backend logs at `~/linkedout-data/logs/backend.log`. |

---

## Testing Strategy

### Unit Tests (Extension — vitest)

| Test | File | What it covers |
|------|------|----------------|
| Config loading | `extension/lib/__tests__/config.test.ts` | `getConfig()` returns defaults when storage is empty, merges stored values, validates types |
| Options page rendering | `extension/entrypoints/options/__tests__/App.test.tsx` | Form renders with defaults, saves to storage, connection test button |
| Dev log utility | `extension/lib/__tests__/dev-log.test.ts` | Outputs in dev mode, silent in production, correct format |

### Unit Tests (Backend — pytest)

| Test | File | What it covers |
|------|------|----------------|
| Start-backend command | `backend/tests/unit/cli/test_start_backend.py` | Foreground mode starts uvicorn, background mode writes PID file, health check validation |
| Status with backend | `backend/tests/unit/cli/test_status.py` | Status reports backend running/not running based on PID file and port check |

### Integration Tests

| Test | What it covers |
|------|----------------|
| Extension build | CI workflow: `npm ci && wxt build && wxt zip` succeeds, zip is valid |
| Backend start/stop lifecycle | Start backend in background, verify health check, stop, verify stopped |
| Extension → Backend connectivity | Load extension, verify it can reach backend `/health` endpoint |

### Manual Testing Checklist (for SJ or contributors)

- [ ] Fresh sideload of extension zip works in Chrome 114+
- [ ] Extension detects LinkedIn profile pages correctly
- [ ] Side panel shows profile data after Voyager fetch
- [ ] Manual mode: profile data displayed, "Fetch" button saves to DB
- [ ] Auto mode: profile data fetched and saved automatically
- [ ] Rate limiting kicks in at configured thresholds
- [ ] Backend unreachable: extension shows offline banner
- [ ] Options page: change backend URL, verify it takes effect
- [ ] Options page: connection test button works
- [ ] `linkedout start-backend --background` starts and daemonizes correctly
- [ ] `linkedout status` shows backend status
- [ ] Error badge appears on extension icon after errors, clears on side panel open

---

## Exit Criteria Verification Checklist

Per `plan.collab.md` Phase 12 exit criteria:

- [ ] **User can install extension:** Pre-built zip downloads from GitHub Release, sideloads in Chrome successfully
- [ ] **User can crawl LinkedIn profiles:** Navigate to a LinkedIn profile, extension fetches Voyager data, sends to backend
- [ ] **Profiles appear in `/linkedout` queries:** Crawled profiles are in the database, queryable via the skill (may require `linkedout embed` for semantic search)
- [ ] **UX design doc approved:** `docs/design/extension-setup-ux.md` reviewed and approved by SJ before implementation
- [ ] **Extension build pipeline works:** GitHub Actions produces zip on release
- [ ] **Options page functional:** Users can configure backend URL and rate limits without rebuilding
- [ ] **Backend server manageable:** `linkedout start-backend` with daemon mode, health checks, status reporting
- [ ] **Logging integrated:** `devLog()` utility, backend call logging, error badge on extension icon
- [ ] **Documentation complete:** Voyager fragility, rate limits, troubleshooting all documented

---

## Task Execution Order

```
12A (UX Design Doc)          ← GATE: must be approved before any other task
    ↓
12B (Build Pipeline)  ───┐
12C (Options Page)    ───┤── can run in parallel (no dependencies between them)
12E (Backend Mgmt)    ───┤
12F (Logging)         ───┘
    ↓
12D (Extension Setup Skill)  ← depends on 12B, 12C, 12E all complete
    ↓
12G (Documentation)          ← last, captures final state
```

**Estimated complexity breakdown:**
- 12A: M (design, no code)
- 12B: S (single CI workflow file)
- 12C: M (options page + config refactor across multiple files)
- 12D: L (full skill with multi-step flow, error handling, idempotency)
- 12E: M (CLI command + daemon management + status integration)
- 12F: S (devLog utility + minor modifications)
- 12G: S (documentation writing)

---

## Resolved Decisions (2026-04-07, SJ)

1. **Minimum Chrome version:** **Chrome 114+, with version check on install.** Add a 5-line check in the extension that detects Chrome version and shows a clear error ("LinkedOut requires Chrome 114 or later") instead of a cryptic `setPanelBehavior is not a function`.

2. **Extension distribution:** **Ship zip.** Skill unzips to `~/linkedout-data/extension/chrome/`, user does "Load unpacked" from there. One artifact, one path, one set of instructions.

3. **Backend auto-start:** **Manual `linkedout start-backend` for v1.** Extension MUST detect "backend unreachable" and show an actionable error message: `Backend not running. Run "linkedout start-backend" or ask /linkedout-setup-report to diagnose.` No generic connection errors — every error state should reference specific CLI commands or skills for resolution.

4. **Extension update flow:** **Overwrite fixed path + instruct user to click refresh on `chrome://extensions`.** Upgrade skill unzips new version to same `~/linkedout-data/extension/chrome/` path. One-click refresh. No re-adding, no re-navigating to a new folder.

5. **`stop-backend` visibility:** **User-facing in `--help` as a convenience command.** Not part of the 13-command contract. Natural pair with `start-backend`.

### Cross-Phase Decisions Affecting This Phase

- **`start-backend` idempotency (Phase 6):** `start-backend` detects existing process on port, kills it, then starts fresh. No "address already in use" errors. Implemented in Phase 6's CLI refactor.
- **`/linkedout-extension-setup` skill:** Created HERE in Phase 12, not stubbed in Phase 8. Requires UX design gate approval before implementation.
- **Extension error messages:** ALL error states (backend unreachable, Chrome version too old, sideloading failures) must include actionable fix instructions referencing specific CLI commands or skills.
