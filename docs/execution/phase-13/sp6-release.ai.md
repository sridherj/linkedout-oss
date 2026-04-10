# SP6: v0.1.0 Release

**Phase:** 13 — Polish & Launch
**Sub-phase:** 6 of 6
**Dependencies:** SP1 (roadmap), SP2 (docs), SP3 (test + observability validation), SP4 (CI + e2e), SP5 (good first issues) — ALL must be complete
**Estimated effort:** ~2 hours
**Shared context:** `_shared_context.md`

---

## Scope

Tag and publish the first official release (v0.1.0) with all required artifacts: source code, seed data, Chrome extension zip, and release notes. This is the final sub-phase — everything else must pass first.

**Tasks from phase plan:** 13H

---

## Task 13H: v0.1.0 Release

### Pre-release Validation Checklist

Before proceeding with any release work, verify ALL of these:

- [ ] All Tier 1 + 2 CI tests pass on `main` (check `.github/workflows/ci.yml`)
- [ ] Tier 3 installation tests pass on latest nightly run (check `.github/workflows/installation-test.yml`)
- [ ] E2E flow test (from SP4) passes
- [ ] Observability validation (from SP3) passes — `scripts/validate-observability.sh`
- [ ] All documentation (from SP2) is complete and linked from README
- [ ] Good first issues (from SP5) are created
- [ ] Roadmap (from SP1) is published
- [ ] `ROADMAP.md` exists and is linked from README

**If any check fails, STOP and report the failure. Do not proceed with the release.**

---

### Step 1: Update VERSION and CHANGELOG

#### VERSION file

**File to modify:** `VERSION` (repo root — should exist from Phase 10)

Set content to exactly: `0.1.0`

#### CHANGELOG.md

**File to modify:** `CHANGELOG.md` (repo root — should exist from Phase 1)

Add a v0.1.0 entry. Move items from `[Unreleased]` section to the new version section. Follow Keep a Changelog format:

```markdown
## [0.1.0] — 2026-XX-XX

### Highlights
- First public release of LinkedOut OSS
- AI-native professional network intelligence via Claude Code / Codex / Copilot skills
- Local-first: all data stays on your machine in ~/linkedout-data/
- 13 CLI commands under the `linkedout` namespace
- Dual embedding support: OpenAI (fast) or nomic-embed-text-v1.5 (free, local)
- Optional Chrome extension for LinkedIn profile crawling
- Comprehensive diagnostics and readiness reporting

### Features
- `/linkedout-setup` — AI-guided installation and configuration
- `/linkedout` — Natural language network queries
- `/linkedout-upgrade` — One-command updates
- Import from LinkedIn CSV and Google/iCloud contacts
- Affinity scoring with Dunbar tier classification
- Seed data: ~5K companies (core) or ~50-100K companies (full)
- Query history and usage reporting
- Structured operation reports for every command

### Technical
- PostgreSQL with pgvector for semantic search
- Loguru-based logging with per-component files
- Three-layer config: env vars > config.yaml > secrets.yaml
- Apache 2.0 license
- CI: lint + type check + integration tests + nightly installation tests
```

Replace `2026-XX-XX` with the actual release date.

---

### Step 2: Create Release Workflow

**File to create:** `.github/workflows/release.yml`

```yaml
name: Release

on:
  push:
    tags: ['v*.*.*']

permissions:
  contents: write  # needed for creating GitHub Releases

jobs:
  # Gate: run Tier 1 + 2 tests first
  test:
    uses: ./.github/workflows/ci.yml

  release:
    needs: test
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Build Chrome extension
        working-directory: extension
        run: |
          npm ci
          npx wxt build
          npx wxt zip

      - name: Verify seed data checksums
        run: |
          # Verify seed-manifest.json checksums match seed files
          # Implementation depends on where seed files are stored
          python scripts/verify-seed-checksums.py

      - name: Extract release notes from CHANGELOG
        id: changelog
        run: |
          # Extract the v0.1.0 section from CHANGELOG.md
          python -c "
          import re, sys
          content = open('CHANGELOG.md').read()
          match = re.search(r'## \[0\.1\.0\].*?\n(.*?)(?=\n## \[|$)', content, re.DOTALL)
          if match:
              print(match.group(1).strip())
          else:
              print('First public release of LinkedOut OSS')
          " > release_notes.txt

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          name: "v0.1.0 — First Public Release"
          body_path: release_notes.txt
          files: |
            extension/.output/*.zip
            seed-data/linkedout-seed-core.sqlite
            seed-data/linkedout-seed-full.sqlite
            seed-data/seed-manifest.json
          draft: false
          prerelease: false
```

#### Implementation notes
- The `test` job reuses the existing CI workflow as a gate
- Extension is built with `wxt build` + `wxt zip` (from Phase 12)
- Seed data files come from the Phase 7 pipeline — verify paths exist
- Release notes are extracted from CHANGELOG.md automatically
- Uses `softprops/action-gh-release@v2` for creating the release (widely used, well-maintained)
- `permissions: contents: write` needed for release creation

---

### Step 3: Release Artifacts Inventory

Verify all release artifacts exist and are ready:

| Artifact | Source | Path | Notes |
|----------|--------|------|-------|
| Source code (zip + tar.gz) | GitHub auto-generates | N/A | From tagged commit |
| `linkedout-seed-core.sqlite` | Phase 7 seed pipeline | `seed-data/` | ~50MB, core company set |
| `linkedout-seed-full.sqlite` | Phase 7 seed pipeline | `seed-data/` | ~500MB, full company set |
| `seed-manifest.json` | Phase 7 | `seed-data/` | Checksums, sizes, version |
| Chrome extension zip | Phase 12 WXT build | `extension/.output/` | Pre-built for sideloading |

If any artifact is missing, document what's needed and flag it as a blocker.

---

### Step 4: Tag and Release

**Do NOT execute these commands automatically.** Document them for SJ to run manually when ready:

```bash
# 1. Ensure you're on main with all changes committed
git checkout main
git pull origin main

# 2. Create annotated tag
git tag -a v0.1.0 -m "v0.1.0 — First Public Release"

# 3. Push tag (triggers release workflow)
git push origin v0.1.0

# 4. Monitor release workflow
gh run watch  # watch the triggered workflow
```

---

### Step 5: Post-Release Verification

After the release workflow completes, verify:

- [ ] GitHub Release exists at the repo's Releases page
- [ ] Release title is "v0.1.0 — First Public Release"
- [ ] Release notes contain the CHANGELOG content
- [ ] All 4 artifacts are attached (2 seed files, manifest, extension zip)
- [ ] Seed data checksums in `seed-manifest.json` match the uploaded assets
- [ ] Extension zip can be sideloaded in Chrome
- [ ] `linkedout download-seed` can download from the GitHub Release URL
- [ ] A fresh `git clone` + `/linkedout-setup` works using the release

---

## Verification

- [ ] `VERSION` file reads `0.1.0`
- [ ] `CHANGELOG.md` has a complete v0.1.0 entry with correct date
- [ ] `.github/workflows/release.yml` exists with correct triggers and steps
- [ ] Release workflow gates on Tier 1 + 2 tests passing
- [ ] Release workflow builds extension and attaches all artifacts
- [ ] Tag and release commands are documented (not auto-executed)
- [ ] Pre-release checklist items all passed

---

## Output Artifacts

- `VERSION` (modified — set to `0.1.0`)
- `CHANGELOG.md` (modified — add v0.1.0 entry)
- `.github/workflows/release.yml` (new)
- Documented tag + release commands for SJ to execute

---

## Post-Completion Check

1. `VERSION` file contains exactly `0.1.0` with no trailing newline issues
2. `CHANGELOG.md` follows Keep a Changelog format
3. Release workflow YAML is valid
4. No secrets or API keys hardcoded in the release workflow
5. Release workflow does NOT auto-announce (SJ controls timing)
6. Tag commands are documented, not executed — release timing is SJ's call

---

## IMPORTANT: Human Action Required

This sub-phase prepares all release infrastructure but does NOT execute the actual release. The final steps (tagging, pushing, announcing) require SJ's explicit approval and timing decision. Document everything clearly so SJ can execute when ready.
