# Sub-Phase 05: Core `/linkedout-upgrade` Implementation

**Source task:** 10D
**Complexity:** L (largest sub-phase)
**Dependencies:** Sub-phases 02 (version), 03 (update check), 04 (logging/reporting)

## Objective

Implement the core upgrade flow: detect install type, pull latest code, update dependencies, run database migrations, execute version migration scripts, show "What's New" from CHANGELOG.md, and produce a structured upgrade report.

## Context

Read `_shared_context.md` for project-level context. Key decisions:
- Support only git clone install type in v1 (vendored deferred)
- Version migration scripts are Python with `migrate(config)` signature
- `linkedout migrate` wraps `alembic upgrade head` (internal-only command)
- Dirty working tree: refuse to upgrade with clear message
- Manual rollback instructions only (no automated `linkedout rollback`)
- Reports to `~/linkedout-data/reports/`, logs via loguru

## Deliverables

### Files to Create

1. **`backend/src/linkedout/upgrade/upgrader.py`** (extend from sub-phase 04)

   `Upgrader` class with methods:

   - `detect_install_type() -> str`: Check for `.git` directory → "git_clone". Log the detection.
   - `pre_flight_check() -> UpgradeStepResult`:
     - Check `git status --porcelain` — if dirty, refuse with message from UX design doc
     - Record current version from `VERSION` file
     - Return step result
   - `pull_code() -> UpgradeStepResult`:
     - `git fetch origin && git pull origin main` (or configured branch)
     - Handle failures: network, merge conflict
     - Return step result with details
   - `update_deps() -> UpgradeStepResult`:
     - `uv pip install -r requirements.txt` in existing venv
     - Handle failures: pip errors
     - Return step result
   - `run_migrations() -> UpgradeStepResult`:
     - Run `alembic upgrade head` (or `linkedout migrate`)
     - Record number of migrations applied
     - Handle failures: schema conflict, DB connection
     - Return step result with `migrations_applied` count
   - `run_version_scripts(from_ver, to_ver) -> UpgradeStepResult`:
     - Find scripts in `migrations/version/` matching version range
     - Execute in ascending version order
     - Each script is Python with `migrate(config)` function
     - Skip if no scripts found
     - Return step result
   - `post_upgrade_check() -> UpgradeStepResult`:
     - Run `linkedout status` (or equivalent health check)
     - Verify system is healthy
     - Return step result
   - `show_whats_new(from_ver, to_ver) -> str`:
     - Use `changelog_parser.py` to extract relevant CHANGELOG sections
     - Return formatted string
   - `run_upgrade() -> UpgradeReport`:
     - Orchestrates all steps in order
     - On failure at any step: stop, show rollback instructions, write report with failures
     - On success: show "What's New", write report
     - Uses logging infrastructure from sub-phase 04

2. **`backend/src/linkedout/upgrade/changelog_parser.py`**
   - `parse_changelog(old_version: str, new_version: str) -> str`
     - Reads `CHANGELOG.md` from repo root
     - Expects standard Keep a Changelog format with `## [X.Y.Z]` headers
     - Extracts all sections between old and new version
     - Returns formatted string (or empty string if no changelog or versions not found)

3. **`backend/src/linkedout/upgrade/version_migrator.py`**
   - `find_migration_scripts(from_ver: str, to_ver: str) -> list[Path]`
     - Looks in `migrations/version/` for Python files
     - Matches scripts applicable to the version range
     - Returns sorted by version (ascending)
   - `run_version_migrations(from_ver: str, to_ver: str, config) -> list[dict]`
     - Imports and calls `migrate(config)` on each script
     - Returns list of results (script name, status, duration)

4. **`migrations/version/README.md`**
   - Explains the version migration script pattern
   - Template for creating new scripts
   - Example: `v0_1_0_to_v0_2_0.py` with `migrate(config)` function

5. **`skills/claude-code/linkedout-upgrade/SKILL.md`**
   - The `/linkedout-upgrade` skill definition
   - Describes what the skill does, when to use it
   - Invokes `linkedout upgrade` CLI command

### Files to Modify

6. **`backend/src/dev_tools/cli.py`**
   - Add `linkedout upgrade` command
   - Creates `Upgrader` instance, calls `run_upgrade()`
   - Prints output per UX design doc format

### Tests to Create

7. **`backend/tests/unit/upgrade/test_changelog_parser.py`**
   - Correct extraction between two versions
   - Missing old version (extracts from start to new version)
   - Missing new version (extracts nothing gracefully)
   - Malformed markdown handling
   - Empty changelog

8. **`backend/tests/unit/upgrade/test_version_migrator.py`**
   - Script discovery in `migrations/version/`
   - Execution order (ascending version)
   - Skip-if-no-scripts (returns empty list)
   - Script with `migrate()` function called correctly

9. **`backend/tests/unit/upgrade/test_upgrader.py`** (extend from sub-phase 04)
   - Step orchestration: all steps called in order
   - Failure at each step produces correct rollback message
   - Dirty working tree detected and refused
   - Report structure correct on success and failure
   - "What's New" included in successful report

10. **`backend/tests/integration/upgrade/test_upgrade_with_migration.py`** (review finding 2026-04-07: highest-risk upgrade operation — expanded)
    - **Schema upgrade:** Set up DB with current schema, add a new Alembic migration, run upgrader, verify new schema applied (new table/column exists)
    - **Data preservation:** Insert test rows before upgrade, run migration, assert rows survive with correct values
    - **Migration failure:** Simulate a bad migration (e.g., add a NOT NULL column with no default to a populated table), verify upgrader reports error clearly and DB is not left in a half-migrated state
    - **Version migration scripts:** Place a test Python script in `migrations/version/`, verify it executes during upgrade in ascending version order
    - **No-op upgrade:** Run upgrade to same version, verify no migrations run, no data changes, report says "already current"

11. **`backend/tests/integration/upgrade/test_upgrade_report.py`**
    - Report file written to correct path
    - Report JSON valid and contains all required fields

## Acceptance Criteria

- [ ] `linkedout upgrade` detects git clone install type
- [ ] Dirty working tree → refuses with clear message
- [ ] Pulls latest code via `git fetch && git pull`
- [ ] Updates Python dependencies via `uv pip install`
- [ ] Runs Alembic migrations
- [ ] Runs version migration scripts (if any exist)
- [ ] Shows "What's New" from CHANGELOG.md
- [ ] Writes upgrade report to `~/linkedout-data/reports/upgrade-*.json`
- [ ] Records metrics event
- [ ] On failure: shows rollback instructions with exact commands
- [ ] On failure: system remains in working pre-upgrade state (report written with failure details)
- [ ] Re-running when already current: "Already running the latest version" message
- [ ] All unit tests pass with mocked externals
- [ ] Integration tests pass against real local DB
- [ ] `/linkedout-upgrade` skill definition exists

## Verification

```bash
# Run all upgrade unit tests
cd backend && python -m pytest tests/unit/upgrade/ -v

# Run integration tests (requires local PostgreSQL)
cd backend && python -m pytest tests/integration/upgrade/ -v

# Manual smoke test (in a test environment)
linkedout upgrade --dry-run  # if dry-run is implemented
```

## Notes

- This is the largest sub-phase — consider breaking implementation into:
  1. First: `Upgrader` class skeleton with `run_upgrade()` orchestration
  2. Then: individual step methods
  3. Then: changelog parser and version migrator
  4. Finally: CLI wiring and skill definition
- All subprocess calls (`git`, `uv`, `alembic`) should capture stdout/stderr for logging
- Use the UX design doc (sub-phase 01 output) for all user-facing text
- Rollback instructions template: `git checkout v{from_version} && linkedout migrate`
