# SP2: Extension Build Pipeline

**Phase:** 12 — Chrome Extension Add-on
**Sub-phase:** 2 of 7
**Dependencies:** SP1 (UX Design Doc approved by SJ)
**Estimated effort:** ~30 minutes
**Shared context:** `_shared_context.md`
**Phase plan tasks:** 12B

---

## Scope

Create a GitHub Actions workflow that builds and zips the Chrome extension on every release, uploading the zip as a release asset. Users download this zip to sideload — no Node.js required on their machine.

---

## Task 12B: Extension Build Pipeline

### Files to Create

**`.github/workflows/extension-build.yml`**

GitHub Actions workflow with:

- **Triggers:**
  - `release` event (type: `published`)
  - `workflow_dispatch` (manual trigger for testing)

- **Matrix:** Node.js 20 (LTS)

- **Steps:**
  1. Checkout repo
  2. `cd extension && npm ci`
  3. `wxt build` (produces `extension/.output/chrome-mv3/`)
  4. `wxt zip` (produces `extension/.output/linkedout-extension-*.zip`)
  5. Upload zip as GitHub Release asset via `gh release upload`

- **Build-time env:**
  - `VITE_BACKEND_URL=http://localhost:8001` (default, per `docs/decision/env-config-design.md`)

### Files to Modify

**`.gitignore` (root)**
- Verify that `extension/.output/` is excluded
- If not present in root `.gitignore`, add it (it should already be in `extension/.gitignore`)

### Decision Docs to Read

- `docs/decision/env-config-design.md` — `VITE_BACKEND_URL` default value

### Implementation Notes

- The workflow should be self-contained — no dependencies on other CI workflows
- The zip filename should include the version: `linkedout-extension-{version}.zip`
- Use `gh release upload` (GitHub CLI) to attach the zip to the release that triggered the workflow
- For `workflow_dispatch`, the zip can be uploaded as a workflow artifact instead (no release to attach to)

### Verification

- [ ] `.github/workflows/extension-build.yml` created with correct trigger events
- [ ] Workflow runs `npm ci`, `wxt build`, `wxt zip` in correct order
- [ ] `VITE_BACKEND_URL` is set to `http://localhost:8001` at build time
- [ ] Zip is uploaded as a release asset on `release` triggers
- [ ] `extension/.output/` is in `.gitignore`
- [ ] Workflow syntax is valid (check with `actionlint` or manual review)
