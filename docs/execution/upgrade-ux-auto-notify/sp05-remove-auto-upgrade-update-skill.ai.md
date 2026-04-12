# Sub-phase 05: Remove Auto-Upgrade Code + Update Skill & Specs

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP05 |
| Dependencies | SP01, SP02, SP03, SP04 (all notification layers wired before removing old code) |
| Estimated effort | 1 session (~2 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-12-upgrade-ux-auto-notify-holistic.collab.md` — Sub-phase 5 |
| Shared context | `_shared_context.md` |

## Objective

1. Remove the dead `try_auto_upgrade()` function and `auto_upgrade` config field
2. Rewrite the `/linkedout-upgrade` skill template to use the CLI command
3. Update specs and UX design doc to reflect all changes from SP01-SP04

## Context

`try_auto_upgrade()` in `update_checker.py` (lines 234-285) is dead code — nothing calls it. The `auto_upgrade` config field in `settings.py` (line 228) has no consumer after its removal. The `/linkedout-upgrade` skill template still has manual git/pip steps that should be replaced by `linkedout upgrade --verbose`. All spec updates from SP01-SP04 are bundled here.

## Tasks

### 1. Verify no callers before deletion

**Critical safety check:** Before deleting anything, grep the entire codebase:

```bash
# Must return zero results (excluding the definition itself and tests)
grep -rn 'try_auto_upgrade' backend/src/
grep -rn 'auto_upgrade' backend/src/ --include='*.py'
grep -rn 'auto_upgrade' backend/src/ --include='*.yaml'
```

Expected results:
- `try_auto_upgrade`: only `update_checker.py` (the definition)
- `auto_upgrade`: only `settings.py` (the field definition)

If any unexpected callers exist, **stop and report** — do not delete.

### 2. Delete `try_auto_upgrade()` from update_checker.py

**File:** `backend/src/linkedout/upgrade/update_checker.py`

Remove:
- The `# ── Auto-upgrade ───` section comment (line 229)
- The `LOG_FILE` constant (line 231)
- The entire `try_auto_upgrade()` function (lines 234-285)
- The `import subprocess` — verify it's only used by `try_auto_upgrade()` before removing
- The `from linkedout.version import _repo_root` import inside the function (it's a lazy import, so it's only in the function body)

After deletion, the file should end after `_is_outdated()` (or after `get_snooze_duration()` if SP03 added it).

### 3. Remove `auto_upgrade` field from settings.py

**File:** `backend/src/shared/config/settings.py` (line 228)

Delete the field:

```python
auto_upgrade: bool = Field(default=False)
```

Also check for and remove:
- Any comment block above the field explaining it
- Any reference in `config.yaml.example` or template files
- Any reference in diagnostics or config show/dump commands

```bash
grep -rn 'auto_upgrade' backend/ docs/ skills/ --include='*.py' --include='*.yaml' --include='*.md' --include='*.tmpl'
```

### 4. Rewrite `/linkedout-upgrade` skill template

**File:** `skills/linkedout-upgrade/SKILL.md.tmpl`

Replace the entire content after the frontmatter with:

```markdown
---
name: linkedout-upgrade
description: Upgrade LinkedOut to the latest version — pull code, run migrations, and verify system health
tools:
  - Bash
  - Read
---

# /linkedout-upgrade — Upgrade LinkedOut

Upgrade LinkedOut to the latest version using the CLI upgrade command.

## Preamble

1. **Load credentials and activate the virtual environment:**

```bash
cd $(git rev-parse --show-toplevel) && source backend/.venv/bin/activate && source {{AGENT_CONTEXT_PATH}}
```

If `agent-context.env` does not exist, tell the user:
> Run `/linkedout-setup` first to configure LinkedOut.

## Upgrade

2. **Run the upgrade:**

```bash
{{CLI_PREFIX}} upgrade --verbose
```

Show the full output to the user. The CLI handles:
- Pre-flight checks (git status, install type detection)
- Code pull, dependency updates, database migrations
- Post-upgrade health check
- What's New section from changelog

3. **Handle issues:**

If the upgrade reports errors or failures, suggest:

```bash
{{CLI_PREFIX}} diagnostics --repair
```

4. **Verify:**

```bash
{{CLI_PREFIX}} version
{{CLI_PREFIX}} status
```

Show the new version and system status to confirm the upgrade succeeded.
```

Key changes:
- Removed all manual git/pip steps — the CLI `upgrade` command handles everything
- Removed the "Phase 10 coming soon" note — this IS the implementation
- Kept the preamble pattern (load credentials, activate venv) consistent with other skills
- Added `--verbose` to show detailed output during upgrade
- Added diagnostics suggestion for error cases

### 5. Regenerate skill files

```bash
cd $(git rev-parse --show-toplevel) && bin/generate-skills
```

Verify all three hosts regenerated:

```bash
for host in claude-code codex copilot; do
  echo "=== $host ==="
  grep -c 'upgrade --verbose' skills/$host/linkedout-upgrade/SKILL.md
done
```

### 6. Update UX design doc

**File:** `docs/design/upgrade-flow-ux.human.md`

Make these changes:

- **Section 7 (Auto-Upgrade Flow):** Replace content with:
  > **DROPPED** — decided 2026-04-12. Auto-upgrade is too risky (silent git pull during queries). Users are notified via CLI banner and skill preamble instead. See Sub-phases 1 and 4 of the upgrade UX plan.

- **Section 1 (Update Notification):** Add note:
  > **Implemented:** CLI result_callback integration (SP01). After every CLI command, if an update is available and not snoozed, a single-line banner appears.

- **Section 2 (Snooze):** Add note:
  > **Implemented:** Explicit `--snooze` flag added to `linkedout upgrade` (SP03). Complements the existing automatic snooze escalation.

### 7. Update CLI commands spec

**File:** `docs/specs/cli_commands.collab.md`

Updates needed:

- **CLI Structure > Demo mode nudge section:** Rename to "Post-command hooks" or "Result callback hooks". Document both the demo nudge and the update notification banner. Update function name reference from `_append_demo_nudge` to `_post_command_hooks`.

- **`version` command section:** Add `--check` flag documentation:
  - `--check`: Run a fresh update check (ignores cache and snooze). Prints "Up to date" or "Update available" with exit code 0/1.
  - `--check --json`: Returns `{"update_available": bool, "current": str, "latest": str, "release_url": str}`.

- **`upgrade` command section:** Add `--snooze` flag documentation:
  - `--snooze`: Snooze the current update notification. Shows confirmation with duration (24h → 48h → 1 week escalation).

### 8. Update skills system spec

**File:** `docs/specs/skills_system.collab.md`

- **Skills Catalog > linkedout-upgrade entry:** Update description to reflect that the skill now delegates to `linkedout upgrade --verbose` instead of manual steps.
- **Skills Catalog > linkedout entry:** Note the version check step in the preamble.

### 9. Update tests

Remove or update any test that references `try_auto_upgrade` or `auto_upgrade`:

```bash
grep -rn 'try_auto_upgrade\|auto_upgrade' backend/tests/
```

- If tests exist for `try_auto_upgrade()`, delete them
- If tests reference the `auto_upgrade` config field, remove those assertions
- Run the full upgrade test suite to confirm:

```bash
pytest backend/tests/unit/upgrade/ -v
```

## Verification

```bash
# 1. Verify no references to removed code
grep -rn 'try_auto_upgrade' backend/src/
grep -rn 'auto_upgrade' backend/src/ --include='*.py'
# Both should return empty

# 2. Run upgrade tests
pytest backend/tests/unit/upgrade/ -v

# 3. Verify skill regeneration
bin/generate-skills
for host in claude-code codex copilot; do
  grep -c 'upgrade --verbose' skills/$host/linkedout-upgrade/SKILL.md
done

# 4. Import check (no broken imports after deletion)
cd backend && python -c "from linkedout.upgrade.update_checker import check_for_update; print('OK')"
cd backend && python -c "from shared.config.settings import LinkedOutSettings; print('OK')"
```

## What NOT to Do

- Do not delete `snooze_update()`, `is_snoozed()`, or `reset_snooze()` — those are active code
- Do not modify the `check_for_update()` signature — that was done in SP01/SP02
- Do not change the CLI banner format — that was done in SP01
- Do not remove the `_SNOOZE_DURATIONS` or snooze file constants — those are used by active snooze code
- Do not remove `LOG_FILE` if it's used elsewhere — grep first
