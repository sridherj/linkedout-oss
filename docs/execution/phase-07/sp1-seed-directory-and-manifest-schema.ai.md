# SP1: Seed Directory Structure + Manifest Schema

**Sub-Phase:** 1 of 6
**Tasks:** 7E (Seed Data Directory Structure) + 7B (Seed Manifest schema definition)
**Complexity:** S + S = S
**Depends on:** None (first sub-phase)
**Blocks:** SP2, SP3, SP4, SP5, SP6

---

## Objective

Establish the `seed-data/` directory in the repo, document the seed data pipeline for maintainers, define the manifest schema, and update `.gitignore` to exclude large seed files.

---

## Context

Read `_shared_context.md` for project-level context, architecture decisions, and seed data scope.

**Key constraints:**
- Seed SQLite files are too large for git — they're published as GitHub Release assets
- `seed-data/` directory exists in repo but only contains docs and `.gitkeep`
- Manifest schema must be documented so SP2 (curation script) can generate it and SP3 (download command) can validate against it

---

## Tasks

### 1. Create Seed Data Directory

Create `seed-data/` at the repo root:
- `seed-data/.gitkeep` — empty placeholder so the directory exists in git

### 2. Update .gitignore

**File:** `.gitignore` (at repo root)

Add these patterns to exclude seed data files from git:

```
# Seed data files (published as GitHub Release assets)
seed-data/*.sqlite
seed-data/*.db
seed-data/seed-manifest.json
```

### 3. Create seed-data/README.md

**File:** `seed-data/README.md` (NEW)

Document the seed data pipeline. Content should cover:

**Section 1: Overview**
- What seed data is and why it exists (pre-populated company database for fresh installs)
- Quick start: `linkedout download-seed && linkedout import-seed`
- What's included: 10 tables (list them), ~5K companies (core) or ~50-100K (full)
- What's NOT included: embeddings (run `linkedout embed` after import), tenant-scoped data

**Section 2: Tiers**
- Core (~50MB): companies where real connections work, full profile/role/funding data
- Full (~500MB): top global companies by employee count, funding, web traffic

**Section 3: Manifest Schema**
Document `seed-manifest.json` structure:

```json
{
  "version": "0.1.0",
  "created_at": "2026-04-07T12:00:00Z",
  "files": [
    {
      "name": "seed-core.sqlite",
      "tier": "core",
      "size_bytes": 52428800,
      "sha256": "abc123...",
      "table_counts": {
        "company": 5000,
        "company_alias": 8500,
        "role_alias": 1200,
        "funding_round": 3400,
        "startup_tracking": 2100,
        "growth_signal": 6700,
        "crawled_profile": 15000,
        "experience": 45000,
        "education": 18000,
        "profile_skill": 32000
      }
    },
    {
      "name": "seed-full.sqlite",
      "tier": "full",
      "size_bytes": 524288000,
      "sha256": "def456...",
      "table_counts": { ... }
    }
  ]
}
```

**Section 4: For Maintainers — Regenerating Seed Data**
- Prerequisites: access to the production LinkedOut PostgreSQL database
- Run the curation script: `python -m dev_tools.seed_export --output seed-data/`
- Script produces SQLite files + `seed-manifest.json`
- Publishing: create a GitHub Release, upload files as release assets

**Section 5: PII Policy**
- Email addresses, phone numbers, and internal notes are stripped
- Names, LinkedIn URLs, headlines, summaries, and photo URLs are retained (public data)
- No embeddings — users generate these locally with their chosen provider

---

## Files to Create

| File | Description |
|------|-------------|
| `seed-data/.gitkeep` | Directory placeholder |
| `seed-data/README.md` | Seed data pipeline documentation |

## Files to Modify

| File | Changes |
|------|---------|
| `.gitignore` | Add seed data exclusion patterns |

---

## Verification

### Manual Checks
- `seed-data/` directory exists in the repo
- `seed-data/.gitkeep` is committed
- `seed-data/README.md` is present and readable
- `.gitignore` contains patterns for `seed-data/*.sqlite`, `seed-data/*.db`, `seed-data/seed-manifest.json`
- Creating a file `seed-data/test.sqlite` does NOT show up in `git status`

---

## Acceptance Criteria

- [ ] `seed-data/` directory exists with `.gitkeep`
- [ ] `seed-data/README.md` documents overview, tiers, manifest schema, maintainer workflow, PII policy
- [ ] Manifest schema is clearly specified with all fields and types
- [ ] `.gitignore` excludes seed SQLite/DB files and manifest from git
- [ ] No new Python code in this sub-phase — docs and config only
