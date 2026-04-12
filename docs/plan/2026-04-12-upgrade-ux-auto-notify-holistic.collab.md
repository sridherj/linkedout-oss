# Upgrade UX: Auto-Notify and Holistic Upgrade Experience

## Overview

The upgrade infrastructure (update checker, snooze, upgrader, changelog parser, extension updater) is fully built and tested. What's missing is the **wiring** -- nothing calls `check_for_update()` except the upgrade command itself, the `/linkedout-upgrade` skill still has manual steps instead of using the CLI, and there's no `--check` flag on `linkedout version`. This plan wires the existing machinery into every user touchpoint (CLI result_callback, skill preamble, version command), removes dead auto-upgrade code, adds the `--snooze` flag, and updates the UX design doc and skill templates to reflect reality.

## Operating Mode

**HOLD SCOPE** -- The task description uses precise language ("wire", "add", "update", "drop") with a fixed list of agreed decisions. No signal words for expansion or reduction. Every deliverable was explicitly confirmed with SJ. Commit fully to the stated scope.

## Sub-phase 1: CLI Notification Layer

**Outcome:** After every `linkedout` CLI command, if an update is available (and not snoozed, and cache says so), a single-line banner appears: `LinkedOut v{latest} available (you have v{current}). Run: linkedout upgrade`. Demo nudge continues to work. Network errors are invisible.

**Dependencies:** None

**Estimated effort:** 1 session (~2 hours)

**Verification:**
- Run any CLI command (e.g., `linkedout version`) with a stale cache or simulated outdated version -- banner appears after output
- Run with up-to-date version -- no banner
- Run with snoozed version -- no banner
- Run with no network -- no banner, no error, no delay
- Demo mode still shows its nudge line
- Run `linkedout upgrade` -- no double banner (upgrade command already handles its own notification)

Key activities:

- **Rename `_append_demo_nudge` → `_post_command_hooks`** in `backend/src/linkedout/cli.py`: The function now handles multiple post-command checks (demo nudge + update banner), so the name should reflect that. Add a call to `check_for_update(timeout=3)` from `linkedout.upgrade.update_checker`. If it returns an `UpdateInfo` with `is_outdated=True`, print the banner line. Import lazily inside the function to keep CLI startup fast. Wrap in `try/except Exception: pass` for zero-failure guarantee. The 3s timeout (vs 10s default) ensures the passive banner never stalls the CLI for users who didn't ask for an update check.

- **Banner format**: `"\nLinkedOut v{latest} available (you have v{current}). Run: linkedout upgrade"`. Single line, no decoration, stdout, after a blank line separator. Matches the UX design doc Section 1 format but uses `linkedout upgrade` (CLI command) rather than `/linkedout-upgrade` (skill) since this is a CLI context.

- **Ordering**: Demo nudge prints first, then update banner. Both are conditional and independent.

- **Suppress during upgrade**: Skip the banner when the invoked command is `upgrade` (check `ctx.invoked_subcommand` or inspect the command name from `ctx.info_name`). The upgrade command already runs its own update check and showing a "you're outdated" banner right before an upgrade would be redundant.

- **Write unit test**: `backend/tests/unit/upgrade/test_cli_update_banner.py` -- mock `check_for_update()` to return outdated/up-to-date/None/exception, invoke CLI via Click's `CliRunner`, assert banner appears/doesn't appear. Test demo mode + update banner coexistence. (Placed in `upgrade/` directory to group with other upgrade notification tests.)

**Design review:**
- Spec consistency: `cli_commands.collab.md` > Demo mode nudge documents the result_callback; adding update notification extends it. The spec says "appends... after every command" -- our addition follows the same pattern. Update the spec (Section: CLI Structure > Demo mode nudge) to mention the update banner. Also update the function name from `_append_demo_nudge` to `_post_command_hooks`.
- Error paths: `check_for_update()` already swallows all exceptions and returns `None`. The result_callback also wraps in try/except. Double safety net -- no failure mode can break the user's command output.
- Performance: `check_for_update()` reads a JSON cache file (fast) or makes one HTTP call (max 3s timeout for banner path, cached for 1hr). The 3s worst-case on a cold cache is acceptable since it happens once per hour and the CLI command's output is already printed. The shorter timeout (vs 10s default) ensures the passive banner fails fast on slow/unreachable networks.

## Sub-phase 2: Version Command `--check` Flag

**Outcome:** `linkedout version --check` runs a fresh update check (ignoring cache age) and prints either "Up to date (v{current})" or "Update available: v{current} -> v{latest}. Run: linkedout upgrade" with exit code 0/1 respectively. `linkedout version --check --json` returns structured JSON.

**Dependencies:** None (can run in parallel with Sub-phase 1)

**Estimated effort:** 1 session (~1.5 hours)

**Verification:**
- `linkedout version --check` with outdated version prints notification, exits 1
- `linkedout version --check` with current version prints "up to date", exits 0
- `linkedout version --check --json` returns `{"update_available": true/false, "current": "...", "latest": "...", "release_url": "..."}`
- `linkedout version --check` with no network prints error message, exits 1
- `linkedout version` (without `--check`) is unchanged

Key activities:

- **Modify `backend/src/linkedout/commands/version.py`**: Add `--check` flag (`click.option`). When set, call `check_for_update(force=True, skip_snooze=True)` to bypass both cache and snooze (user explicitly asked for the truth). Format output based on `--json` flag.

- **Add `check_for_update(force=False, skip_snooze=False, timeout=10)` parameters** to `backend/src/linkedout/upgrade/update_checker.py`: When `force=True`, skip the cache freshness check and always hit the GitHub API. When `skip_snooze=True`, return the `UpdateInfo` even if the version is snoozed (used by `--check` so the user gets a truthful answer). The `timeout` parameter is passed to the HTTP client (banner path uses 3s, `--check` uses 10s). The cache is still written on success for future non-forced checks.

- **Exit codes**: `sys.exit(0)` if up-to-date, `sys.exit(1)` if outdated or check failed. This makes `linkedout version --check` usable in scripts.

- **Write unit test**: `backend/tests/unit/upgrade/test_version_check_flag.py` -- test `--check` flag with mocked update checker, verify output format and exit codes. Include a test for `--check` with snoozed state: mock a snoozed version, run `--check`, assert it still reports "Update available" (verifies `skip_snooze=True` works end-to-end through the CLI).

**Design review:**
- Spec consistency: `cli_commands.collab.md` > version command currently documents `--json` only. Add `--check` to the spec.
- Naming: `--check` is concise and unambiguous in the context of the `version` command. Alternative `--update-check` is redundant.
- Architecture: Reuses existing `check_for_update()` with new `force`, `skip_snooze`, and `timeout` parameters -- no new HTTP client code. `--check` bypasses both cache and snooze to give a truthful answer.

## Sub-phase 3: Snooze CLI Flag

**Outcome:** `linkedout upgrade --snooze` explicitly snoozes the current update notification. The user sees a confirmation message with the snooze duration. The existing automatic snooze (implicit escalation) continues to work.

**Dependencies:** None (can run in parallel with Sub-phases 1-2)

**Estimated effort:** 0.5 session (~1 hour)

**Verification:**
- `linkedout upgrade --snooze` when update available prints "Snoozed v{latest} for 24 hours" (or appropriate duration)
- `linkedout upgrade --snooze` when already snoozed increments the snooze count and shows longer duration
- `linkedout upgrade --snooze` when up to date prints "Already running the latest version"
- After snooze, CLI banner (Sub-phase 1) is suppressed until snooze expires
- Snooze state file is written correctly

Key activities:

- **Modify `backend/src/linkedout/commands/upgrade.py`**: Add `--snooze` flag. When set, run `check_for_update()` to get the latest version. If outdated, call `snooze_update(version)` and print confirmation with the snooze duration. If not outdated, print "Already running the latest version." Exit without running the upgrade flow.

- **Add `get_snooze_duration(version) -> timedelta | None`** to `update_checker.py`: Returns how long the next snooze would last (for display purposes). Reads current snooze count, computes next duration from `_SNOOZE_DURATIONS`. Returns `None` if no update available.

- **Confirmation format**: `"Update v{latest} snoozed for {duration}. Run 'linkedout upgrade' when ready."` where duration is "24 hours", "48 hours", or "1 week".

- **Write unit test**: Add test cases in `backend/tests/unit/upgrade/test_update_checker.py` for `get_snooze_duration()`. Add CLI test for `--snooze` flag.

- **Mutual exclusion**: `--snooze` and `--verbose` can coexist (snooze ignores verbose). `--snooze` skips the entire upgrade flow.

**Design review:**
- Spec consistency: `cli_commands.collab.md` > upgrade command documents `--verbose` only. Add `--snooze` to the spec.
- Naming: `--snooze` is clear and matches the existing `snooze_update()` function name.
- Error paths: If the GitHub API is unreachable, `check_for_update()` returns `None`. The `--snooze` handler prints "Could not check for updates. Try again later." instead of silently doing nothing.

## Sub-phase 4: Skill Preamble Version Check

**Outcome:** The `/linkedout` skill preamble includes a version check step. When an update is available, the skill shows the notification banner after the health check, before answering the query. The notification matches the CLI banner format for consistency.

**Dependencies:** None (can run in parallel with Sub-phases 1-3, but coordinate on notification format)

**Estimated effort:** 1 session (~1.5 hours)

**Verification:**
- Invoke `/linkedout` with outdated version -- notification appears after system health check
- Invoke `/linkedout` with current version -- no notification
- Invoke `/linkedout` with no network -- no notification, skill proceeds normally
- Notification text matches CLI banner format
- All three host-specific skill files are regenerated (claude-code, codex, copilot)

Key activities:

- **Modify `skills/linkedout/SKILL.md.tmpl`**: Add a version check step to the Preamble section, after step 2 (Check system health). The step runs `{{CLI_PREFIX}} version --check --json 2>/dev/null` and if `update_available` is true, shows: `"LinkedOut v{latest} available (you have v{current}). Run /linkedout-upgrade to update."` Note the skill context uses `/linkedout-upgrade` (skill invocation), not `linkedout upgrade` (CLI command). The check is silent on failure (redirect stderr to /dev/null).

- **Regenerate skill files**: Run `bin/generate-skills` to compile the template change into all host-specific output directories (claude-code, codex, copilot).

- **Decide: inline bash or reference --check**: Using `linkedout version --check --json` requires Sub-phase 2 to be complete first. Alternative: use `linkedout version --json` (already exists) and add a version comparison step inline in the skill template. **Decision**: Depend on Sub-phase 2 (`--check` flag) -- it's cleaner and the skill doesn't need to know version comparison logic. Mark this dependency explicitly.

**Design review:**
- Spec consistency: `skills_system.collab.md` > B1 (Template Engine) documents how templates are rendered. Our change follows the existing pattern. Update the Skills Catalog section to note the version check behavior.
- Skill flow: The version check MUST be after `status --json` (health check) and MUST NOT block the query. If the check fails, the skill continues without showing anything. Add explicit instruction: "If the version check command fails or returns an error, skip silently and proceed to the query."
- Naming consistency: CLI context says "Run: linkedout upgrade", skill context says "Run /linkedout-upgrade". Both are correct for their contexts.

## Sub-phase 5: Remove Auto-Upgrade Code + Update `/linkedout-upgrade` Skill

**Outcome:** The `try_auto_upgrade()` function and its supporting code are removed from `update_checker.py`. The `/linkedout-upgrade` skill template is rewritten to use `linkedout upgrade` CLI command instead of manual git/pip steps. The UX design doc Section 7 (Auto-Upgrade Flow) is marked as dropped.

**Dependencies:** Sub-phases 1-4 (all notification layers wired before removing old code)

**Estimated effort:** 1 session (~2 hours)

**Verification:**
- `try_auto_upgrade` function no longer exists in codebase
- No references to `auto_upgrade` in config schema or code
- `/linkedout-upgrade` skill invokes `linkedout upgrade` and shows its output
- Existing upgrade unit tests still pass (any test referencing auto-upgrade is removed or updated)
- Skill regeneration succeeds for all hosts
- UX design doc is updated

Key activities:

- **Delete `try_auto_upgrade()` from `backend/src/linkedout/upgrade/update_checker.py`**: Remove the function, its imports (`subprocess`, `_repo_root`), and the `LOG_FILE` constant. These are dead code that was never wired into any call path.

- **Remove `auto_upgrade` field from `backend/src/shared/config/settings.py`**: Delete the `auto_upgrade: bool = Field(default=False)` field and its comment block (lines 226-228). This config field has no consumer after `try_auto_upgrade()` is removed. Also grep for any references in `config.yaml.example`, diagnostics, or config show commands and remove those too.

- **Rewrite `skills/linkedout-upgrade/SKILL.md.tmpl`**: Replace the manual step-by-step instructions (git status, git pull, uv pip install, etc.) with a single command delegation:
  1. Preamble: load credentials, activate venv (same as other skills)
  2. Run: `{{CLI_PREFIX}} upgrade --verbose`
  3. Show the output to the user
  4. If the upgrade reports issues, suggest `{{CLI_PREFIX}} diagnostics --repair`
  5. Remove the "Phase 10 coming soon" note -- this IS Phase 10
  
  The skill becomes a thin wrapper around the CLI command, which is exactly how skills should work.

- **Regenerate skill files**: Run `bin/generate-skills`.

- **Update `docs/design/upgrade-flow-ux.human.md`**:
  - Section 7 (Auto-Upgrade Flow): Replace content with `**DROPPED** -- decided 2026-04-12. Auto-upgrade is too risky (silent git pull during queries). Users are notified via CLI banner and skill preamble instead.`
  - Section 1 (Update Notification): Add note about CLI result_callback integration
  - Section 2 (Snooze): Add note about explicit `--snooze` flag

- **Update CLI commands spec**: Add `--check` to version command, add `--snooze` to upgrade command, add update banner to result_callback behavior.

- **Update tests**: Remove or skip any test that references `try_auto_upgrade`. Verify remaining upgrade tests pass. Run `pytest backend/tests/unit/upgrade/` to confirm.

**Design review:**
- Spec consistency: Multiple specs need updates (cli_commands, skills_system). Bundle all spec updates into this sub-phase since they reflect changes from Sub-phases 1-4.
- Security: Removing auto-upgrade eliminates the risk of silent `git pull` + `uv pip install` running without user awareness. This is a security improvement.
- Architecture: The `/linkedout-upgrade` skill becomes a true thin wrapper (preamble + one CLI command), matching the pattern of other skills that delegate to CLI commands.
- Error paths: The rewritten skill template must handle the case where `linkedout upgrade` is not found on PATH (e.g., venv not activated). The existing preamble activation step covers this.

## Sub-phase 6: Integration Testing and Polish

**Outcome:** End-to-end verification that all notification touchpoints work together. The notification is consistent across CLI commands, `linkedout version --check`, and skill preamble. Snooze works across all touchpoints. The upgrade experience feels cohesive.

**Dependencies:** Sub-phases 1-5

**Estimated effort:** 1 session (~1.5 hours)

**Verification:**
- Full flow test: outdated version -> see banner on `linkedout status` -> snooze with `linkedout upgrade --snooze` -> banner disappears -> snooze expires -> banner reappears
- Full flow test: outdated version -> run `linkedout upgrade` -> upgrade succeeds -> banner disappears
- `linkedout version --check` works independently of CLI banner
- Skill preamble version check works independently
- All existing upgrade unit tests pass
- New integration tests pass

Key activities:

- **Write integration test**: `backend/tests/unit/upgrade/test_upgrade_notification_flow.py` -- End-to-end test using Click's `CliRunner` with mocked HTTP and file system. Test the full notification lifecycle: first command shows banner, snooze suppresses, snooze expiry re-shows, upgrade clears.

- **Verify notification consistency**: All three touchpoints (CLI banner, version --check, skill preamble) use the same `check_for_update()` function and share the same cache/snooze state. No divergence possible by design -- verify with a test that exercises all three paths against the same state files.

- **Run full test suite**: `pytest backend/tests/unit/upgrade/ -v` to confirm nothing is broken.

- **Manual smoke test**: If feasible, create a test scenario with a mock GitHub release endpoint to verify the full flow end-to-end.

**Design review:**
- No additional flags. This sub-phase is pure verification.

## Build Order

```
Sub-phase 1 (CLI Banner) ──────────┐
Sub-phase 2 (--check flag) ────────┤
Sub-phase 3 (--snooze flag) ───────┼──► Sub-phase 5 (Remove auto-upgrade, ──► Sub-phase 6 (Integration
                                   │    update skill & specs)                  testing & polish)
Sub-phase 4 (Skill preamble) ──────┘
     ^
     |
     depends on Sub-phase 2 for --check --json
```

**Critical path:** Sub-phase 2 -> Sub-phase 4 -> Sub-phase 5 -> Sub-phase 6

**Parallelism:** Sub-phases 1, 2, 3 can all run in parallel. Sub-phase 4 depends on Sub-phase 2 (needs `--check` flag). Sub-phase 5 waits for all four to complete. Sub-phase 6 is the final verification pass.

## Design Review Flags

| Sub-phase | Flag | Action |
|-----------|------|--------|
| Sub-phase 1 | Spec update needed: `cli_commands.collab.md` > CLI Structure > Demo mode nudge | Bundle into Sub-phase 5 spec updates |
| Sub-phase 2 | Spec update needed: `cli_commands.collab.md` > version command | Bundle into Sub-phase 5 spec updates |
| Sub-phase 3 | Spec update needed: `cli_commands.collab.md` > upgrade command | Bundle into Sub-phase 5 spec updates |
| Sub-phase 4 | Template change triggers skill regeneration for all 3 hosts | Run `bin/generate-skills` in Sub-phase 4 and Sub-phase 5 |
| Sub-phase 5 | `try_auto_upgrade()` removal -- verify no callers exist before deleting | Grep for `try_auto_upgrade` and `auto_upgrade` across entire codebase |
| Sub-phase 5 | `auto_upgrade` field in `settings.py` must be removed alongside `try_auto_upgrade()` | Also check `config.yaml.example`, diagnostics, config show |

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `check_for_update()` adds latency to every CLI command | Low | Already cached (1hr TTL). Cold-cache HTTP uses 3s timeout for passive banner (fails fast). `--check` uses 10s (user explicitly asked). Acceptable for once-per-hour occurrence. |
| GitHub API rate limit hit (60/hr unauthenticated) | Low | One check per hour per user. Single-user tool. Already handles rate limit gracefully (returns None). `GITHUB_TOKEN` env var supported for higher limits. |
| Skill preamble version check adds an extra bash command to every `/linkedout` invocation | Low | The `--check --json` call reuses the same 1hr cache. In-cache path is a fast file read + JSON parse. No network call most of the time. |
| Removing `try_auto_upgrade()` breaks something | Low | Function is dead code (nothing calls it). Grep will confirm before deletion. Tests will catch any unexpected reference. |

## Open Questions

- **Notification format in skill context**: Should the skill say "Run /linkedout-upgrade" or "Run `linkedout upgrade`"? The task description says `/linkedout-upgrade` in skill context, `linkedout upgrade` in CLI context. This matches what was agreed but is worth confirming since the skill could say either. **Current plan**: `/linkedout-upgrade` in skill context, `linkedout upgrade` in CLI context.

- **Cache TTL for `--check` flag**: The `--check` flag bypasses cache (`force=True`) and snooze (`skip_snooze=True`) to give a fresh, truthful answer. It writes to cache on success so the next CLI command's passive banner doesn't need another API call. **Resolved 2026-04-12.**

## Spec References

| Spec | Sections Referenced | Conflicts Found |
|------|---------------------|-----------------|
| `cli_commands.collab.md` | CLI Structure > Demo mode nudge, version command, upgrade command | 3 -- Sub-phases 1/2/3 add new behaviors; bundle spec update into Sub-phase 5 |
| `skills_system.collab.md` | Skills Catalog > linkedout-upgrade | 1 -- Sub-phase 5 rewrites the skill; update catalog description in Sub-phase 5 |

## Files Modified (Summary)

### Modified files

| File | Sub-phase | Change |
|------|-----------|--------|
| `backend/src/linkedout/cli.py` | 1 | Rename `_append_demo_nudge` → `_post_command_hooks`, add update notification with 3s timeout |
| `backend/src/linkedout/commands/version.py` | 2 | Add `--check` flag |
| `backend/src/linkedout/upgrade/update_checker.py` | 2, 3, 5 | Add `force`, `skip_snooze`, `timeout` params, add `get_snooze_duration()`, remove `try_auto_upgrade()` |
| `backend/src/shared/config/settings.py` | 5 | Remove `auto_upgrade` field (dead config after `try_auto_upgrade()` removal) |
| `backend/src/linkedout/commands/upgrade.py` | 3 | Add `--snooze` flag |
| `skills/linkedout/SKILL.md.tmpl` | 4 | Add version check to preamble |
| `skills/linkedout-upgrade/SKILL.md.tmpl` | 5 | Rewrite to use CLI command |
| `docs/design/upgrade-flow-ux.human.md` | 5 | Mark auto-upgrade as dropped, add CLI/skill notification notes |
| `docs/specs/cli_commands.collab.md` | 5 | Add --check, --snooze, update banner |
| `docs/specs/skills_system.collab.md` | 5 | Update linkedout-upgrade catalog entry |

### New files

| File | Sub-phase | Description |
|------|-----------|-------------|
| `backend/tests/unit/upgrade/test_cli_update_banner.py` | 1 | Unit tests for CLI update banner |
| `backend/tests/unit/upgrade/test_version_check_flag.py` | 2 | Unit tests for --check flag |
| `backend/tests/unit/upgrade/test_upgrade_notification_flow.py` | 6 | Integration test for full notification lifecycle |
