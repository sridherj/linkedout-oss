# Sub-Phase 01: UX Design Doc (Design Gate)

**Source task:** 10A
**Complexity:** M
**Dependencies:** None — this sub-phase MUST run first
**Gate:** SJ approval required before any implementation sub-phase begins

## Objective

Produce `docs/design/upgrade-flow-ux.md` — a complete user-facing flow specification for the upgrade experience. Every user-visible string must be written out verbatim. Every error scenario must have an actionable recovery message.

## Context

Read `_shared_context.md` for project-level context and Phase 0 decisions. Key constraints:
- CLI uses flat `linkedout` namespace
- All state/config under `~/linkedout-data/`
- `migrate` is internal-only (not shown in `--help`)
- Loguru with human-readable logs
- Operation result pattern: Progress → Summary → Gaps → Next steps → Report path

## Deliverable

Create: `docs/design/upgrade-flow-ux.md`

## Contents to Specify

The UX design doc must cover these sections with **exact user-visible text**:

### 1. Update Notification
- One-line, non-blocking notification shown during skill invocation
- Format: `LinkedOut vX.Y.Z available (you have vA.B.C). Run /linkedout-upgrade`
- When up-to-date or check fails: show nothing

### 2. Snooze Confirmation
- Options presented to user: "Remind me in 24h / 48h / 1 week / Don't remind again"
- Text shown after snoozing

### 3. `/linkedout-upgrade` Step-by-Step Output
Walk through every step the user sees:
1. Detecting install type (git clone vs vendored)
2. Pulling latest code
3. Updating Python dependencies
4. Running database migrations
5. Running version migration scripts (if any)
6. Updating extension (if installed)
7. Post-upgrade health check
8. Showing "What's New" (parsed from CHANGELOG.md)
9. Writing upgrade report

### 4. "What's New" Display Format
- How changelog entries between old and new version are rendered
- Example with realistic entries

### 5. Error Messages
Write exact error messages for each failure mode:
- Git pull fails: dirty working tree
- Git pull fails: merge conflict
- Git pull fails: network error
- Migration fails: schema conflict
- Migration fails: DB connection error
- Extension download fails: network error
- Extension download fails: GitHub API error

### 6. Rollback Instructions
- Exact commands shown on failure (git checkout, migrate commands)
- What the user should expect after rollback

### 7. Auto-Upgrade Flow
- Silent mode: `auto_upgrade: true` in config
- No terminal output, logs to `~/linkedout-data/logs/cli.log`
- Fallback to notification mode on failure

### 8. Edge Cases
- Already up-to-date: "Already running the latest version (vX.Y.Z)"
- Re-running after failed upgrade
- First run (no previous version recorded)

## Acceptance Criteria

- [ ] Every user-visible string is written out verbatim
- [ ] Every error scenario has an actionable recovery message
- [ ] Rollback instructions include exact commands
- [ ] Auto-upgrade behavior is fully specified
- [ ] Edge cases are covered
- [ ] Document follows the project's UX design doc conventions

## Verification

1. Review the doc for completeness against the 8 sections above
2. Ensure no placeholder text remains — all strings must be final
3. Confirm rollback commands are syntactically correct
4. Flag the doc for SJ approval (this is a Design Gate)

## Important Notes

- This is a **design document only** — do NOT write any code
- Do NOT proceed to implementation sub-phases until SJ approves this document
- Reference `docs/decision/cli-surface.md` for command naming conventions
- Reference `docs/decision/env-config-design.md` for file paths and config structure
