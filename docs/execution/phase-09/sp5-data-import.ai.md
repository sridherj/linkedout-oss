# Sub-Phase 5: Data Import Pipeline (CSV + Contacts + Seed)

**Phase:** 9 — AI-Native Setup Flow
**Plan tasks:** 9H (LinkedIn CSV Import), 9I (Contacts Import), 9J (Seed Data Setup)
**Dependencies:** sp4 (API keys + user profile configured)
**Blocks:** sp6
**Can run in parallel with:** —

## Objective
Build the guided data import modules: LinkedIn CSV import, optional contacts import, and seed data download/import. These three are grouped because they're all "get data into the database" steps that run sequentially after configuration is complete. Each wraps existing CLI commands with guided UX.

## Context
- Read shared context: `docs/execution/phase-09/_shared_context.md`
- Read plan (9H + 9I + 9J sections): `docs/plan/phase-09-setup-flow.md`
- Read UX design doc: `docs/design/setup-flow-ux.md` (use exact wording)
- Read CLI surface: `docs/decision/cli-surface.md`
- Read existing import pipeline: `backend/src/linkedout/import_pipeline/`
- Read CSV converter: `backend/src/linkedout/import_pipeline/converters/linkedin_csv.py`

## Deliverables

### 1. `backend/src/linkedout/setup/csv_import.py` (NEW)

Guided LinkedIn CSV import flow.

**Implementation:**

1. **Guidance step:**
   - Provide link to LinkedIn data export page
   - Step-by-step instructions: Settings → Data Privacy → Get a copy of your data → Connections
   - Note: LinkedIn takes ~10 minutes to prepare the export

2. **CSV file location:**
   - Auto-detect: scan `~/Downloads/` for files matching `Connections*.csv` or `connections*.csv`
   - If found: confirm with user ("Found Connections.csv in ~/Downloads/ — use this? [Y/n]")
   - If not found: prompt for path
   - Copy CSV to `~/linkedout-data/uploads/` for record-keeping

3. **Import execution:**
   - Run `linkedout import-connections <csv_path>` via subprocess or direct Python call
   - Show progress: "Importing connections... X/Y profiles"
   - Show result summary following Phase 3 operation result pattern

**Key functions:**
- `find_linkedin_csv(downloads_dir: Path | None = None) -> Path | None` — auto-detect CSV
- `prompt_csv_path(auto_detected: Path | None) -> Path` — confirm or prompt for path
- `copy_to_uploads(csv_path: Path, data_dir: Path) -> Path` — archive copy
- `run_csv_import(csv_path: Path) -> OperationReport` — execute import
- `setup_csv_import(data_dir: Path) -> OperationReport` — full orchestration

**Idempotency:**
- Re-running on same CSV produces "skipped: already imported" for existing profiles
- New profiles in a re-import are added without duplicating existing ones

### 2. `backend/src/linkedout/setup/contacts_import.py` (NEW)

Optional contacts import (Google CSV or iCloud vCard).

**Implementation:**

1. **Ask user:** "Would you like to import your Google or iCloud contacts? This adds phone numbers and emails to your network. [y/N]"

2. **If yes — Google Contacts:**
   - Guide: contacts.google.com → Export → Google CSV
   - Auto-detect in ~/Downloads/ (`contacts*.csv`, `google*.csv`)
   - Run `linkedout import-contacts <path> --format google`

3. **If yes — iCloud Contacts:**
   - Guide: icloud.com/contacts → Select All → Export vCard
   - Auto-detect in ~/Downloads/ (`*.vcf`)
   - Run `linkedout import-contacts <path> --format icloud`

4. **Reconciliation:** Import command automatically reconciles against existing LinkedIn connections.

**Key functions:**
- `prompt_contacts_import() -> bool` — ask if user wants to import
- `prompt_contacts_format() -> str` — "google" or "icloud"
- `find_contacts_file(format: str, downloads_dir: Path | None = None) -> Path | None`
- `run_contacts_import(path: Path, format: str) -> OperationReport`
- `setup_contacts_import(data_dir: Path) -> OperationReport` — full orchestration (returns early if user declines)

**Idempotency:** Reconciliation handles re-imports gracefully.

### 3. `backend/src/linkedout/setup/seed_data.py` (NEW)

Seed data download and import orchestration.

**Implementation:**

1. **Core seed (mandatory):**
   - Run `linkedout download-seed` — downloads core seed (~50MB) from GitHub Releases
   - Show download progress bar
   - Run `linkedout import-seed` — imports into local PostgreSQL
   - Show import progress with per-table counts

2. **Full seed (optional):**
   - Prompt: "Download the full company database (~500MB, ~50-100K companies)? This gives broader company intelligence. [y/N]"
   - If yes: `linkedout download-seed --full` then `linkedout import-seed`

3. **Checksum verification:** Both download commands verify SHA256 checksum from seed manifest.

**Key functions:**
- `download_seed(full: bool = False) -> OperationReport` — download with progress
- `import_seed() -> OperationReport` — import with per-table counts
- `verify_seed_checksum(seed_dir: Path) -> bool`
- `setup_seed_data(data_dir: Path) -> OperationReport` — full orchestration

**Idempotency:**
- Skip download if checksum matches existing file
- Import handles existing data gracefully (upsert or skip)

**Error handling:**
- Network failure: actionable error with retry instructions and manual download URL
- Checksum mismatch: re-download automatically
- Import failure: partial import is safe, re-running continues from where it stopped

### 4. Unit Tests

**`backend/tests/linkedout/setup/test_csv_import.py`** (NEW)
- `find_linkedin_csv()` finds `Connections.csv` in a temp ~/Downloads/ dir
- `find_linkedin_csv()` returns None when no matching file exists
- `find_linkedin_csv()` finds case-insensitive `connections.csv`
- `copy_to_uploads()` copies file to `~/linkedout-data/uploads/`
- `run_csv_import()` calls correct CLI command (mock subprocess)
- Invalid CSV path raises clear error

**`backend/tests/linkedout/setup/test_contacts_import.py`** (NEW)
- `find_contacts_file("google")` finds `contacts.csv` in ~/Downloads/
- `find_contacts_file("icloud")` finds `.vcf` files in ~/Downloads/
- Declining contacts import returns early with skip status
- `run_contacts_import()` calls correct CLI command with format flag (mock)

**`backend/tests/linkedout/setup/test_seed_data.py`** (NEW)
- `download_seed(full=False)` calls `linkedout download-seed` (mock)
- `download_seed(full=True)` calls `linkedout download-seed --full` (mock)
- `import_seed()` calls `linkedout import-seed` (mock)
- `verify_seed_checksum()` returns True for matching checksum
- `verify_seed_checksum()` returns False for mismatched checksum

## Verification
1. `python -c "from linkedout.setup.csv_import import find_linkedin_csv"` imports without error
2. `python -c "from linkedout.setup.contacts_import import setup_contacts_import"` imports without error
3. `python -c "from linkedout.setup.seed_data import setup_seed_data"` imports without error
4. `pytest backend/tests/linkedout/setup/test_csv_import.py -v` passes
5. `pytest backend/tests/linkedout/setup/test_contacts_import.py -v` passes
6. `pytest backend/tests/linkedout/setup/test_seed_data.py -v` passes

## Notes
- These modules are thin wrappers around existing CLI commands (`import-connections`, `import-contacts`, `download-seed`, `import-seed`). Don't duplicate the import logic — call the existing commands.
- Auto-detection in ~/Downloads/ should handle both macOS (`~/Downloads/`) and Linux (`~/Downloads/`) paths. Use `Path.home() / "Downloads"`.
- CSV file copy to `~/linkedout-data/uploads/` is for record-keeping only — the import reads from the original or copied file.
- The contacts import is entirely optional — "N" is the default. Don't pressure the user.
- Seed data download requires network. If offline, provide clear error with manual download instructions.
- Use exact prompt wording and progress format from UX design doc (sp1).
