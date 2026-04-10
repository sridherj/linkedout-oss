# SP7: Extension Documentation

**Phase:** 12 — Chrome Extension Add-on
**Sub-phase:** 7 of 7
**Dependencies:** SP6 (Extension Setup Skill) — all implementation complete
**Estimated effort:** ~45 minutes
**Shared context:** `_shared_context.md`
**Phase plan tasks:** 12G

---

## Scope

Create comprehensive extension documentation and add an extension section to the main README. This is the final sub-phase — it captures the final state of all implementation work.

---

## Task 12G: Extension Documentation

### Files to Create

#### `docs/extension.md`

Create with the following sections:

**a. Overview:**
- What the extension does (LinkedIn profile crawling via Voyager API)
- What it requires (backend API running on localhost)
- What it's NOT (not a scraper, not automated bulk collection — it captures profiles you visit)
- How to install (link to `/linkedout-extension-setup` skill)

**b. Voyager API Fragility Notes:**
- The Voyager API is LinkedIn's internal API, not a public contract
- Decoration IDs (currently `com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93`) can change without notice
- LinkedIn may detect automated requests → CAPTCHA challenges
- The extension mimics normal browser behavior but is inherently fragile
- When Voyager changes: file a GitHub issue, maintainers will update the parser
- This section must be honest and upfront — don't downplay the fragility

**c. Rate Limit Guidance:**
Per `docs/decision/env-config-design.md`:
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
| Profiles not appearing in queries | Embeddings not generated | Run `linkedout embed` to generate embeddings |
| Error badge on extension icon | Background errors occurred | Open side panel to see details, badge clears |
| Options page not accessible | Extension not fully loaded | Reload extension from `chrome://extensions` |

**e. Architecture Diagram:**
Include the ASCII architecture diagram from the phase plan, verified against the actual codebase after implementation.

**f. Configuration Reference:**

| Setting | Default | Env Var | Config Key | Notes |
|---------|---------|---------|------------|-------|
| Backend URL | `http://localhost:8001` | `VITE_BACKEND_URL` (build) | runtime override via options | — |
| Backend port | `8001` | `LINKEDOUT_BACKEND_PORT` | `backend_port` | For CLI |
| Backend host | `127.0.0.1` | `LINKEDOUT_BACKEND_HOST` | `backend_host` | For CLI |
| Staleness days | `30` | `LINKEDOUT_STALENESS_DAYS` | — | Via options page |
| Hourly limit | `30` | `LINKEDOUT_RATE_LIMIT_HOURLY` | — | Via options page |
| Daily limit | `150` | `LINKEDOUT_RATE_LIMIT_DAILY` | — | Via options page |

### Files to Modify

#### `README.md`
Add a brief extension section with:
- One-paragraph description of what the extension does
- Link to `docs/extension.md` for full documentation
- Link to `/linkedout-extension-setup` for installation
- Note that the extension is optional — LinkedOut works fully without it for data already in the database

### Decision Docs to Read

Before writing documentation, read:
- `docs/decision/env-config-design.md` — all config keys, defaults, env vars
- `docs/decision/logging-observability-strategy.md` — extension logging behavior
- `docs/decision/queue-strategy.md` — synchronous enrichment (no queue)
- `docs/decision/2026-04-07-data-directory-convention.md` — file paths
- Read the actual implementation files to verify the architecture diagram and config reference are accurate

### Implementation Notes

- Documentation must reflect the **actual** implementation, not just the plan. Read the code produced by SP2-SP6 before writing.
- The Voyager API fragility section is critical for managing user expectations — be direct and honest.
- Every troubleshooting entry should reference a specific command or action.
- The architecture diagram should be verified against the actual codebase.

### Verification

- [ ] `docs/extension.md` created with all required sections (a-f)
- [ ] Voyager fragility is clearly and honestly communicated
- [ ] Rate limit defaults match `docs/decision/env-config-design.md`
- [ ] Every troubleshooting entry has a specific fix action
- [ ] Architecture diagram matches actual codebase
- [ ] Configuration reference is complete and accurate
- [ ] `README.md` has brief extension section linking to docs
- [ ] Extension section in README notes that extension is optional
- [ ] No prohibited content (Docker, Procrastinate, TaskOS, etc.)
