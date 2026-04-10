# SP6: Extension Setup Skill

**Phase:** 12 — Chrome Extension Add-on
**Sub-phase:** 6 of 7
**Dependencies:** SP2 (Build Pipeline), SP3 (Options Page), SP4 (Backend Server Management), SP5 (Extension Logging)
**Estimated effort:** ~90 minutes
**Shared context:** `_shared_context.md`
**Phase plan tasks:** 12D

---

## Scope

Create the `/linkedout-extension-setup` skill that guides users through downloading the extension zip, sideloading it in Chrome, and starting the backend server. This skill depends on all implementation sub-phases being complete, as it references the build pipeline output, options page, and backend management commands.

---

## Task 12D: `/linkedout-extension-setup` Skill

### Files to Create

#### `skills/templates/linkedout-extension-setup.md.tmpl`

Skill template following the Phase 8 skill system pattern. Read `docs/design/extension-setup-ux.md` (produced in SP1) for the exact UX flow and wording.

#### Generated per-host skills:
- `skills/claude-code/linkedout-extension-setup.md`
- `skills/codex/linkedout-extension-setup.md`
- `skills/copilot/linkedout-extension-setup.md`

### Skill Flow

The skill must implement the flow defined in the UX design doc (SP1 output). The general structure:

**1. Prerequisites Check:**
- Verify Chrome is installed and version >= 114
- Verify backend is configured (`~/linkedout-data/config/config.yaml` exists)
- Verify database is set up (run `linkedout status --json`, check DB connected)
- Report pass/fail for each with actionable fix for failures

**2. Download Extension Zip:**
- Determine latest version from `linkedout version`
- Download from GitHub Releases URL: `https://github.com/sridherj/linkedout-oss/releases/download/v{version}/linkedout-extension-{version}.zip`
- Save to `~/linkedout-data/extension/linkedout-extension-{version}.zip`
- Unzip to `~/linkedout-data/extension/chrome/` (fixed path per resolved decision)
- Verify download integrity

**3. Sideloading Instructions:**
- Display step-by-step Chrome sideloading guide:
  1. Open `chrome://extensions`
  2. Enable "Developer mode" (top-right toggle)
  3. Click "Load unpacked" → navigate to `~/linkedout-data/extension/chrome/`
- Ask user to confirm when done

**4. Start Backend Server:**
- Run `linkedout start-backend --background`
- Verify backend is reachable: `curl -s http://localhost:8001/health`
- If port conflict: suggest `linkedout start-backend --port 8002` and remind to update extension options

**5. Verify Extension Connection:**
- Guide user: "Open any LinkedIn profile page. The LinkedOut side panel should appear when you click the extension icon."
- If backend unreachable from extension: guide to options page → update backend URL

**6. Summary:**
- Show what was set up
- Remind about `linkedout start-backend` being needed whenever extension is active
- Point to extension documentation (`docs/extension.md`)

### Decision Docs to Read

Before implementing, read:
- `docs/design/extension-setup-ux.md` — the UX design doc (SP1 output) — this is the primary reference for exact wording and flow
- `docs/decision/cli-surface.md` — `start-backend` command spec
- `docs/decision/2026-04-07-data-directory-convention.md` — where extension zip is stored
- `docs/decision/2026-04-07-skill-distribution-pattern.md` — skill template pattern, Agent Skills standard
- Read existing skill templates in `skills/templates/` to understand the pattern
- Read existing generated skills in `skills/claude-code/` to understand the output format

### Implementation Notes

- **Idempotency:** Re-running on an already-setup system should skip completed steps. Check each step's state before executing.
- **Error handling:** Every failure must include an actionable fix referencing specific CLI commands or skills (resolved decision).
- **Cross-host compatibility:** The template must generate correctly for all three hosts (Claude Code, Codex, Copilot). Host-specific differences should be minimal for this skill.
- The skill should NOT auto-start the backend without user consent — it should ask or at minimum inform.

### Verification

- [ ] Skill template exists at `skills/templates/linkedout-extension-setup.md.tmpl`
- [ ] Per-host skills generated for claude-code, codex, copilot
- [ ] Skill flow matches the UX design doc (`docs/design/extension-setup-ux.md`)
- [ ] Prerequisites check covers Chrome version, config, and database
- [ ] Download step uses correct GitHub Releases URL pattern
- [ ] Extension is unzipped to `~/linkedout-data/extension/chrome/` (fixed path)
- [ ] Sideloading instructions are clear and step-by-step
- [ ] Backend startup includes health check verification
- [ ] Port conflict handling suggests alternative port and options page update
- [ ] Skill is idempotent — re-running skips completed steps
- [ ] All error states include actionable fix guidance
- [ ] Summary references `docs/extension.md` for further documentation
