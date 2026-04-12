# Sub-phase 02: Version Command `--check` Flag

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP02 |
| Dependencies | None (can start immediately; coordinate with SP01 on `check_for_update()` signature) |
| Estimated effort | 1 session (~1.5 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-12-upgrade-ux-auto-notify-holistic.collab.md` — Sub-phase 2 |
| Shared context | `_shared_context.md` |

## Objective

`linkedout version --check` runs a fresh update check (ignoring cache and snooze) and prints either:
- `Up to date (v{current})` with exit code 0, or
- `Update available: v{current} -> v{latest}. Run: linkedout upgrade` with exit code 1

`linkedout version --check --json` returns structured JSON.

## Context

The `version` command at `backend/src/linkedout/commands/version.py` currently only shows version info. We add a `--check` flag that calls `check_for_update(force=True, skip_snooze=True)` to give a fresh, truthful answer regardless of cache or snooze state.

## Tasks

### 1. Add `force` and `skip_snooze` parameters to `check_for_update()`

**File:** `backend/src/linkedout/upgrade/update_checker.py`

Extend the function signature. If SP01 already added `timeout`, merge the parameters:

```python
def check_for_update(*, force: bool = False, skip_snooze: bool = False, timeout: float = 10) -> UpdateInfo | None:
    """Check GitHub for a newer release, returning None on any error.

    Args:
        force: Skip cache freshness check, always hit GitHub API.
        skip_snooze: Return UpdateInfo even if snoozed (for --check).
        timeout: HTTP client timeout in seconds.
    """
    if not force:
        cached = get_cached_update()
        if cached is not None:
            info = cached
        else:
            try:
                info = _fetch_and_cache(timeout=timeout)
            except Exception:
                logger.debug('Update check failed — continuing without update info')
                return None
    else:
        try:
            info = _fetch_and_cache(timeout=timeout)
        except Exception:
            logger.debug('Update check failed — continuing without update info')
            return None

    if info is None or not info.is_outdated:
        return info

    # Reset snooze if a different (newer) version was detected
    _maybe_reset_snooze(info.latest_version)

    # Suppress notification if snoozed (unless caller asked to skip snooze)
    if not skip_snooze and is_snoozed(info.latest_version):
        return None

    return info
```

Key points:
- `force=True` skips the `get_cached_update()` path entirely and always hits `_fetch_and_cache()`
- The cache is still **written** on success (via `save_update_cache()` inside `_fetch_and_cache()`), so the next passive banner doesn't need another API call
- `skip_snooze=True` bypasses the `is_snoozed()` check, so `--check` always returns the truth
- All existing callers pass no arguments, so behavior is unchanged

### 2. Add `--check` flag to the version command

**File:** `backend/src/linkedout/commands/version.py`

```python
@click.command('version')
@click.option('--json', 'as_json', is_flag=True, help='Output version info as JSON.')
@click.option('--check', 'check_update', is_flag=True, help='Check for available updates.')
def version_command(as_json: bool, check_update: bool):
    """Show version information."""
    if check_update:
        _handle_check(as_json)
        return

    from linkedout.version import __version__, get_version_info

    if as_json:
        click.echo(json.dumps(get_version_info(), indent=2))
        return

    info = get_version_info()
    click.echo(_read_logo())
    click.echo()
    click.echo(f"v{info['version']}")
    click.echo(f"Python {info['python_version']}")
    click.echo(f"PostgreSQL {info['pg_version']}")
    click.echo(f"Install path: {info['install_path']}")
    click.echo(f"Config: {info['config_path']}")
    click.echo(f"Data dir: {info['data_dir']}")
```

### 3. Implement `_handle_check()` helper

In the same file (`version.py`), add a private helper:

```python
import sys


def _handle_check(as_json: bool) -> None:
    """Handle the --check flag: fresh update check with exit code."""
    from linkedout.upgrade.update_checker import check_for_update
    from linkedout.version import __version__

    try:
        info = check_for_update(force=True, skip_snooze=True)
    except Exception:
        if as_json:
            click.echo(json.dumps({'error': 'Could not check for updates'}))
        else:
            click.echo('Could not check for updates. Try again later.')
        sys.exit(1)

    if info is None:
        if as_json:
            click.echo(json.dumps({'error': 'Could not check for updates'}))
        else:
            click.echo('Could not check for updates. Try again later.')
        sys.exit(1)

    if as_json:
        click.echo(json.dumps({
            'update_available': info.is_outdated,
            'current': info.current_version,
            'latest': info.latest_version,
            'release_url': info.release_url,
        }, indent=2))
        sys.exit(1 if info.is_outdated else 0)

    if info.is_outdated:
        click.echo(
            f'Update available: v{info.current_version} -> v{info.latest_version}. '
            f'Run: linkedout upgrade'
        )
        sys.exit(1)
    else:
        click.echo(f'Up to date (v{info.current_version})')
        sys.exit(0)
```

### 4. Write unit test

**New file:** `backend/tests/unit/upgrade/test_version_check_flag.py`

Test cases:

1. **`--check` with outdated version:** Mock `check_for_update(force=True, skip_snooze=True)` to return `UpdateInfo(is_outdated=True, latest_version='0.3.0', current_version='0.2.0', ...)`. Assert output: `"Update available: v0.2.0 -> v0.3.0. Run: linkedout upgrade"`. Assert exit code 1.

2. **`--check` with current version:** Mock returns `UpdateInfo(is_outdated=False, ...)`. Assert output: `"Up to date (v0.2.0)"`. Assert exit code 0.

3. **`--check --json` with outdated:** Assert JSON output has `update_available: true`, correct versions, exit code 1.

4. **`--check --json` with current:** Assert JSON output has `update_available: false`, exit code 0.

5. **`--check` with network error:** Mock returns `None`. Assert output: `"Could not check for updates."`. Assert exit code 1.

6. **`--check` bypasses snooze:** Mock `check_for_update` and verify it was called with `force=True, skip_snooze=True`. This confirms the CLI wiring passes the right flags.

7. **`version` without `--check` is unchanged:** Invoke `linkedout version`, assert the normal version output (logo, version, etc.), no update check.

Use `CliRunner` with `catch_exceptions=False` for exit code testing. Note: Click's `CliRunner` captures `SystemExit` — check `result.exit_code`.

## Verification

```bash
# Run the new test
pytest backend/tests/unit/upgrade/test_version_check_flag.py -v

# Run all upgrade tests (regression check)
pytest backend/tests/unit/upgrade/ -v

# Check imports work
cd backend && python -c "from linkedout.commands.version import version_command; print('OK')"
```

## Coordination with SP01

Both SP01 and SP02 modify `check_for_update()` in `update_checker.py`. SP01 adds `timeout`, SP02 adds `force` and `skip_snooze`. If running in parallel:
- The second to merge reconciles the signature: all three are additive keyword-only args with defaults
- Final signature: `check_for_update(*, force=False, skip_snooze=False, timeout=10)`
- No conflicting logic — `force` controls cache bypass, `timeout` controls HTTP, `skip_snooze` controls snooze filter

## What NOT to Do

- Do not modify `cli.py` — that's SP01
- Do not add `--snooze` to the upgrade command — that's SP03
- Do not modify skill templates — that's SP04
- Do not update specs — that's bundled into SP05
- Do not add version comparison logic to the version command — reuse `check_for_update()`
