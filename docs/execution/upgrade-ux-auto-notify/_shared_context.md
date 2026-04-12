# Shared Context: Upgrade UX — Auto-Notify and Holistic Upgrade Experience

**Plan:** `docs/plan/2026-04-12-upgrade-ux-auto-notify-holistic.collab.md`
**Goal:** Wire the existing upgrade infrastructure (update checker, snooze, upgrader) into every user touchpoint — CLI result_callback, skill preamble, version command — remove dead auto-upgrade code, add `--snooze` and `--check` flags, and update skills/specs/UX docs.

---

## Core Insight

All the upgrade machinery exists and is tested. Nothing calls it except `linkedout upgrade`. This plan wires `check_for_update()` into passive touchpoints (CLI banner, skill preamble) and active touchpoints (`linkedout version --check`, `linkedout upgrade --snooze`), then removes dead `try_auto_upgrade()` code.

## Key Decisions

1. **3s timeout for passive banner.** The CLI result_callback uses `timeout=3` (not the default 10s) so the banner never stalls the CLI. The `--check` flag uses 10s since the user explicitly asked.
2. **`--check` bypasses snooze.** `check_for_update(force=True, skip_snooze=True)` gives a truthful answer.
3. **Rename `_append_demo_nudge` → `_post_command_hooks`.** The function now handles multiple post-command concerns.
4. **Remove `auto_upgrade` from `settings.py`.** Dead config field after `try_auto_upgrade()` removal.
5. **Add `--check` + snoozed test.** Verifies `skip_snooze=True` works end-to-end.
6. **Move banner test to `tests/unit/upgrade/`.** Groups with other upgrade notification tests.

## DAG (Build Order)

```
SP01 (CLI Banner) ──────────┐
SP02 (--check flag) ────────┤
SP03 (--snooze flag) ───────┼──► SP05 (Remove auto-upgrade, ──► SP06 (Integration
                            │    update skill & specs)          testing & polish)
SP04 (Skill preamble) ──────┘
     ^
     |
     depends on SP02 for --check --json
```

**Parallelism:** SP01, SP02, SP03 can run in parallel. SP04 depends on SP02. SP05 depends on SP01-SP04. SP06 depends on SP05.

## Key File Locations

| Component | Path |
|-----------|------|
| CLI entry + result_callback | `backend/src/linkedout/cli.py` (lines 108-126) |
| Version command | `backend/src/linkedout/commands/version.py` |
| Upgrade command | `backend/src/linkedout/commands/upgrade.py` |
| Update checker | `backend/src/linkedout/upgrade/update_checker.py` |
| Settings | `backend/src/shared/config/settings.py` (line 228: `auto_upgrade`) |
| Skill template (query) | `skills/linkedout/SKILL.md.tmpl` |
| Skill template (upgrade) | `skills/linkedout-upgrade/SKILL.md.tmpl` |
| Skill generator | `bin/generate-skills` |
| UX design doc | `docs/design/upgrade-flow-ux.human.md` |
| CLI commands spec | `docs/specs/cli_commands.collab.md` |
| Skills system spec | `docs/specs/skills_system.collab.md` |
| Existing upgrade tests | `backend/tests/unit/upgrade/` |

## Existing Functions in update_checker.py

| Function | Lines | Purpose |
|----------|-------|---------|
| `check_for_update()` | 50-78 | Main entry: cache check → API → snooze filter |
| `get_cached_update()` | 94-113 | Read cache if < 1hr old |
| `save_update_cache()` | 116-119 | Write cache |
| `is_snoozed()` | 125-141 | Check snooze state |
| `snooze_update()` | 144-170 | Write snooze with escalation |
| `reset_snooze()` | 173-183 | Clear snooze file |
| `_fetch_and_cache()` | 185-213 | Hit GitHub API, cache result |
| `_is_outdated()` | 216-226 | PEP 440 version comparison |
| `try_auto_upgrade()` | 234-285 | **DEAD CODE — to be removed in SP05** |

## Current `check_for_update()` Signature

```python
def check_for_update() -> UpdateInfo | None:
```

After SP02 modifications:

```python
def check_for_update(*, force: bool = False, skip_snooze: bool = False, timeout: float = 10) -> UpdateInfo | None:
```

- `force=True`: skip cache freshness check, always hit GitHub API
- `skip_snooze=True`: return UpdateInfo even if snoozed (for `--check`)
- `timeout`: HTTP client timeout (3s for passive banner, 10s for explicit check)

## Notification Format Consistency

| Touchpoint | Format | Action text |
|------------|--------|-------------|
| CLI banner (result_callback) | `\nLinkedOut v{latest} available (you have v{current}). Run: linkedout upgrade` | `linkedout upgrade` (CLI) |
| `version --check` (outdated) | `Update available: v{current} -> v{latest}. Run: linkedout upgrade` | `linkedout upgrade` (CLI) |
| `version --check` (current) | `Up to date (v{current})` | — |
| Skill preamble | `LinkedOut v{latest} available (you have v{current}). Run /linkedout-upgrade to update.` | `/linkedout-upgrade` (skill) |

## Key Specs (read before modifying)

- `docs/specs/cli_commands.collab.md` — CLI Structure, version command, upgrade command
- `docs/specs/skills_system.collab.md` — Skills Catalog, template engine

## Testing Conventions

- Unit tests in `backend/tests/unit/upgrade/`
- Use Click's `CliRunner` for CLI tests
- Mock `check_for_update()` and file I/O — never hit real GitHub API
- `from click.testing import CliRunner` + `from linkedout.cli import cli`
