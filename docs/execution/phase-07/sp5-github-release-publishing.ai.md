# SP5: GitHub Release Publishing

**Sub-Phase:** 5 of 6
**Tasks:** 7F (GitHub Release Publishing)
**Complexity:** S
**Depends on:** SP2 (curation script must exist to document its usage)
**Blocks:** None

---

## Objective

Document the manual process for publishing seed data as GitHub Release assets and optionally create a GitHub Actions workflow for automation.

---

## Context

Read `_shared_context.md` for project-level context.

**Key facts:**
- Seed SQLite files are 50-500MB — too large for git, published as GitHub Release assets
- `seed-manifest.json` is published alongside the SQLite files
- `linkedout download-seed` (SP3) constructs URLs from: `https://github.com/sridherj/linkedout-oss/releases/download/<version>/`
- The curation script (SP2) generates both SQLite files and the manifest

---

## Tasks

### 1. Update seed-data/README.md with Release Process

**File:** `seed-data/README.md` (created in SP1, update the "For Maintainers" section)

Add a detailed release checklist:

```markdown
## Publishing a Seed Data Release

### Prerequisites
- Access to the production LinkedOut PostgreSQL database
- `gh` CLI installed and authenticated
- Write access to the `sridherj/linkedout-oss` repository

### Steps

1. **Generate seed files:**
   ```bash
   cd backend
   python -m dev_tools.seed_export --output ../seed-data/
   ```
   This produces:
   - `seed-data/seed-core.sqlite`
   - `seed-data/seed-full.sqlite`
   - `seed-data/seed-manifest.json`

2. **Verify output:**
   ```bash
   # Check file sizes
   ls -lh seed-data/seed-*.sqlite
   
   # Verify manifest
   cat seed-data/seed-manifest.json | python -m json.tool
   
   # Spot-check data
   sqlite3 seed-data/seed-core.sqlite "SELECT count(*) FROM company"
   ```

3. **Create GitHub Release:**
   ```bash
   VERSION=$(jq -r '.version' seed-data/seed-manifest.json)
   
   gh release create "seed-v${VERSION}" \
     --title "Seed Data v${VERSION}" \
     --notes "Seed company database for LinkedOut OSS.

   **Core tier:** $(jq -r '.files[] | select(.tier=="core") | "\(.table_counts.company) companies, \(.size_bytes / 1048576 | floor)MB"' seed-data/seed-manifest.json)
   **Full tier:** $(jq -r '.files[] | select(.tier=="full") | "\(.table_counts.company) companies, \(.size_bytes / 1048576 | floor)MB"' seed-data/seed-manifest.json)

   Install: \`linkedout download-seed && linkedout import-seed\`" \
     seed-data/seed-core.sqlite \
     seed-data/seed-full.sqlite \
     seed-data/seed-manifest.json
   ```

4. **Verify release:**
   ```bash
   # Test download command against the new release
   linkedout download-seed --version "seed-v${VERSION}" --force
   ```

### Release Naming Convention
- Tag format: `seed-v{semver}` (e.g., `seed-v0.1.0`)
- This keeps seed releases separate from code releases
- The `download-seed` command strips the `seed-v` prefix when constructing URLs
```

### 2. (Optional) GitHub Actions Workflow

**File:** `.github/workflows/release-seed-data.yml` (NEW, optional)

Create a manually-triggered workflow:

```yaml
name: Release Seed Data

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Seed data version (semver, e.g., 0.1.0)'
        required: true
      notes:
        description: 'Release notes'
        required: false
        default: 'Updated seed company database'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Download seed artifacts
        # Seed files must be pre-built and uploaded as workflow artifacts
        # or built by a separate CI job with DB access
        run: |
          echo "This workflow expects seed-core.sqlite, seed-full.sqlite, and seed-manifest.json"
          echo "to be available in the seed-data/ directory."
          echo "Build these locally with: python -m dev_tools.seed_export --output seed-data/"
          exit 1  # Placeholder — this needs the actual artifact source
      
      - name: Create Release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release create "seed-v${{ inputs.version }}" \
            --title "Seed Data v${{ inputs.version }}" \
            --notes "${{ inputs.notes }}" \
            seed-data/seed-core.sqlite \
            seed-data/seed-full.sqlite \
            seed-data/seed-manifest.json
```

**Note:** The GH Actions workflow is a nice-to-have. The manual `gh release create` process documented above is the primary path. The workflow is incomplete because it can't access the production database — seed files must be generated locally and uploaded. Consider adding artifact upload support in a future iteration.

---

## Files to Modify

| File | Changes |
|------|---------|
| `seed-data/README.md` | Add detailed release process documentation |

## Files to Create (Optional)

| File | Description |
|------|-------------|
| `.github/workflows/release-seed-data.yml` | Optional: manual release workflow |

---

## Verification

### Manual Checks
- `seed-data/README.md` has a complete, copy-pasteable release checklist
- Each `gh` command in the docs is syntactically correct
- Release naming convention (`seed-v{semver}`) is documented
- If GH Actions workflow is created, it passes YAML validation

---

## Acceptance Criteria

- [ ] `seed-data/README.md` documents the full manual release process
- [ ] Release steps are specific and copy-pasteable (not vague)
- [ ] Release tag naming convention documented (`seed-v{semver}`)
- [ ] Verification step included (test download after release)
- [ ] (Optional) GitHub Actions workflow created for manual triggering
