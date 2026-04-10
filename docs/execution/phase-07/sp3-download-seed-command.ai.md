# SP3: `linkedout download-seed` CLI Command

**Sub-Phase:** 3 of 6
**Tasks:** 7C (download-seed command)
**Complexity:** M
**Depends on:** SP1 (manifest schema definition)
**Blocks:** SP6 (integration testing)

---

## Objective

Implement the `linkedout download-seed` CLI command that downloads seed SQLite files from GitHub Releases with progress bar, checksum verification, and tier selection.

---

## Context

Read `_shared_context.md` for project-level context, CLI conventions, and data directory paths.

**Key constraints:**
- CLI follows Operation Result Pattern: Progress → Summary → Gaps → Next steps → Report path
- Downloads to `~/linkedout-data/seed/` (configurable via `LINKEDOUT_DATA_DIR`)
- GitHub Release URL: `https://github.com/sridherj/linkedout-oss/releases/download/<version>/`
- Override URL via `LINKEDOUT_SEED_URL` env var (for forks)
- Validates SHA256 checksums against `seed-manifest.json`

---

## Tasks

### 1. Create Download Seed Command

**File:** `backend/src/linkedout/cli/commands/download_seed.py` (NEW)

#### CLI Interface

```python
@click.command("download-seed")
@click.option("--full", is_flag=True, help="Download full dataset (~500MB) instead of core (~50MB)")
@click.option("--output", type=click.Path(), default=None, help="Download location (default: ~/linkedout-data/seed/)")
@click.option("--version", "release_version", default=None, help="Specific release version (default: latest)")
@click.option("--force", is_flag=True, help="Re-download even if file exists and checksum matches")
def download_seed(full, output, release_version, force):
    """Download seed company data from GitHub Releases."""
```

#### Download Flow

1. **Determine download directory:**
   - Use `--output` if provided
   - Otherwise `~/linkedout-data/seed/` (respect `LINKEDOUT_DATA_DIR` override)
   - Create directory if it doesn't exist

2. **Determine release version:**
   - If `--version` specified, use that
   - Otherwise, query GitHub API for latest release: `GET /repos/sridherj/linkedout-oss/releases/latest`
   - Use `LINKEDOUT_SEED_URL` env var as base URL override if set

3. **Download manifest:**
   - Fetch `seed-manifest.json` from the release (~1KB)
   - Parse and validate structure

4. **Select tier file:**
   - `--full` → select the file with `"tier": "full"`
   - Default → select the file with `"tier": "core"`

5. **Check existing file:**
   - If file exists at target path AND SHA256 matches manifest AND `--force` not set:
     - Print: `Seed data already downloaded (core v0.1.0, checksum OK). Use --force to re-download.`
     - Exit with success

6. **Download with progress:**
   - Stream download using `requests` or `urllib3`
   - Show progress bar with `tqdm` or `rich.progress`
   - Display: filename, tier, total size, download speed

7. **Verify checksum:**
   - Compute SHA256 of downloaded file
   - Compare against manifest
   - On mismatch: delete file, print error, exit with code 1

8. **Generate report:**
   - Write JSON report to `~/linkedout-data/reports/download-seed-YYYYMMDD-HHMMSS.json`
   - Include: version, tier, file size, checksum, download duration, source URL

9. **Print summary (Operation Result Pattern):**
   ```
   Downloaded: seed-core.sqlite (52 MB)
   Version:   0.1.0
   Checksum:  OK (SHA256 verified)
   Location:  ~/linkedout-data/seed/seed-core.sqlite

   Next steps:
     → Run `linkedout import-seed` to load data into PostgreSQL

   Report saved: ~/linkedout-data/reports/download-seed-20260407-142305.json
   ```

#### Error Handling

- **Network failure:** Clear message with retry guidance: `Download failed: {error}. Check your internet connection and try again.`
- **GitHub rate limiting:** Detect 403/429, suggest `GITHUB_TOKEN` env var or waiting
- **Invalid manifest:** `Manifest validation failed: {details}. The release may be corrupted.`
- **Checksum mismatch:** `Checksum verification failed. File may be corrupted. Try --force to re-download.`

### 2. GitHub Release URL Construction

```python
DEFAULT_REPO = "sridherj/linkedout-oss"
DEFAULT_BASE_URL = f"https://github.com/{DEFAULT_REPO}/releases/download"
GITHUB_API_BASE = f"https://api.github.com/repos/{DEFAULT_REPO}/releases"

def get_release_url(version: str | None = None) -> str:
    """Get the GitHub Release download URL.
    
    Checks LINKEDOUT_SEED_URL env var first (for forks).
    If version is None, queries GitHub API for latest.
    """
```

### 3. Checksum Verification

```python
def verify_checksum(filepath: Path, expected_sha256: str) -> bool:
    """Verify SHA256 checksum of a downloaded file."""
```

Reuse the same `compute_sha256` pattern from SP2 (or factor into a shared utility if both sub-phases are being implemented).

### 4. Register Command

**File:** `backend/src/linkedout/cli/cli.py`

Add `download_seed` to the CLI group:
```python
from linkedout.cli.commands.download_seed import download_seed
cli.add_command(download_seed)
```

### 5. Add tqdm Dependency

**File:** `backend/requirements.txt`

Add `tqdm` if not already present. Check first — it may already be a transitive dependency.

---

## Files to Create

| File | Description |
|------|-------------|
| `backend/src/linkedout/cli/commands/download_seed.py` | Download seed command |

## Files to Modify

| File | Changes |
|------|---------|
| `backend/src/linkedout/cli/cli.py` | Register `download-seed` command |
| `backend/requirements.txt` | Add `tqdm` if needed |

---

## Verification

### Unit Tests (for SP6 to implement, but design for testability)

Ensure the following are independently testable:
- `get_release_url()` with and without env var override
- `verify_checksum()` with correct and incorrect checksums
- Manifest parsing and validation
- Skip-if-exists logic
- Report generation

### Manual Checks
- `linkedout download-seed` downloads core seed file with progress bar
- `linkedout download-seed --full` downloads full seed file
- Running again without `--force` shows "already downloaded" message
- `--force` re-downloads even if file exists
- `--version 0.1.0` downloads a specific version
- Bad network → clear error message
- Report JSON is written to `~/linkedout-data/reports/`

---

## Acceptance Criteria

- [ ] `linkedout download-seed` downloads core seed (~50MB) with progress bar
- [ ] `--full` downloads full seed (~500MB)
- [ ] SHA256 checksum verified against `seed-manifest.json`
- [ ] Skip download if file exists and checksum matches (unless `--force`)
- [ ] `--version` downloads a specific release version
- [ ] `--output` overrides download directory
- [ ] `LINKEDOUT_SEED_URL` env var overrides GitHub Release URL
- [ ] Follows Operation Result Pattern in output
- [ ] Produces JSON report in `~/linkedout-data/reports/`
- [ ] Logs to `~/linkedout-data/logs/cli.log`
- [ ] Clear error messages for network failures and checksum mismatches
- [ ] Command registered in CLI entry point
