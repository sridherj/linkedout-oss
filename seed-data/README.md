# Seed Data

LinkedOut ships a pre-populated company database so new installs have useful data
without running Apify enrichment. Seed data is published as a GitHub Release asset
(pg_dump file) and imported into your local PostgreSQL database.

## Quick Start

```bash
linkedout download-seed          # downloads seed dump + manifest
linkedout import-seed            # imports into PostgreSQL
```

## What's Included

Seed data covers 6 tables of public, non-tenant-scoped company reference data:

| Table | Description |
|-------|-------------|
| `company` | Company reference data |
| `company_alias` | Company name variations |
| `role_alias` | Job title normalization |
| `funding_round` | Public funding data |
| `startup_tracking` | Startup metrics |
| `growth_signal` | Growth indicators |

**Not included:**
- Profile data (`crawled_profile`, `experience`, `education`, `profile_skill`) — ships via the demo pipeline
- Tenant-scoped data (`connection`, `contact_source`, `enrichment_event`, etc.)

## Manifest Schema

The `seed-manifest.json` file is generated alongside the dump file and describes
the contents of the seed file. The download command validates seed files against
this manifest before import.

```json
{
  "version": "0.3.0",
  "created_at": "2026-04-13T12:00:00Z",
  "format": "pgdump",
  "files": [
    {
      "name": "seed.dump",
      "size_bytes": 52428800,
      "sha256": "abc123...",
      "table_counts": {
        "company": 237000,
        "company_alias": 0,
        "role_alias": 62000,
        "funding_round": 300,
        "startup_tracking": 400,
        "growth_signal": 0
      }
    }
  ]
}
```

### Manifest Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | `string` | Manifest schema version (semver) |
| `created_at` | `string` | ISO 8601 timestamp when seed files were generated |
| `format` | `string` | Seed file format (`"pgdump"`) |
| `files` | `array` | List of seed file entries |
| `files[].name` | `string` | Filename of the dump file |
| `files[].size_bytes` | `integer` | File size in bytes |
| `files[].sha256` | `string` | SHA-256 hex digest for integrity verification |
| `files[].table_counts` | `object` | Map of table name to row count |

## For Maintainers — Regenerating Seed Data

### Prerequisites

- Access to the production LinkedOut PostgreSQL database
- Python environment with project dependencies installed

### Steps

1. Run the export script:

   ```bash
   python -m dev_tools.seed_export --output seed-data/
   ```

   This produces:
   - `seed.dump` — seed data (pg_dump format)
   - `seed-manifest.json` — manifest describing the file

   Export uses a `_seed_staging` schema: filtered data is written to the staging
   schema, then `pg_dump` produces the `.dump` file.

2. Create a GitHub Release and upload both files as release assets
   (see [Publishing a Seed Data Release](#publishing-a-seed-data-release) below).

3. Users will download from:
   `https://github.com/sridherj/linkedout-oss/releases/download/<version>/`

   Forks can override this URL with the `LINKEDOUT_SEED_URL` environment variable.

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
   - `seed-data/seed.dump`
   - `seed-data/seed-manifest.json`

2. **Verify output:**

   ```bash
   # Check file size
   ls -lh seed-data/seed.dump

   # Verify manifest
   cat seed-data/seed-manifest.json | python -m json.tool

   # Spot-check data (restore to staging and query)
   pg_restore --list seed-data/seed.dump | head -20
   ```

3. **Create GitHub Release:**

   ```bash
   VERSION=$(jq -r '.version' seed-data/seed-manifest.json)

   gh release create "seed-v${VERSION}" \
     --title "Seed Data v${VERSION}" \
     --notes "Seed company database for LinkedOut OSS.

   **Dataset:** $(jq -r '.files[0] | "\(.table_counts.company) companies, \(.size_bytes / 1048576 | floor)MB"' seed-data/seed-manifest.json)

   Install: \`linkedout download-seed && linkedout import-seed\`" \
     seed-data/seed.dump \
     seed-data/seed-manifest.json
   ```

4. **Verify release:**

   ```bash
   # Test download command against the new release
   linkedout download-seed --version "seed-v${VERSION}" --force
   ```

### Release Naming Convention

- Tag format: `seed-v{semver}` (e.g., `seed-v0.3.0`)
- This keeps seed releases separate from code releases
- The `download-seed` command strips the `seed-v` prefix when constructing URLs

## PII Policy

Seed data contains only company reference data — no personal profile information.
Company names, websites, industries, and funding data are all public.
