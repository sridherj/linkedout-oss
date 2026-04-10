# Phase 10: Upgrade & Version Management — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Ready for implementation (after Design Gate approval)
**Phase Dependencies:** Phase 9 (Setup Flow) must be complete. Phases 8 (Skill System) and 3 (Logging & Observability) provide infrastructure used here.
**Can run in parallel with:** Phase 11 (Query History), Phase 12 (Chrome Extension)

---

## Phase Overview

**Goal:** Users can stay current with one command. The upgrade flow handles code updates, database migrations, extension updates, config changes, and version migration scripts — all through `/linkedout-upgrade` or the `auto_upgrade` config flag.

**What this phase delivers:**
1. A `VERSION` file at repo root as the single source of truth for the installed version
2. A non-blocking update notification shown when skills are invoked
3. A `/linkedout-upgrade` skill that pulls updates, runs migrations, and shows what's new
4. Snooze support with escalating backoff for update notifications
5. Extension zip upgrade flow (download + re-sideload instructions)
6. Full upgrade logging with rollback instructions on failure

**Phase 0 decisions that constrain this phase:**
- CLI uses flat `linkedout` namespace (`docs/decision/cli-surface.md`) — `linkedout version` and `linkedout migrate` are the relevant commands
- Config lives under `~/linkedout-data/` (`docs/decision/env-config-design.md`) — upgrade state files go there
- Logging uses loguru with human-readable format (`docs/decision/logging-observability-strategy.md`) — upgrade operations produce structured logs and reports
- No Procrastinate queue (`docs/decision/queue-strategy.md`) — upgrades run synchronously

---

## Design Gate

> **GATE: Before ANY implementation in this phase begins, produce `docs/design/upgrade-flow-ux.md`.**
>
> This document must specify:
> - What the user sees when an update is available (exact notification text)
> - What `/linkedout-upgrade` shows at each step
> - What "What's New" display looks like
> - Error/rollback messaging
>
> **SJ approval required before implementation.**

---

## Task Breakdown

### 10A. UX Design Doc

**Deliverable:** `docs/design/upgrade-flow-ux.md`

**Description:** Complete user-facing flow specification for the upgrade experience. This is the Design Gate artifact — no code is written until SJ approves this document.

**Contents to specify:**
1. Update notification format (one-line, non-blocking, shown during skill invocation)
2. Snooze confirmation text ("Remind me in 24h / 48h / 1 week / Don't remind again")
3. `/linkedout-upgrade` step-by-step output (detecting install type, pulling code, running migrations, showing changelog)
4. "What's New" display format (parsed from CHANGELOG.md between old and new version)
5. Error messages for each failure mode:
   - Git pull fails (dirty working tree, merge conflict, network)
   - Migration fails (schema conflict, DB connection)
   - Extension download fails (network, GitHub API)
6. Rollback instructions shown on failure (exact commands)
7. Auto-upgrade flow (silent, logs only, no terminal output)

**Acceptance criteria:**
- Every user-visible string is written out verbatim
- Every error scenario has an actionable recovery message
- SJ has approved the document

**Files:**
- Create: `docs/design/upgrade-flow-ux.md`

**Complexity:** M

---

### 10B. VERSION File & Version Utilities

**Deliverable:** `VERSION` file at repo root + version reading utility

**Description:** Establish the single source of truth for LinkedOut's installed version. The `VERSION` file contains a semver string (e.g., `0.1.0`). A small utility module reads this at runtime for CLI commands, skills, and upgrade checks.

**Acceptance criteria:**
- `VERSION` file exists at repo root with content `0.1.0`
- `linkedout version` reads from this file (already specified in CLI surface decision)
- Version is importable in Python: `from linkedout.version import __version__`
- Version is available to skills via `linkedout version --json`

**Files:**
- Create: `VERSION` (repo root)
- Create: `backend/src/linkedout/version.py` — reads `VERSION` file, exposes `__version__`, `get_version_info()` returning dict with version, python version, pg version, install path, config path, data dir
- Modify: `backend/pyproject.toml` — add `linkedout` entry point (or ensure the future CLI refactor in Phase 6E uses this module)
- Modify: `backend/src/dev_tools/cli.py` — wire `linkedout version` command to use `version.py`

**Integration with Phase 0 decisions:**
- `linkedout version` displays ASCII logo from `docs/brand/logo-ascii.txt` per `docs/decision/cli-surface.md`
- Config path shown is `~/linkedout-data/config/config.yaml` per `docs/decision/env-config-design.md`

**Complexity:** S

---

### 10C. Update Check Mechanism

**Deliverable:** Non-blocking update check on skill invocation

**Description:** When a LinkedOut skill is invoked, check whether a newer version is available. The check compares the local `VERSION` file against the latest GitHub Release tag. Results are cached to avoid excessive API calls.

**Acceptance criteria:**
- Check runs on skill invocation (triggered by skills calling `linkedout status` or a dedicated `linkedout check-update` internal command)
- GitHub API call is throttled: max once per hour, cached to `~/linkedout-data/state/update-check.json`
- If outdated, prints a single non-blocking line: `LinkedOut vX.Y.Z available (you have vA.B.C). Run /linkedout-upgrade`
- If up-to-date or check fails (network error), prints nothing
- Never blocks or prevents usage
- Respects snooze state (see 10E)

**Files:**
- Create: `backend/src/linkedout/upgrade/update_checker.py`
  - `check_for_update() -> UpdateInfo | None` — calls GitHub Releases API, compares semver
  - `get_cached_update() -> UpdateInfo | None` — reads cache, returns if still valid (< 1h old)
  - `save_update_cache(info: UpdateInfo)` — writes to state file
- Create: `backend/src/linkedout/upgrade/__init__.py`
- Create/modify: `~/linkedout-data/state/update-check.json` (runtime, not in repo)
  - Format: `{"checked_at": "ISO timestamp", "latest_version": "X.Y.Z", "current_version": "A.B.C", "release_url": "https://...", "is_outdated": true}`

**Integration with Phase 0 decisions:**
- State file lives under `~/linkedout-data/state/` per `docs/decision/env-config-design.md`
- Uses loguru for logging the check result per `docs/decision/logging-observability-strategy.md`

**Complexity:** M

---

### 10D. `/linkedout-upgrade` Implementation

**Deliverable:** Full upgrade skill and supporting CLI infrastructure

**Description:** The core upgrade flow. Detects how LinkedOut was installed (git clone vs vendored copy), pulls the latest code, runs database migrations, executes version migration scripts, and shows "What's New" from CHANGELOG.md.

**Acceptance criteria:**
- Detects install type:
  - **Git clone:** `git pull origin main` (or configured branch)
  - **Vendored copy:** Clone to temp dir, copy files over, preserve `~/linkedout-data/`
- Records pre-upgrade version for rollback reference
- Runs `linkedout migrate` (Alembic `upgrade head`) — the internal-only command from CLI surface decision
- Runs version migration scripts if any exist: `migrations/version/v{old}_to_v{new}.sh` (or `.py`)
- Parses CHANGELOG.md between old and new version, displays "What's New"
- Updates `~/linkedout-data/state/.last-upgrade-version` with new version
- Produces an upgrade report to `~/linkedout-data/reports/upgrade-YYYYMMDD-HHMMSS.json`
- On failure at any step: shows rollback instructions (exact git commands), does not leave system in broken state

**Sub-steps of the upgrade flow:**
1. Pre-flight: check git status (warn if dirty), record current version
2. Pull code: `git fetch && git pull` (or vendored swap)
3. Update Python deps: `uv pip install -r requirements.txt` (in existing venv)
4. Run migrations: `linkedout migrate` (wraps `alembic upgrade head`)
5. Run version scripts: execute any `migrations/version/v*.py` scripts for the version range
6. Update extension: if extension installed, download latest zip (see 10F)
7. Post-upgrade check: `linkedout status` to verify system health
8. Show "What's New": parsed CHANGELOG.md section
9. Write upgrade report and update state files

**Files:**
- Create: `backend/src/linkedout/upgrade/upgrader.py`
  - `Upgrader` class with methods: `detect_install_type()`, `pre_flight_check()`, `pull_code()`, `update_deps()`, `run_migrations()`, `run_version_scripts()`, `post_upgrade_check()`, `show_whats_new()`
  - Each method logs via loguru, produces structured output
- Create: `backend/src/linkedout/upgrade/changelog_parser.py`
  - `parse_changelog(old_version, new_version) -> str` — extracts relevant sections from CHANGELOG.md
  - Expects standard Keep a Changelog format with `## [X.Y.Z]` headers
- Create: `backend/src/linkedout/upgrade/version_migrator.py`
  - `run_version_migrations(from_ver, to_ver)` — finds and executes scripts in `migrations/version/`
  - Scripts are Python files with a `migrate()` function
- Create: `migrations/version/` directory (initially empty, with a README explaining the pattern)
- Modify: `backend/src/dev_tools/cli.py` — add `linkedout upgrade` command (or wire into future CLI from Phase 6E)
- Create: `skills/claude-code/linkedout-upgrade/SKILL.md` — the `/linkedout-upgrade` skill definition (or template per Phase 8 skill system)

**Integration with Phase 0 decisions:**
- `linkedout migrate` is internal-only per `docs/decision/cli-surface.md` — not shown in `--help`
- Reports saved to `~/linkedout-data/reports/` per `docs/decision/env-config-design.md`
- Upgrade logging follows operation result pattern from `docs/decision/logging-observability-strategy.md`

**Complexity:** L

---

### 10E. Snooze Support

**Deliverable:** Escalating backoff for update notifications + auto-upgrade config option

**Description:** Users who dismiss the update notification get reminded with escalating intervals. Users who want hands-off upgrades can enable auto-upgrade.

**Acceptance criteria:**
- Snooze escalation: 24h -> 48h -> 1 week
- Snooze state persisted to `~/linkedout-data/state/update-snooze.json`
  - Format: `{"snoozed_at": "ISO", "snooze_count": 1, "next_reminder": "ISO", "snoozed_version": "X.Y.Z"}`
- Snooze resets when a new version is detected (different from snoozed version)
- `auto_upgrade: true` in `~/linkedout-data/config/config.yaml` enables silent auto-upgrade:
  - On skill invocation, if update available, run upgrade silently
  - Log output to `~/linkedout-data/logs/cli.log`, no terminal output
  - If upgrade fails, fall back to notification mode (don't block user)
- `auto_upgrade: false` (default) — notification only

**Files:**
- Modify: `backend/src/linkedout/upgrade/update_checker.py` — add snooze logic to `check_for_update()`
  - `is_snoozed(version) -> bool`
  - `snooze_update(version)`
  - `reset_snooze()`
- Runtime file: `~/linkedout-data/state/update-snooze.json`
- Modify: config schema in `backend/src/shared/config/config.py` (or future `LinkedOutSettings`) — add `auto_upgrade: bool = False`

**Integration with Phase 0 decisions:**
- Config lives in `~/linkedout-data/config/config.yaml` per `docs/decision/env-config-design.md`
- State files under `~/linkedout-data/state/` per same decision

**Complexity:** M

---

### 10F. Extension Upgrade

**Deliverable:** Download latest pre-built extension zip + re-sideload instructions

**Description:** If the user has the Chrome extension installed, `/linkedout-upgrade` also downloads the latest extension zip from GitHub Releases and provides re-sideload instructions.

**Acceptance criteria:**
- Detects if extension was previously installed (check for `~/linkedout-data/extension/` or extension config marker)
- Downloads latest extension zip from GitHub Releases to `~/linkedout-data/extension/linkedout-extension-vX.Y.Z.zip`
- Verifies checksum (SHA256 from release metadata)
- Shows re-sideload instructions:
  1. Open `chrome://extensions`
  2. Remove old LinkedOut extension
  3. Drag-and-drop new zip (or "Load unpacked" after extracting)
- Does NOT attempt to auto-install the extension (not possible with sideloaded extensions)
- If download fails (network), shows error and continues upgrade (extension update is non-blocking)

**Files:**
- Create: `backend/src/linkedout/upgrade/extension_updater.py`
  - `check_extension_installed() -> bool`
  - `download_extension_zip(version) -> Path`
  - `verify_checksum(path, expected_sha256) -> bool`
  - `get_sideload_instructions() -> str`
- Runtime directory: `~/linkedout-data/extension/` (stores downloaded zips)

**Integration with Phase 0 decisions:**
- Extension zip published as GitHub Release asset (defined in plan Phase 12B)
- Downloads to `~/linkedout-data/` per `docs/decision/env-config-design.md`

**Complexity:** M

---

### 10G. Upgrade Logging & Reporting

**Deliverable:** Comprehensive upgrade logging with structured report output

**Description:** Every step of the upgrade process produces structured logs and a final upgrade report. On failure, rollback instructions are displayed.

**Acceptance criteria:**
- Every upgrade step logs start/success/failure with timing via loguru
- Component binding: `component="cli"`, `operation="upgrade"`
- Correlation ID per upgrade invocation: `cli_upgrade_YYYYMMDD_HHMM`
- Final upgrade report written to `~/linkedout-data/reports/upgrade-YYYYMMDD-HHMMSS.json`
- Report follows the standard `OperationReport` format from Phase 3K:
  ```json
  {
    "operation": "upgrade",
    "timestamp": "2026-04-07T14:30:00Z",
    "duration_ms": 15000,
    "from_version": "0.1.0",
    "to_version": "0.2.0",
    "counts": {
      "total_steps": 7,
      "succeeded": 7,
      "skipped": 0,
      "failed": 0
    },
    "steps": [
      {"step": "pre_flight", "status": "success", "duration_ms": 100},
      {"step": "pull_code", "status": "success", "duration_ms": 3000},
      {"step": "update_deps", "status": "success", "duration_ms": 5000},
      {"step": "run_migrations", "status": "success", "duration_ms": 2000, "migrations_applied": 2},
      {"step": "version_scripts", "status": "skipped", "detail": "no scripts for 0.1.0 -> 0.2.0"},
      {"step": "extension_update", "status": "success", "detail": "downloaded v0.2.0 zip"},
      {"step": "post_check", "status": "success", "detail": "linkedout status: healthy"}
    ],
    "whats_new": "## [0.2.0] - 2026-04-15\n- Added semantic search\n- Fixed affinity computation for large networks",
    "next_steps": ["Re-sideload extension from ~/linkedout-data/extension/linkedout-extension-v0.2.0.zip"],
    "failures": [],
    "rollback": "git checkout v0.1.0 && linkedout migrate"
  }
  ```
- On failure: print rollback instructions to terminal (exact git commands to revert)
- Metrics event: `{"metric": "upgrade", "from": "0.1.0", "to": "0.2.0", "status": "success", "duration_ms": 15000}`

**Files:**
- Integrated into `backend/src/linkedout/upgrade/upgrader.py` — each step method returns a structured result
- Uses `OperationReport` from Phase 3K (or defines a compatible structure if Phase 3 is not yet complete)
- Writes to `~/linkedout-data/reports/` and `~/linkedout-data/metrics/daily/`

**Integration with Phase 0 decisions:**
- Loguru with human-readable format per `docs/decision/logging-observability-strategy.md`
- Reports dir per `docs/decision/env-config-design.md`
- Follows operation result pattern: Progress -> Summary -> Failures -> Report path

**Complexity:** M

---

## File-Level Implementation Summary

### New files to create

| File | Type | Description |
|------|------|-------------|
| `VERSION` | Data | Semver version string (e.g., `0.1.0`) |
| `docs/design/upgrade-flow-ux.md` | Design | UX specification for upgrade flow (Design Gate) |
| `backend/src/linkedout/version.py` | Code | Version reading utility, `__version__`, `get_version_info()` |
| `backend/src/linkedout/upgrade/__init__.py` | Code | Package init |
| `backend/src/linkedout/upgrade/update_checker.py` | Code | GitHub Release check, caching, snooze logic |
| `backend/src/linkedout/upgrade/upgrader.py` | Code | Core upgrade orchestration (detect, pull, migrate, report) |
| `backend/src/linkedout/upgrade/changelog_parser.py` | Code | Parse CHANGELOG.md between version ranges |
| `backend/src/linkedout/upgrade/version_migrator.py` | Code | Find and run version migration scripts |
| `backend/src/linkedout/upgrade/extension_updater.py` | Code | Extension zip download and checksum verification |
| `migrations/version/README.md` | Docs | Explains the version migration script pattern |
| `skills/claude-code/linkedout-upgrade/SKILL.md` | Skill | `/linkedout-upgrade` skill definition |

### Existing files to modify

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `linkedout` CLI entry point (Phase 6E prerequisite) |
| `backend/src/dev_tools/cli.py` | Add `upgrade` and `version` commands (or integrate into future `linkedout` CLI) |
| `backend/src/shared/config/config.py` | Add `auto_upgrade: bool` setting |

### Runtime files (not in repo, created at runtime)

| Path | Description |
|------|-------------|
| `~/linkedout-data/state/update-check.json` | Cached update check result |
| `~/linkedout-data/state/update-snooze.json` | Snooze state |
| `~/linkedout-data/state/.last-upgrade-version` | Last successfully upgraded version |
| `~/linkedout-data/reports/upgrade-*.json` | Upgrade reports |
| `~/linkedout-data/extension/*.zip` | Downloaded extension zips |

---

## Testing Strategy

### Unit tests

| Test | What it verifies |
|------|-----------------|
| `test_version.py` | `VERSION` file parsing, `get_version_info()` returns correct structure |
| `test_update_checker.py` | GitHub API response parsing, cache read/write, throttle logic (mocked HTTP) |
| `test_snooze.py` | Escalating backoff (24h -> 48h -> 1w), reset on new version, state persistence |
| `test_changelog_parser.py` | Correct extraction of changelog sections between two versions, edge cases (missing versions, malformed markdown) |
| `test_version_migrator.py` | Script discovery, execution order (ascending version), skip-if-no-scripts |
| `test_extension_updater.py` | Checksum verification, download path construction, installed detection |
| `test_upgrader.py` | Step orchestration, failure at each step produces correct rollback message, report structure |

### Integration tests

| Test | What it verifies |
|------|-----------------|
| `test_upgrade_with_migration.py` | Migration-during-upgrade integration tests (review finding 2026-04-07: this is the highest-risk upgrade operation — expanded coverage): |
| | — Set up DB with current schema, add a new migration, run upgrader, verify new schema applied |
| | — Verify existing data preserved after migration (insert test rows before upgrade, assert they survive) |
| | — Migration failure mid-upgrade: simulate a bad migration (e.g., constraint violation), verify upgrader reports error clearly and DB is not left in partial state |
| | — Version migration scripts: place a test script in `migrations/version/`, verify it executes in order during upgrade |
| | — No-op upgrade: upgrade to same version, verify no migrations run, data untouched |
| `test_upgrade_report.py` | Report file written to correct path with correct structure |

### Installation tests (Phase 13 / nightly)

| Test | What it verifies |
|------|-----------------|
| Upgrade path test | Install v0.1.0, run setup, upgrade to v0.2.0 (git pull + `/linkedout-upgrade`), verify migrations run, data intact, readiness report clean |

**All unit tests must run without network access or real GitHub API calls** — mock HTTP responses. Integration tests may use a real local PostgreSQL but no external services.

**Test file locations:**
- `backend/tests/unit/upgrade/test_version.py`
- `backend/tests/unit/upgrade/test_update_checker.py`
- `backend/tests/unit/upgrade/test_snooze.py`
- `backend/tests/unit/upgrade/test_changelog_parser.py`
- `backend/tests/unit/upgrade/test_version_migrator.py`
- `backend/tests/unit/upgrade/test_extension_updater.py`
- `backend/tests/unit/upgrade/test_upgrader.py`
- `backend/tests/integration/upgrade/test_upgrade_with_migration.py`
- `backend/tests/integration/upgrade/test_upgrade_report.py`

---

## Exit Criteria Verification Checklist

- [ ] `VERSION` file exists at repo root with valid semver
- [ ] `linkedout version` prints version, Python version, PostgreSQL version, config path, data dir, and ASCII logo
- [ ] `linkedout version --json` returns structured JSON
- [ ] On skill invocation when outdated: one-line notification printed, non-blocking
- [ ] On skill invocation when up-to-date: no notification
- [ ] On skill invocation when network unavailable: no notification, no error
- [ ] Snooze escalation works: 24h -> 48h -> 1 week
- [ ] Snooze resets when new version detected
- [ ] `auto_upgrade: true` in config triggers silent upgrade on skill invocation
- [ ] `/linkedout-upgrade` detects git clone install type
- [ ] `/linkedout-upgrade` pulls latest code via git
- [ ] `/linkedout-upgrade` runs Alembic migrations
- [ ] `/linkedout-upgrade` runs version migration scripts (if any)
- [ ] `/linkedout-upgrade` shows "What's New" from CHANGELOG.md
- [ ] `/linkedout-upgrade` downloads latest extension zip (if extension installed)
- [ ] `/linkedout-upgrade` shows re-sideload instructions for extension
- [ ] Upgrade report written to `~/linkedout-data/reports/upgrade-*.json`
- [ ] Upgrade metrics event recorded
- [ ] On upgrade failure: rollback instructions shown with exact commands
- [ ] On upgrade failure: system remains in working pre-upgrade state
- [ ] Re-running `/linkedout-upgrade` when already current: "Already up to date" message
- [ ] All unit tests pass with mocked externals
- [ ] Integration tests pass against real local DB

---

## Estimated Complexity Summary

| Task | Complexity | Notes |
|------|-----------|-------|
| 10A. UX Design Doc | M | Requires careful wording of all user-facing strings |
| 10B. VERSION File & Utilities | S | Small utility module |
| 10C. Update Check Mechanism | M | GitHub API integration, caching logic |
| 10D. `/linkedout-upgrade` Implementation | L | Core upgrade flow with multiple steps and failure handling |
| 10E. Snooze Support | M | State management, escalating backoff |
| 10F. Extension Upgrade | M | Download, checksum, instruction generation |
| 10G. Upgrade Logging | M | Integrated into upgrader, report structure |

**Total estimated effort:** 1 L + 5 M + 1 S

**Suggested implementation order:**
1. 10A (Design Gate — must be first, blocks all other tasks)
2. 10B (VERSION file — foundational, no dependencies)
3. 10C (Update check — depends on 10B for version reading)
4. 10G (Logging/reporting — set up early so all other tasks use it)
5. 10D (Core upgrade — depends on 10B, 10C, 10G)
6. 10E (Snooze — depends on 10C)
7. 10F (Extension upgrade — depends on 10D)

---

## Open Questions

1. **Vendored copy upgrade path:** The plan mentions "vendored copy" as an install type (users who downloaded a release tarball instead of git cloning). How realistic is this for v1? If we only support git clone initially, the vendored path can be deferred. **Recommendation:** Support only git clone in v1, document vendored as future.

2. **Version migration script format:** Should version migration scripts be Python (`.py` with a `migrate()` function) or shell (`.sh`)? Python gives access to the DB and config; shell is simpler for file-system-only changes. **Recommendation:** Python with a `migrate(config: LinkedOutSettings)` signature — most version migrations will involve config or DB changes.

3. **GitHub API authentication:** The update check calls the GitHub Releases API. Unauthenticated requests have a 60/hour rate limit (per IP). This is fine for a single user checking once per hour, but could fail in CI or shared environments. **Recommendation:** Accept unauthenticated for v1, document `GITHUB_TOKEN` env var as optional for higher limits.

4. **Extension version coupling:** Should the extension version always match the backend version? Or can they diverge? **Recommendation:** Same version for v1 (released together as GitHub Release assets). Allows divergence later if needed.

5. **Rollback mechanism:** The current plan shows rollback instructions (manual git commands). Should we provide an automated `linkedout rollback` command? **Recommendation:** Manual rollback instructions in v1 — automated rollback is complex (migration rollback, dep rollback) and premature for a pre-1.0 project with few users.

6. **Dirty working tree handling:** If the user has local modifications in their git clone, `git pull` may fail. Options: (a) refuse to upgrade with message, (b) stash changes + pull + unstash, (c) force pull (destructive). **Recommendation:** Option (a) — refuse with clear message: "You have uncommitted changes. Commit or stash them first, then re-run /linkedout-upgrade."
