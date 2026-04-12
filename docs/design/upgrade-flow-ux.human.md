# Upgrade Flow UX Design

**Phase:** 10 (Upgrade & Version Management)
**Date:** 2026-04-07
**Status:** Pending SJ approval (Design Gate)
**Author:** Claude (taskos-subphase-runner agent)

---

## 1. Update Notification

> **Implemented:** CLI result_callback integration (SP01). After every CLI command, if an update is available and not snoozed, a single-line banner appears.

A non-blocking, single-line notification shown when a LinkedOut skill is invoked and a newer version is available. The notification appears after the skill's normal output, never before or during it.

### When shown

- A cached or fresh GitHub Releases check indicates the latest version is newer than the local `VERSION` file.
- The user has not snoozed this version (see Section 2).
- The check cache is stale (older than 1 hour) or missing — a fresh check runs silently in the background.

### When NOT shown

- The installed version matches or exceeds the latest release.
- The GitHub API check fails (network error, rate limit, malformed response).
- The user has snoozed this specific version and the snooze period has not expired.

### Notification text

```
LinkedOut v0.2.0 available (you have v0.1.0). Run /linkedout-upgrade
```

Format: `LinkedOut v{latest} available (you have v{current}). Run /linkedout-upgrade`

- Versions always include the `v` prefix in display text.
- The notification is a single line, no decoration, no color codes.
- It appears on stdout, after a blank line separator from the skill output.

---

## 2. Snooze Confirmation

> **Implemented:** Explicit `--snooze` flag added to `linkedout upgrade` (SP03). Complements the existing automatic snooze escalation.

When the user sees an update notification but does not run `/linkedout-upgrade`, the notification reappears on subsequent skill invocations with escalating backoff.

### Escalation schedule

| Snooze count | Reminder interval |
|---|---|
| 0 (first notification) | Shown immediately |
| 1 | Suppressed for 24 hours |
| 2 | Suppressed for 48 hours |
| 3+ | Suppressed for 1 week |

### Snooze behavior

- The snooze counter increments each time the notification is shown and the user does not upgrade.
- Snooze state is tracked per version in `~/linkedout-data/state/update-snooze.json`.
- When a new version is detected (different from the snoozed version), the snooze counter resets to 0 and the notification shows immediately.

### Snooze state file format

```json
{
  "snoozed_version": "0.2.0",
  "snooze_count": 2,
  "last_shown_at": "2026-04-07T14:30:00Z",
  "next_reminder_at": "2026-04-09T14:30:00Z"
}
```

### No interactive snooze prompt

There is no interactive "Remind me in 24h / 48h / 1 week" prompt. The escalation is automatic and silent. The user's only action is to either run `/linkedout-upgrade` or ignore the notification. This avoids interrupting the skill-driven workflow with interactive prompts.

---

## 3. `/linkedout-upgrade` Step-by-Step Output

When the user invokes `/linkedout-upgrade`, the skill runs `linkedout upgrade` under the hood. The following is the complete terminal output the user sees at each step.

### Step 1: Pre-flight check

```
Checking for updates...
```

If a dirty working tree is detected:

```
ERROR: Cannot upgrade — you have uncommitted changes in your LinkedOut directory.

  Commit or stash your changes first, then re-run /linkedout-upgrade.

  To see what's changed:
    cd /path/to/linkedout-oss && git status
```

The upgrade aborts. No further steps run.

If no update is available:

```
Already running the latest version (v0.1.0).
```

The upgrade exits cleanly.

### Step 2: Version detection

```
Upgrading LinkedOut from v0.1.0 to v0.2.0...
```

### Step 3: Pulling latest code

```
Pulling latest code...
  Done.
```

On verbose mode (`linkedout upgrade --verbose`), also shows:
```
Pulling latest code...
  git fetch origin
  git pull origin main
  Done.
```

### Step 4: Updating Python dependencies

```
Updating Python dependencies...
  Done.
```

On verbose mode, also shows:
```
Updating Python dependencies...
  uv pip install -e ".[dev]"
  Done.
```

### Step 5: Running database migrations

If migrations exist:

```
Running database migrations...
  Applying 2 migration(s)...
  Done.
```

If no pending migrations:

```
Running database migrations...
  No pending migrations.
```

### Step 6: Running version migration scripts

If scripts exist for this version range:

```
Running version migration scripts...
  Running v0.1.0 -> v0.2.0 migration...
  Done.
```

If no scripts exist:

```
Running version migration scripts...
  No migration scripts for v0.1.0 -> v0.2.0.
```

### Step 7: Updating extension

If the Chrome extension is installed:

```
Updating Chrome extension...
  Downloading linkedout-extension-v0.2.0.zip...
  Verifying checksum... OK
  Saved to ~/linkedout-data/extension/linkedout-extension-v0.2.0.zip

  To update the extension:
    1. Open chrome://extensions
    2. Remove the old LinkedOut extension
    3. Drag and drop the new zip file onto the page
       (or click "Load unpacked" after extracting)
```

If the extension is not installed:

This step is skipped silently (no output).

### Step 8: Post-upgrade health check

```
Running post-upgrade health check...
  LinkedOut v0.2.0 | DB connected | 4,012 profiles | embeddings: 98.2%
  Health check passed.
```

If the health check fails:

```
Running post-upgrade health check...
  WARNING: Health check found issues.
  Run `linkedout diagnostics --repair` to investigate.
```

### Step 9: What's New

```

What's New in v0.2.0
---------------------
- Added semantic search across all profile fields
- Fixed affinity computation for networks with 10,000+ connections
- Improved embedding generation speed by 3x with batched API calls
- Added `linkedout export` command for CSV/JSON network export
```

See Section 4 for the full display format specification.

### Step 10: Upgrade report

```
Upgrade complete: v0.1.0 -> v0.2.0 (15.2s)

Report saved: ~/linkedout-data/reports/upgrade-20260407-143000.json
```

### Complete successful output (all steps combined)

```
Checking for updates...
Upgrading LinkedOut from v0.1.0 to v0.2.0...

Pulling latest code...
  Done.

Updating Python dependencies...
  Done.

Running database migrations...
  Applying 2 migration(s)...
  Done.

Running version migration scripts...
  No migration scripts for v0.1.0 -> v0.2.0.

Updating Chrome extension...
  Downloading linkedout-extension-v0.2.0.zip...
  Verifying checksum... OK
  Saved to ~/linkedout-data/extension/linkedout-extension-v0.2.0.zip

  To update the extension:
    1. Open chrome://extensions
    2. Remove the old LinkedOut extension
    3. Drag and drop the new zip file onto the page
       (or click "Load unpacked" after extracting)

Running post-upgrade health check...
  LinkedOut v0.2.0 | DB connected | 4,012 profiles | embeddings: 98.2%
  Health check passed.

What's New in v0.2.0
---------------------
- Added semantic search across all profile fields
- Fixed affinity computation for networks with 10,000+ connections
- Improved embedding generation speed by 3x with batched API calls
- Added `linkedout export` command for CSV/JSON network export

Upgrade complete: v0.1.0 -> v0.2.0 (15.2s)

Report saved: ~/linkedout-data/reports/upgrade-20260407-143000.json
```

---

## 4. "What's New" Display Format

The "What's New" section is parsed from `CHANGELOG.md` at the repo root. The changelog follows the [Keep a Changelog](https://keepachangelog.com/) format with `## [X.Y.Z]` version headers.

### Parsing rules

1. Find the section header matching the new version: `## [0.2.0]`
2. Include all content from that header until the next `## [` header (the previous version).
3. If upgrading across multiple versions (e.g., v0.1.0 -> v0.3.0), include all sections between the old and new versions, newest first.
4. Strip the `## [X.Y.Z] - YYYY-MM-DD` header format down to just the version.
5. Strip Keep a Changelog category headers (`### Added`, `### Fixed`, etc.) and flatten into a single bullet list per version.

### Single-version upgrade display

```
What's New in v0.2.0
---------------------
- Added semantic search across all profile fields
- Fixed affinity computation for networks with 10,000+ connections
- Improved embedding generation speed by 3x with batched API calls
- Added `linkedout export` command for CSV/JSON network export
```

### Multi-version upgrade display

When the user skips versions (e.g., v0.1.0 -> v0.3.0):

```
What's New since v0.1.0
------------------------

v0.3.0:
- Added Chrome extension auto-discovery of mutual connections
- Fixed seed data import for companies with Unicode names

v0.2.0:
- Added semantic search across all profile fields
- Fixed affinity computation for networks with 10,000+ connections
- Improved embedding generation speed by 3x with batched API calls
- Added `linkedout export` command for CSV/JSON network export
```

### Edge cases

**CHANGELOG.md is missing or empty:**

```
What's New in v0.2.0
---------------------
  No changelog entries found. See https://github.com/{owner}/linkedout-oss/releases/tag/v0.2.0
```

**Version not found in CHANGELOG.md:**

```
What's New in v0.2.0
---------------------
  Changelog entry not found for this version. See https://github.com/{owner}/linkedout-oss/releases/tag/v0.2.0
```

**More than 30 lines of changelog content** (across all versions):

Show the first 25 lines, then:

```
  ... and 12 more changes. See full changelog:
  https://github.com/{owner}/linkedout-oss/blob/main/CHANGELOG.md
```

---

## 5. Error Messages

Every error message follows the pattern: `ERROR:` line, blank line, indented explanation, blank line, indented recovery action. All errors abort the upgrade at the point of failure. Steps that already succeeded are not rolled back automatically (see Section 6 for rollback instructions).

### 5.1 Git pull fails: dirty working tree

Shown during Step 1 (pre-flight check), before any changes are made.

```
ERROR: Cannot upgrade — you have uncommitted changes in your LinkedOut directory.

  Commit or stash your changes first, then re-run /linkedout-upgrade.

  To see what's changed:
    cd /path/to/linkedout-oss && git status
```

`/path/to/linkedout-oss` is replaced with the actual repo path.

### 5.2 Git pull fails: merge conflict

```
ERROR: Git pull failed — merge conflict detected.

  You have local changes that conflict with the upstream update.
  This typically happens if you've modified LinkedOut source files directly.

  To resolve:
    cd /path/to/linkedout-oss
    git status                    # see which files conflict
    git merge --abort             # abort the merge and restore pre-upgrade state
    git stash                     # stash your local changes
    linkedout upgrade             # re-run the upgrade
    git stash pop                 # re-apply your changes (may need manual merge)

  If you don't need your local changes:
    cd /path/to/linkedout-oss
    git merge --abort
    git checkout -- .
    linkedout upgrade
```

### 5.3 Git pull fails: network error

```
ERROR: Git pull failed — could not reach the remote repository.

  Check your internet connection and try again.

  If you're behind a proxy or firewall:
    cd /path/to/linkedout-oss
    git remote -v                 # verify the remote URL
    git fetch origin              # test connectivity

  Your LinkedOut installation is unchanged — no rollback needed.
```

### 5.4 Migration fails: schema conflict

```
ERROR: Database migration failed.

  Migration "abc123_add_search_index" could not be applied.
  This may indicate a schema conflict with manual database changes.

  Details:
    {alembic_error_message}

  To rollback to your previous version:
    cd /path/to/linkedout-oss
    git checkout v0.1.0
    linkedout migrate

  To investigate:
    linkedout diagnostics

  Report saved: ~/linkedout-data/reports/upgrade-20260407-143000.json
```

`{alembic_error_message}` is replaced with the actual Alembic error output, truncated to 5 lines if longer.

### 5.5 Migration fails: DB connection error

```
ERROR: Database migration failed — could not connect to PostgreSQL.

  Ensure PostgreSQL is running and the connection string is correct.

  To check:
    pg_isready -h localhost -p 5432
    linkedout config show          # verify database_url

  Your code has been updated but the database has not been migrated.
  To rollback the code update:
    cd /path/to/linkedout-oss
    git checkout v0.1.0

  To retry the migration after fixing the connection:
    linkedout migrate
```

### 5.6 Extension download fails: network error

```
WARNING: Could not download the updated Chrome extension.

  Network error while downloading linkedout-extension-v0.2.0.zip.

  The core upgrade succeeded — only the extension update was skipped.
  You can download it manually later:
    /linkedout-upgrade    (re-run to retry the extension download)

  Or download directly from:
    https://github.com/{owner}/linkedout-oss/releases/tag/v0.2.0
```

Note: Extension download failures are non-blocking warnings, not errors. The upgrade continues and completes successfully. The report records the extension step as `"status": "failed"`.

### 5.7 Extension download fails: GitHub API error

```
WARNING: Could not download the updated Chrome extension.

  GitHub API returned an error: {status_code} {error_message}

  This may be a temporary issue. The core upgrade succeeded.
  You can retry later:
    /linkedout-upgrade

  Or download directly from:
    https://github.com/{owner}/linkedout-oss/releases/tag/v0.2.0
```

### 5.8 Version migration script fails

```
ERROR: Version migration script failed.

  Script: migrations/version/v0_1_0_to_v0_2_0.py
  Error:  {script_error_message}

  The code and database have been updated, but the version migration
  script did not complete successfully.

  To investigate:
    cat migrations/version/v0_1_0_to_v0_2_0.py
    linkedout diagnostics

  To rollback to your previous version:
    cd /path/to/linkedout-oss
    git checkout v0.1.0
    linkedout migrate

  Report saved: ~/linkedout-data/reports/upgrade-20260407-143000.json
```

### 5.9 Dependency update fails

```
ERROR: Failed to update Python dependencies.

  uv pip install returned an error:
    {pip_error_message}

  The code has been updated but dependencies are out of sync.

  To retry:
    cd /path/to/linkedout-oss
    uv pip install -e ".[dev]"

  To rollback:
    cd /path/to/linkedout-oss
    git checkout v0.1.0
    uv pip install -e ".[dev]"

  Report saved: ~/linkedout-data/reports/upgrade-20260407-143000.json
```

---

## 6. Rollback Instructions

Rollback is manual in v1. When an upgrade fails partway through, the error message includes the exact commands needed to return to the previous working state.

### Rollback commands by failure point

| Failed at | Code changed? | DB changed? | Rollback commands |
|---|---|---|---|
| Pre-flight (dirty tree) | No | No | None needed |
| Git pull (network) | No | No | None needed |
| Git pull (merge conflict) | Partial | No | `git merge --abort` |
| Dependency update | Yes | No | `git checkout v{old}` then `uv pip install -e ".[dev]"` |
| Database migration | Yes | Partial | `git checkout v{old}` then `linkedout migrate` |
| Version migration script | Yes | Yes | `git checkout v{old}` then `linkedout migrate` |
| Extension download | Yes | Yes | None needed (core upgrade succeeded) |
| Post-upgrade health check | Yes | Yes | Investigate with `linkedout diagnostics` |

### Rollback output shown on failure

After any error that leaves the system in a partially upgraded state (dependency update, migration, or version script failure), the following block is appended to the error message:

```
To rollback to your previous version:
    cd /path/to/linkedout-oss
    git checkout v0.1.0
    uv pip install -e ".[dev]"
    linkedout migrate
```

### What the user should expect after rollback

```
After rollback:
  - Code is restored to v0.1.0 (the version you had before the upgrade)
  - Database schema matches v0.1.0
  - Python dependencies match v0.1.0
  - Any data created during the failed upgrade remains in the database
    (this is safe — the old code can read it)
  - The upgrade report at ~/linkedout-data/reports/upgrade-*.json
    contains details of what succeeded and what failed
```

This text is not shown during the upgrade itself — it is included in the UX doc for reference. The actual error messages (Section 5) contain the specific rollback commands for each failure mode.

---

## 7. Auto-Upgrade Flow

> **DROPPED** — decided 2026-04-12. Auto-upgrade is too risky (silent git pull during queries). Users are notified via CLI banner and skill preamble instead. See Sub-phases 1 and 4 of the upgrade UX plan.

---

## 8. Edge Cases

### 8.1 Already up-to-date

When the user runs `/linkedout-upgrade` and no update is available:

```
Checking for updates...
Already running the latest version (v0.1.0).
```

Exit cleanly, no report generated.

### 8.2 Re-running after a failed upgrade

When the user runs `/linkedout-upgrade` after a previous upgrade failed partway through:

The upgrade runs from the beginning. It does not attempt to resume from the failed step. The pre-flight check detects whether the working tree is clean and whether the current version matches the expected pre-upgrade version.

If the code was partially updated (git pull succeeded but migration failed), the pre-flight check detects the version mismatch:

```
Checking for updates...

NOTE: Your code is at v0.2.0 but your database schema is at v0.1.0.
  This may indicate a previous upgrade that failed during migration.
  Continuing upgrade from the current state...

Running database migrations...
  Applying 2 migration(s)...
  Done.

Running version migration scripts...
  No migration scripts for v0.1.0 -> v0.2.0.

Running post-upgrade health check...
  LinkedOut v0.2.0 | DB connected | 4,012 profiles | embeddings: 98.2%
  Health check passed.

What's New in v0.2.0
---------------------
- Added semantic search across all profile fields
- Fixed affinity computation for networks with 10,000+ connections

Upgrade complete: v0.1.0 -> v0.2.0 (8.1s)

Report saved: ~/linkedout-data/reports/upgrade-20260407-150000.json
```

### 8.3 First run (no previous version recorded)

When `/linkedout-upgrade` runs for the first time and `~/linkedout-data/state/.last-upgrade-version` does not exist:

The system reads the current version from the `VERSION` file and treats it as the "from" version. If the user is already on the latest version, it behaves like case 8.1.

If the user installed an older version and runs upgrade before ever recording a version:

```
Checking for updates...
Upgrading LinkedOut from v0.1.0 to v0.2.0...

NOTE: No previous upgrade recorded. Running full upgrade sequence.

Pulling latest code...
  ...
```

The full upgrade sequence runs. After completion, `~/linkedout-data/state/.last-upgrade-version` is written with the new version.

### 8.4 GitHub API unreachable during update check

The update check fails silently. No notification is shown. The skill proceeds normally. A debug-level log entry is written:

```
2026-04-07 14:23:05.123 | DEBUG    | cli.update_checker:check:42 | Update check failed: ConnectionError — github.com unreachable. Skipping notification.
```

### 8.5 GitHub API rate limited

Same behavior as 8.4. The check fails silently. The cached result (if any) is used if it is less than 1 hour old. Otherwise, no notification.

### 8.6 User runs `linkedout upgrade` directly (CLI, not skill)

The behavior is identical to the skill invocation. `linkedout upgrade` is the CLI command that `/linkedout-upgrade` invokes under the hood. Both produce the same output.

### 8.7 Upgrade while backend server is running

```
WARNING: The LinkedOut backend server is running on port 8001.

  The upgrade may require restarting the server.
  After the upgrade completes, restart it with:
    linkedout start-backend
```

The upgrade proceeds. The warning is informational only.

### 8.8 Downgrade attempt

If the user manually runs `git checkout v0.1.0` (to an older version) and then runs `/linkedout-upgrade`:

The update check detects that a newer version exists on GitHub. The upgrade runs normally, pulling the latest code.

There is no explicit "downgrade" path. Users who want to stay on an older version should not run `/linkedout-upgrade`.
