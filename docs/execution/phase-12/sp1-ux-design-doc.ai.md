# SP1: UX Design Doc (Design Gate)

**Phase:** 12 — Chrome Extension Add-on
**Sub-phase:** 1 of 7
**Dependencies:** None (first sub-phase — DESIGN GATE)
**Estimated effort:** ~60 minutes
**Shared context:** `_shared_context.md`
**Phase plan tasks:** 12A

---

## Scope

Create a comprehensive UX design document for the `/linkedout-extension-setup` skill and extension experience. This is a **DESIGN GATE** — SJ must review and approve this document before ANY implementation sub-phases begin.

**No code changes in this sub-phase. Design only.**

---

## Task 12A: UX Design Document

**File to create:** `docs/design/extension-setup-ux.md`

### Required Sections

#### 1. `/linkedout-extension-setup` Skill Flow

Document every step the skill shows the user, with exact wording:

**Step 1 — Prerequisites Check:**
- Check Chrome is installed and version >= 114
- Check backend is configured (`~/linkedout-data/config/config.yaml` exists)
- Check database is set up (run `linkedout status --json`, check DB connected)
- Define exact messages for each check passing/failing

**Step 2 — Download Extension:**
- Determine latest version from `linkedout version`
- Download from GitHub Releases URL
- Save to `~/linkedout-data/extension/linkedout-extension-{version}.zip`
- Unzip to `~/linkedout-data/extension/chrome/`
- Define messages for download progress, success, failure

**Step 3 — Sideloading Instructions:**
- Exact step-by-step text for Chrome sideloading:
  1. Open `chrome://extensions`
  2. Enable "Developer mode" (top-right toggle)
  3. Click "Load unpacked" → navigate to `~/linkedout-data/extension/chrome/`
- Ask user to confirm when done

**Step 4 — Start Backend Server:**
- Run `linkedout start-backend --background`
- Verify health check succeeds
- Messages for port conflicts

**Step 5 — Verify Extension Connection:**
- Guide user to open a LinkedIn profile page
- What success looks like (side panel appears, data loads)
- What failure looks like (backend unreachable banner)

**Step 6 — Summary:**
- What was set up
- How to use going forward
- How to stop backend when done

#### 2. Backend Server Status Communication

Define how the backend status is shown to the user:
- Running / stopped / error states
- Where each state is visible (CLI status, extension side panel, options page)
- Exact messages for each state

#### 3. Error Messages (Exact Wording)

Define the exact user-facing text for each error state:

| Error State | Where Shown | Exact Message | Resolution Guidance |
|---|---|---|---|
| Chrome too old (< 114) | Skill output | TBD | TBD |
| Developer mode not enabled | Skill output | TBD | TBD |
| Backend unreachable | Extension side panel | TBD | TBD |
| Port conflict on 8001 | CLI output | TBD | TBD |
| Extension zip download failure | Skill output | TBD | TBD |
| LinkedIn CAPTCHA challenge | Extension side panel | TBD | TBD |
| CSRF token expired | Extension side panel | TBD | TBD |
| Rate limit hit (hourly) | Extension side panel | TBD | TBD |
| Rate limit hit (daily) | Extension side panel | TBD | TBD |

**Key requirement:** Every error message MUST include an actionable fix referencing specific CLI commands or skills. No generic "connection failed" messages.

#### 4. First Successful Crawl Experience

Document what the user sees when the extension is working correctly:
- Navigate to LinkedIn profile
- Side panel appears
- Profile data loaded from Voyager API
- "Fetch" button (manual mode) or auto-save (auto mode)
- Success confirmation message
- How to verify data landed in DB (`linkedout status` or direct query)

#### 5. Stopping the Backend

- How the user stops the backend when done
- Exact command: `linkedout stop-backend`
- What happens if they forget (no harm — backend is localhost only)

#### 6. Screenshot Placeholders

For each key screen state, include a placeholder with:
- Dimensions (e.g., 400×300)
- Description of what would be shown
- Key UI elements to highlight

Screens to document:
- Extension side panel: loading state
- Extension side panel: profile loaded
- Extension side panel: backend unreachable error
- Extension side panel: rate limit warning
- Options page: default settings
- Options page: connection test success
- Options page: connection test failure

### Decision Docs to Read

Before writing the UX doc, read these for constraints:

- `docs/decision/env-config-design.md` — config defaults, `browser.storage.local` pattern, env var names
- `docs/decision/cli-surface.md` — `start-backend` command spec, CLI naming conventions
- `docs/decision/logging-observability-strategy.md` — `devLog()`, error badge behavior
- `docs/decision/2026-04-07-data-directory-convention.md` — where extension zip is stored, log paths

### Verification

- [ ] Every step of `/linkedout-extension-setup` is documented with exact wording
- [ ] All error states listed in phase plan have exact error messages defined
- [ ] Every error message includes actionable resolution guidance (specific commands/skills)
- [ ] Backend status communication is defined for all states
- [ ] First successful crawl experience is documented
- [ ] Screenshot placeholders are included with dimensions and descriptions
- [ ] File is written to `docs/design/extension-setup-ux.md`
- [ ] No code changes made — design only

### Gate Outcome

After creating `docs/design/extension-setup-ux.md`, stop and report to the orchestrator. SJ must review and approve before SP2-SP7 can proceed.
