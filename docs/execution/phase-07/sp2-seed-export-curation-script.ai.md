# SP2: Seed Export Curation Script

**Sub-Phase:** 2 of 6
**Tasks:** 7A (Seed Data Curation Script) + 7B (Seed Manifest generation)
**Complexity:** L
**Depends on:** SP1 (directory structure + manifest schema)
**Blocks:** SP5 (GitHub Release publishing)

---

## Objective

Build a maintainer-only script that connects to the production LinkedOut PostgreSQL database and exports the 10 seed tables into tiered SQLite files with a machine-readable manifest. This is NOT user-facing — it's a developer tool for regenerating seed data.

---

## Context

Read `_shared_context.md` for project-level context, entity schemas, and seed data scope.

**Key constraints:**
- Script connects to production DB via `DATABASE_URL` env var
- Exports 10 non-tenant-scoped tables (see shared context for list)
- Produces two SQLite files: `seed-core.sqlite` and `seed-full.sqlite`
- Generates `seed-manifest.json` alongside the SQLite files
- Must strip PII: email, phone, internal notes
- Must be idempotent — same source data produces identical output

---

## Tasks

### 1. Create Seed Export Script

**File:** `backend/src/dev_tools/seed_export.py` (NEW)

#### Entry point

```python
def main(output_dir: str, tiers: list[str] = ["core", "full"]):
    """Export seed data from PostgreSQL to SQLite files.
    
    Args:
        output_dir: Directory to write SQLite files and manifest
        tiers: Which tiers to export ("core", "full", or both)
    """
```

Make this runnable as: `python -m dev_tools.seed_export --output seed-data/`

Use `argparse` or Click (whichever is already used in `dev_tools/`). Include flags:
- `--output DIR` — output directory (required)
- `--tiers core,full` — comma-separated tiers to export (default: both)
- `--dry-run` — show what would be exported without writing

#### Core tier filter logic

For the "core" tier, include only companies where at least one `crawled_profile` has an `experience` record pointing to that company:

```sql
SELECT DISTINCT c.* FROM company c
JOIN experience e ON e.company_id = c.id
JOIN crawled_profile cp ON cp.id = e.profile_id
```

Then export all related data for those companies: aliases, funding rounds, startup tracking, growth signals, and all profiles/experience/education/skills linked to those companies.

#### Full tier filter logic

For the "full" tier, include all companies meeting any of:
- `employee_count > 0`
- Has at least one `funding_round` record
- `web_traffic_rank IS NOT NULL` (or equivalent web traffic indicator)

Include all related data for qualifying companies.

#### SQLite export

For each tier:
1. Create a new SQLite database file (`seed-{tier}.sqlite`)
2. Create tables mirroring the PostgreSQL schema (use column names/types from entity files)
3. Export rows from PostgreSQL, apply PII stripping, insert into SQLite
4. Create a `_metadata` table with:
   - `version` — semver string (e.g., "0.1.0")
   - `created_at` — ISO 8601 timestamp
   - `source_db_hash` — hash of the query results for reproducibility
   - `table_counts` — JSON string with per-table row counts

### 2. PII Stripping

Apply these rules during export:

| Table | Fields to strip | Fields to keep |
|-------|----------------|----------------|
| `crawled_profile` | `email`, `phone`, `internal_notes` (set to NULL) | `full_name`, `linkedin_url`, `headline`, `summary`, `photo_url` |
| All other tables | No PII fields | All fields retained |

Check entity definitions for exact column names — the names above are illustrative.

### 3. Manifest Generation

After SQLite files are written, generate `seed-manifest.json` in the output directory following the schema defined in SP1 (`seed-data/README.md`):

```python
def generate_manifest(output_dir: Path, files: list[dict]) -> None:
    manifest = {
        "version": VERSION,  # from a constant or CLI arg
        "created_at": datetime.utcnow().isoformat() + "Z",
        "files": []
    }
    for f in files:
        manifest["files"].append({
            "name": f["name"],
            "tier": f["tier"],
            "size_bytes": f["path"].stat().st_size,
            "sha256": compute_sha256(f["path"]),
            "table_counts": f["table_counts"]
        })
    (output_dir / "seed-manifest.json").write_text(json.dumps(manifest, indent=2))
```

### 4. SHA256 Checksum

```python
def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
```

### 5. Progress Reporting

Show progress during export:
- Per-table progress: `Exporting company... 4,521 rows`
- Summary at end: total rows exported per tier, file sizes, manifest path

---

## Files to Create

| File | Description |
|------|-------------|
| `backend/src/dev_tools/seed_export.py` | Seed export curation script |

## Files to Reference (Read-Only)

| File | Why |
|------|-----|
| All 10 entity files (see `_shared_context.md`) | Column names, types, PKs, FKs |
| `backend/src/shared/infra/db/db_session_manager.py` | DB session setup |
| `backend/src/dev_tools/seed_companies.py` | Existing patterns (reference only, don't extend) |

---

## Verification

### Manual Checks (requires production DB access)
- Run `python -m dev_tools.seed_export --output /tmp/seed-test/`
- Verify two SQLite files are created: `seed-core.sqlite`, `seed-full.sqlite`
- Verify `seed-manifest.json` is created with correct checksums and row counts
- Open SQLite files with `sqlite3` and verify table structure matches entity definitions
- Verify `_metadata` table exists with correct values
- Verify PII fields (email, phone) are NULL in `crawled_profile`
- Verify names, LinkedIn URLs, headlines are present
- Run script twice — verify output is byte-identical (idempotency)
- Run with `--dry-run` — verify no files written, only summary printed

### Unit Tests (can run without DB)
- Test `compute_sha256()` with known input
- Test manifest generation with mock file data
- Test PII stripping logic

---

## Acceptance Criteria

- [ ] Script connects to PostgreSQL via `DATABASE_URL` and exports 10 tables
- [ ] Core tier filters to companies with connected profiles
- [ ] Full tier filters to companies with employee count, funding, or web traffic
- [ ] PII (email, phone, internal notes) stripped from `crawled_profile`
- [ ] Each SQLite file has a `_metadata` table with version, timestamps, row counts
- [ ] `seed-manifest.json` generated with SHA256 checksums and file sizes
- [ ] Script is idempotent — same input produces same output
- [ ] `--dry-run` reports without writing
- [ ] Progress shown during export
