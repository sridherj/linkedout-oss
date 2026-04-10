# UX Design: Chrome Extension Setup

**Phase:** 12 — Chrome Extension Add-on
**Task:** 12A — Design Gate
**Date:** 2026-04-07
**Status:** Draft — pending SJ review

---

## 1. `/linkedout-extension-setup` Skill Flow

The skill guides the user through six sequential steps. Each step checks preconditions before proceeding. The skill is idempotent — re-running it on an already-configured system skips completed steps.

---

### Step 1 — Prerequisites Check

The skill runs three checks and reports results inline.

**Check 1a: Chrome installed and version >= 114**

```
Checking Chrome version...
```

On success:
```
Chrome 126 detected. Meets minimum requirement (114+).
```

On failure (Chrome not found):
```
Chrome not found on this system.

LinkedOut's extension requires Google Chrome 114 or later.
Install Chrome from https://www.google.com/chrome/ and re-run /linkedout-extension-setup.
```

On failure (Chrome too old):
```
Chrome 112 detected. LinkedOut requires Chrome 114 or later.

The extension uses the Side Panel API (chrome.sidePanel), which was introduced in Chrome 114.
Update Chrome via chrome://settings/help and re-run /linkedout-extension-setup.
```

**Check 1b: Backend configured**

The skill checks that `~/linkedout-data/config/config.yaml` exists.

On success:
```
Backend config found at ~/linkedout-data/config/config.yaml.
```

On failure:
```
No LinkedOut config found at ~/linkedout-data/config/config.yaml.

Run /linkedout-setup first to configure LinkedOut, then come back to /linkedout-extension-setup.
```

**Check 1c: Database connected**

The skill runs `linkedout status --json` and checks the `db_connected` field.

On success:
```
Database connected. 4,012 profiles loaded.
```

On failure:
```
Database is not reachable.

Run `linkedout diagnostics` to troubleshoot, or re-run /linkedout-setup to reconfigure.
```

**Step summary on all checks passing:**
```
All prerequisites met. Proceeding to download the extension.
```

If any check fails, the skill stops with:
```
Prerequisites not met. Fix the issues above and re-run /linkedout-extension-setup.
```

---

### Step 2 — Download Extension

The skill determines the current version, downloads the extension zip from GitHub Releases, and extracts it.

**Determining version:**
```
Detecting LinkedOut version...
LinkedOut v0.1.0
```

**Downloading:**
```
Downloading extension zip from GitHub Releases...
  linkedout-extension-0.1.0.zip (2.1 MB)
  Saved to ~/linkedout-data/extension/linkedout-extension-0.1.0.zip
```

**Extracting:**
```
Extracting to ~/linkedout-data/extension/chrome/...
Done. Extension files ready at ~/linkedout-data/extension/chrome/
```

**On download failure (network error):**
```
Failed to download extension zip.

Error: Connection timed out reaching GitHub Releases.

Try again:
  curl -L -o ~/linkedout-data/extension/linkedout-extension-0.1.0.zip \
    https://github.com/{owner}/{repo}/releases/download/v0.1.0/linkedout-extension-0.1.0.zip

If the problem persists, download the zip manually from the GitHub Releases page
and place it at ~/linkedout-data/extension/linkedout-extension-0.1.0.zip,
then re-run /linkedout-extension-setup.
```

**On download failure (release not found):**
```
Failed to download extension zip.

Error: No extension zip found for v0.1.0 on GitHub Releases.

This version may not have a pre-built extension. Check the releases page
at https://github.com/{owner}/{repo}/releases for available versions,
or build from source: cd extension && npm ci && npx wxt build && npx wxt zip
```

**If extension already exists at the target path:**
```
Extension files already present at ~/linkedout-data/extension/chrome/.
Overwriting with v0.1.0...
Done. Extension files updated.
```

---

### Step 3 — Sideloading Instructions

The skill displays step-by-step sideloading instructions and waits for the user to confirm.

```
Now load the extension into Chrome. Follow these steps:

  1. Open Chrome and navigate to chrome://extensions
  2. Enable "Developer mode" using the toggle in the top-right corner
  3. Click "Load unpacked"
  4. In the file picker, navigate to:
       ~/linkedout-data/extension/chrome/
     and click "Select Folder" (or "Open" on Mac)
  5. You should see "LinkedOut" appear in your extensions list

If you already have LinkedOut loaded from a previous install,
click the refresh icon on the LinkedOut card in chrome://extensions instead.

Let me know when you've completed this step, or if you ran into any issues.
```

**On user confirming success:** Proceed to Step 4.

**On user reporting "Developer mode" issue:**
```
Developer mode must be enabled to sideload extensions.

On chrome://extensions, look for the "Developer mode" toggle in the top-right corner.
If your organization manages Chrome, developer mode may be disabled by policy —
check with your IT admin or use a personal Chrome profile.
```

**On user reporting the extension doesn't appear:**
```
If the extension didn't load:

  1. Make sure you selected the folder ~/linkedout-data/extension/chrome/
     (the folder containing manifest.json, not the parent folder)
  2. Check for error banners at the top of chrome://extensions
  3. Try removing and re-loading the extension

If Chrome shows "Manifest file is missing or unreadable":
  The zip may not have extracted correctly. Run:
    rm -rf ~/linkedout-data/extension/chrome/
  Then re-run /linkedout-extension-setup to re-download and extract.
```

---

### Step 4 — Start Backend Server

The skill starts the backend API server in the background.

```
Starting the backend server...
```

Running `linkedout start-backend --background`:

**On success:**
```
Backend started on http://localhost:8001 (PID: 12345).
Health check passed.
```

**On port conflict (LinkedOut process detected):**
```
Port 8001 is already in use by a LinkedOut backend (PID: 12340).

Restarting...
Backend started on http://localhost:8001 (PID: 12346).
Health check passed.
```

**On port conflict (non-LinkedOut process):**
```
Port 8001 is already in use by another process (PID: 12340).

LinkedOut will NOT stop an unknown process. Options:
  [1] Use a different port: linkedout start-backend --port 8002
      (then update Backend URL in the extension options page)
  [2] Stop the other process manually, then re-run /linkedout-extension-setup
```

Port conflict detection: check if `~/linkedout-data/state/backend.pid` exists AND its PID matches the process on port 8001. If yes, it's a LinkedOut process (safe to restart). If no, it's an unknown process (do not kill).

**On health check failure (backend started but not responding):**
```
Backend process started (PID: 12345) but health check failed after 10 seconds.

Check the backend log for errors:
  tail -50 ~/linkedout-data/logs/backend.log

Common causes:
  - Database not running: run `linkedout diagnostics` to check
  - Missing dependencies: run `pip install -e .` in the backend/ directory
  - Port blocked by firewall: try a different port with `linkedout start-backend --port 8002`
    (then update the backend URL in the extension options page)

After fixing the issue, run `linkedout start-backend --background` to retry.
```

**On database connection error during startup:**
```
Backend failed to start: cannot connect to database.

Run `linkedout diagnostics` to check your database configuration,
or re-run /linkedout-setup to reconfigure.
```

---

### Step 5 — Verify Extension Connection

The skill guides the user to verify the extension is working.

```
Let's verify the extension can talk to the backend.

  1. Open any LinkedIn profile page (e.g., linkedin.com/in/someone)
  2. Click the LinkedOut extension icon in Chrome's toolbar
  3. The side panel should open and show the profile information

What do you see?
```

**On user confirming the side panel shows data:**

The skill also checks for version mismatch between extension and backend:

```
The extension is connected and working.
```

If version mismatch detected:
```
The extension is connected, but there's a version mismatch:
  Extension: v0.1.0
  Backend:   v0.2.0

This may cause unexpected behavior. Update the extension:
  Re-run /linkedout-extension-setup to download the matching version.
```

**On user reporting "Backend is unreachable" in the side panel:**
```
The extension can't reach the backend server.

  1. Confirm the backend is running:
       linkedout status
     Look for "backend: running" in the output.

  2. If the backend is not running:
       linkedout start-backend --background

  3. If the backend is running but the extension still can't connect,
     check the backend URL in the extension options:
       Right-click the LinkedOut extension icon → Options
       Verify "Backend URL" is set to http://localhost:8001

  4. If you started the backend on a different port (e.g., 8002),
     update the Backend URL in the extension options to match.
```

**On user reporting the side panel is empty / nothing happens:**
```
The side panel only activates on LinkedIn profile pages.

Make sure you're on a URL that looks like:
  https://www.linkedin.com/in/someone-name/

The extension does not activate on LinkedIn's home feed, search results,
or company pages — only individual profile pages.

If you're on a profile page and still see nothing:
  1. Check chrome://extensions — is LinkedOut enabled?
  2. Click the LinkedOut extension icon in the toolbar to open the side panel manually
  3. Check for errors: right-click the extension icon → "Inspect popup" → Console tab
```

**On user reporting "LinkedIn challenge detected" (CAPTCHA):**
```
LinkedIn has detected automated activity and is showing a CAPTCHA challenge.

  1. Go to the LinkedIn tab (not the side panel)
  2. Solve the CAPTCHA challenge LinkedIn is showing
  3. After solving it, go back to the profile page
  4. Click "Retry" in the LinkedOut side panel

This is normal — LinkedIn occasionally challenges browser sessions.
If it happens frequently, reduce your crawling rate in the extension options.
```

---

### Step 6 — Summary

Shown after successful verification:

```
Extension setup complete.

What was set up:
  - LinkedOut Chrome extension loaded from ~/linkedout-data/extension/chrome/
  - Backend server running on http://localhost:8001

How to use:
  - Visit any LinkedIn profile page — the side panel shows profile data
  - In manual mode: click "Fetch" to save the profile to your database
  - In auto mode: profiles are saved automatically when you visit them
  - Query your network anytime with /linkedout

When you're done browsing LinkedIn:
  linkedout stop-backend

Next time you want to use the extension:
  linkedout start-backend --background

For troubleshooting, run:
  linkedout diagnostics
```

---

## 2. Backend Server Status Communication

The backend has three states. Each state is visible in multiple locations.

### State: Running

| Location | What the User Sees |
|---|---|
| `linkedout status` (CLI) | `backend: running (PID 12345, port 8001)` |
| Extension side panel | Profile data loads normally. No status banner. |
| Extension options page | Connection test shows green check: "Connected to LinkedOut backend v0.1.0" |

### State: Stopped (Not Running)

| Location | What the User Sees |
|---|---|
| `linkedout status` (CLI) | `backend: not running` |
| Extension side panel | Red banner at top: "Backend not running. Start it with: linkedout start-backend" |
| Extension options page | Connection test shows red X: "Cannot reach backend at http://localhost:8001" |

### State: Error (Process Running but Unhealthy)

| Location | What the User Sees |
|---|---|
| `linkedout status` (CLI) | `backend: error (PID 12345, port 8001 — health check failed)` |
| Extension side panel | Red banner at top: "Backend error. Check logs: tail ~/linkedout-data/logs/backend.log" |
| Extension options page | Connection test shows red X: "Backend returned an error. Run linkedout diagnostics to troubleshoot." |

### Backend Status Detection Logic

- **CLI (`linkedout status`):** Check if `~/linkedout-data/state/backend.pid` exists AND the process is alive AND `GET http://localhost:{port}/health` returns 200.
- **Extension (side panel, options page):** Attempt `GET {backendUrl}/health` on side panel open or on "Test Connection" click. Cache the result for 30 seconds to avoid repeated calls.

---

## 3. Error Messages (Exact Wording)

Every error message includes an actionable fix referencing specific CLI commands or skills.

| Error State | Where Shown | Exact Message | Resolution Guidance |
|---|---|---|---|
| Chrome too old (< 114) | Skill output | "Chrome {version} detected. LinkedOut requires Chrome 114 or later." | "The extension uses the Side Panel API introduced in Chrome 114. Update Chrome via chrome://settings/help and re-run /linkedout-extension-setup." |
| Developer mode not enabled | Skill output | "Developer mode must be enabled to sideload extensions." | "On chrome://extensions, enable the 'Developer mode' toggle in the top-right corner. If managed by your organization, use a personal Chrome profile." |
| Backend unreachable | Extension side panel | "Backend not running. Start it with: linkedout start-backend" | (Message is self-contained. Shown as a red banner at the top of the side panel.) |
| Port conflict on 8001 | CLI output | "Port 8001 is already in use." | "LinkedOut will stop the existing process and start fresh. If you need a different port: linkedout start-backend --port 8002 (then update Backend URL in extension options)." |
| Extension zip download failure | Skill output | "Failed to download extension zip. Error: {specific_error}" | "Try the curl command shown above to download manually, or download from the GitHub Releases page and place the zip at ~/linkedout-data/extension/linkedout-extension-{version}.zip." |
| LinkedIn CAPTCHA challenge | Extension side panel | "LinkedIn challenge detected. Solve the CAPTCHA in the LinkedIn tab, then click Retry." | (Shown as an amber warning banner in the side panel with a "Retry" button.) |
| CSRF token expired | Extension side panel | "LinkedIn session expired. Refresh the LinkedIn page to continue." | (Shown as an amber warning banner in the side panel. Auto-clears after page refresh.) |
| Rate limit hit (hourly) | Extension side panel | "Hourly crawl limit reached ({count}/{limit}). Resumes in {minutes} minutes." | (Shown as an amber info banner. Includes "Change limits in extension options" link.) |
| Rate limit hit (daily) | Extension side panel | "Daily crawl limit reached ({count}/{limit}). Resets tomorrow." | (Shown as an amber info banner. Includes "Change limits in extension options" link.) |
| Backend health check failed | CLI output | "Backend started but health check failed after 10 seconds." | "Check ~/linkedout-data/logs/backend.log for errors. Run linkedout diagnostics to troubleshoot." |
| Manifest file missing | chrome://extensions | Chrome shows: "Manifest file is missing or unreadable" | Skill guidance: "The zip may not have extracted correctly. Run: rm -rf ~/linkedout-data/extension/chrome/ then re-run /linkedout-extension-setup." |
| Database unreachable at startup | CLI output | "Backend failed to start: cannot connect to database." | "Run linkedout diagnostics to check your database configuration, or re-run /linkedout-setup to reconfigure." |

---

## 4. First Successful Crawl Experience

This documents what the user sees when the extension is working correctly for the first time.

### Step-by-step: First Profile Fetch

**1. Navigate to a LinkedIn profile**

The user visits `https://www.linkedin.com/in/someone/` in Chrome.

**2. Side panel activates**

The LinkedOut extension icon in the toolbar shows a subtle indicator. The user clicks it (or the side panel opens automatically if Chrome's side panel behavior is configured).

**3. Side panel: Loading state**

The side panel shows:
```
Loading profile data...
```
A spinner is visible while the Voyager API call completes (typically 1-2 seconds).

**4. Side panel: Profile loaded**

The side panel displays the profile summary:
- Full name
- Headline / current title
- Current company
- Location
- Profile photo (from LinkedIn)
- Connection degree (1st, 2nd, 3rd)
- Last updated timestamp (or "New profile" if first crawl)

**5. Manual mode: "Save to LinkedOut" button**

In manual mode (default), a primary action button appears:
```
[Save to LinkedOut]
```

The user clicks it. The button shows a brief spinner, then:
```
Profile saved to LinkedOut.
```

The button changes to a checkmark state indicating the profile is stored.

**6. Auto mode: Automatic save**

In auto mode, after the profile loads, the side panel shows:
```
Saving profile to LinkedOut...
Profile saved.
```

No user action required. A subtle success indicator appears.

**7. Enrichment (synchronous, 3-5 seconds)**

After saving, the backend runs synchronous enrichment:
- The side panel shows: "Enriching profile..." with a progress indicator
- On completion: "Profile enriched" with a checkmark

**8. Verify data in database**

The user can confirm the profile landed by running:
```
linkedout status
```

Which now shows an incremented profile count. Or by asking `/linkedout` a query like "what do you know about [person name]?"

**Important:** Newly crawled profiles are immediately available for exact-match queries (name, company, title). For semantic search ("who works in AI?"), embeddings must be generated. The backend auto-queues embedding for newly saved profiles when an OpenAI key is configured. For local embeddings, run `linkedout embed` periodically to cover new profiles.

The side panel shows a subtle indicator when a profile needs embedding:
```
Profile saved. Embedding pending — available for semantic search after next embed run.
```

---

## 5. Stopping the Backend

### How to stop

When the user is done using the extension:

```
linkedout stop-backend
```

Output:
```
Backend stopped.
```

### What happens if they forget

Nothing harmful. The backend:
- Listens only on `localhost` (127.0.0.1) — not accessible from the network
- Uses minimal resources when idle (no background processing)
- Will be cleaned up on system restart (process exits, PID file becomes stale)

The next `linkedout start-backend` detects the stale PID and cleans up automatically.

### Restarting the backend

Next time the user wants to use the extension:
```
linkedout start-backend --background
```

This is idempotent — safe to run even if the backend is already running.

---

## 6. Screenshot Placeholders

### Side Panel: Loading State

```
┌──────────────────────────────┐
│  ┌──┐  LinkedOut             │  400 x 300
│  └──┘                        │
│                              │
│      ◌  Loading profile...   │  Centered spinner with text
│                              │
│                              │
│                              │
│                              │
│                              │
└──────────────────────────────┘
```
- **Dimensions:** 400 x 300 px
- **Key elements:** LinkedOut logo/icon top-left, centered loading spinner, "Loading profile..." text
- **Background:** White (#ffffff)

### Side Panel: Profile Loaded (Manual Mode)

```
┌──────────────────────────────┐
│  ┌──┐  LinkedOut             │  400 x 600
│  └──┘                        │
│  ┌─────┐                     │
│  │photo│  Jane Smith         │  Profile photo, name, headline
│  │     │  VP Engineering     │
│  └─────┘  Acme Corp         │
│                              │
│  📍 San Francisco, CA        │  Location
│  🔗 1st degree connection    │  Connection degree
│                              │
│  ┌──────────────────────┐    │
│  │  Save to LinkedOut   │    │  Primary action button (blue)
│  └──────────────────────┘    │
│                              │
│  Last updated: New profile   │  Staleness info
│                              │
└──────────────────────────────┘
```
- **Dimensions:** 400 x 600 px
- **Key elements:** Profile photo (64x64), name (bold, 18px), headline, company, location, connection degree, "Save to LinkedOut" button (primary blue), last updated text
- **Highlight:** The "Save to LinkedOut" button is the primary CTA

### Side Panel: Backend Unreachable Error

```
┌──────────────────────────────┐
│  ┌──┐  LinkedOut             │  400 x 300
│  └──┘                        │
│ ┌──────────────────────────┐ │
│ │ ⚠ Backend not running.   │ │  Red banner (#dc2626 bg)
│ │ Start it with:           │ │  White text
│ │ linkedout start-backend  │ │  Monospace command text
│ └──────────────────────────┘ │
│                              │
│  Cannot load profile data    │  Gray secondary text
│  until the backend is        │
│  running.                    │
│                              │
└──────────────────────────────┘
```
- **Dimensions:** 400 x 300 px
- **Key elements:** Red error banner with exact CLI command, secondary explanation text below
- **Banner style:** Red background (#dc2626), white text, rounded corners, `linkedout start-backend` in monospace

### Side Panel: Rate Limit Warning

```
┌──────────────────────────────┐
│  ┌──┐  LinkedOut             │  400 x 200
│  └──┘                        │
│ ┌──────────────────────────┐ │
│ │ ⏳ Hourly crawl limit    │ │  Amber banner (#d97706 bg)
│ │ reached (30/30).         │ │  White text
│ │ Resumes in 23 minutes.   │ │
│ │                          │ │
│ │ Change limits in options │ │  Underlined link text
│ └──────────────────────────┘ │
│                              │
└──────────────────────────────┘
```
- **Dimensions:** 400 x 200 px
- **Key elements:** Amber warning banner with count, time remaining, and link to options page
- **Banner style:** Amber background (#d97706), white text, "Change limits in options" as a clickable link

### Options Page: Default Settings

```
┌──────────────────────────────────────────────┐
│  LinkedOut Extension Settings                │  600 x 700
│                                              │
│  Backend URL                                 │
│  ┌────────────────────────────────────────┐  │
│  │ http://localhost:8001                  │  │  Text input
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌──────────────────┐                        │
│  │ Test Connection   │                       │  Secondary button
│  └──────────────────┘                        │
│                                              │
│  Staleness Threshold (days)                  │
│  ┌────────────────────────────────────────┐  │
│  │ 30                                     │  │  Number input
│  └────────────────────────────────────────┘  │
│                                              │
│  Hourly Rate Limit                           │
│  ┌────────────────────────────────────────┐  │
│  │ 30                                     │  │  Number input
│  └────────────────────────────────────────┘  │
│                                              │
│  Daily Rate Limit                            │
│  ┌────────────────────────────────────────┐  │
│  │ 150                                    │  │  Number input
│  └────────────────────────────────────────┘  │
│                                              │
│  Enrichment Mode                             │
│  ○ Manual   ● Auto                           │  Radio/toggle
│                                              │
│  ▸ Advanced Settings                         │  Collapsed section
│                                              │
│  ┌──────────┐                                │
│  │   Save   │                                │  Primary button
│  └──────────┘                                │
│                                              │
└──────────────────────────────────────────────┘
```
- **Dimensions:** 600 x 700 px
- **Key elements:** Backend URL input, "Test Connection" button, staleness/rate limit number inputs, enrichment mode toggle, collapsible "Advanced Settings" section (containing Tenant ID, BU ID, User ID), Save button
- **Layout:** Single-column form, generous spacing, labels above inputs
- **Advanced Settings (collapsed by default):** Contains Tenant ID, BU ID, and User ID fields. These are pre-populated during setup and should not need changing for single-user installations. A help text inside the collapsed section explains: "These identifiers were set during /linkedout-setup. Most users never need to change them. They exist to support multi-user deployments."

### Options Page: Connection Test Success

```
┌──────────────────────────────────────────────┐
│  Backend URL                                 │  600 x 200
│  ┌────────────────────────────────────────┐  │
│  │ http://localhost:8001                  │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌──────────────────┐                        │
│  │ Test Connection   │                       │
│  └──────────────────┘                        │
│                                              │
│  ✓ Connected to LinkedOut backend v0.1.0     │  Green text (#16a34a)
│                                              │
└──────────────────────────────────────────────┘
```
- **Dimensions:** 600 x 200 px (detail crop)
- **Key elements:** Green checkmark + success message including backend version
- **Text style:** Green (#16a34a), normal weight

### Options Page: Connection Test Failure

```
┌──────────────────────────────────────────────┐
│  Backend URL                                 │  600 x 250
│  ┌────────────────────────────────────────┐  │
│  │ http://localhost:8001                  │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌──────────────────┐                        │
│  │ Test Connection   │                       │
│  └──────────────────┘                        │
│                                              │
│  ✗ Cannot reach backend at                   │  Red text (#dc2626)
│    http://localhost:8001                      │
│                                              │
│  Make sure the backend is running:           │  Gray help text
│    linkedout start-backend                   │  Monospace
│                                              │
└──────────────────────────────────────────────┘
```
- **Dimensions:** 600 x 250 px (detail crop)
- **Key elements:** Red X + error message, gray help text with the exact CLI command in monospace
- **Text style:** Error in red (#dc2626), help text in gray (#6b7280), command in monospace

---

## Appendix: Design Constraints Referenced

This document was written in accordance with the following decision documents:

| Decision Doc | Constraints Applied |
|---|---|
| `docs/decision/env-config-design.md` | Config defaults (backend port 8001, rate limits 30/150, staleness 30 days), `browser.storage.local` pattern, YAML config at `~/linkedout-data/config/config.yaml` |
| `docs/decision/cli-surface.md` | `linkedout start-backend` command spec (--port, --host, --background), `linkedout status`, `linkedout diagnostics`, `linkedout stop-backend` as convenience command |
| `docs/decision/logging-observability-strategy.md` | `devLog()` for extension, error badge on extension icon, backend logs at `~/linkedout-data/logs/backend.log` |
| `docs/decision/2026-04-07-data-directory-convention.md` | Extension zip at `~/linkedout-data/extension/`, PID file at `~/linkedout-data/state/backend.pid`, logs at `~/linkedout-data/logs/` |
