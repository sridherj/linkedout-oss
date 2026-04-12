# Sub-phase 03: Snooze CLI Flag

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP03 |
| Dependencies | None (can start immediately) |
| Estimated effort | 0.5 session (~1 hour) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-12-upgrade-ux-auto-notify-holistic.collab.md` — Sub-phase 3 |
| Shared context | `_shared_context.md` |

## Objective

`linkedout upgrade --snooze` explicitly snoozes the current update notification. The user sees a confirmation message with the snooze duration. The existing automatic snooze (implicit escalation) continues to work.

## Context

The snooze machinery (`snooze_update()`, `is_snoozed()`, `_SNOOZE_DURATIONS`) already exists in `backend/src/linkedout/upgrade/update_checker.py`. This sub-phase adds a CLI flag that invokes it, plus a `get_snooze_duration()` helper for displaying the duration.

## Tasks

### 1. Add `get_snooze_duration()` to update_checker.py

**File:** `backend/src/linkedout/upgrade/update_checker.py`

Add after the existing `snooze_update()` function:

```python
def get_snooze_duration(version: str) -> timedelta | None:
    """Return the duration of the next snooze for display purposes.

    Reads the current snooze count for *version* and computes what the
    next snooze duration would be. Returns None if no update is available
    (caller should check first).
    """
    snooze_count = 0
    try:
        if SNOOZE_FILE.exists():
            data = json.loads(SNOOZE_FILE.read_text())
            if data.get('snoozed_version') == version:
                snooze_count = data.get('snooze_count', 0)
    except Exception:
        pass

    next_count = snooze_count + 1
    return _SNOOZE_DURATIONS.get(next_count, _SNOOZE_DEFAULT_DURATION)
```

### 2. Add `--snooze` flag to the upgrade command

**File:** `backend/src/linkedout/commands/upgrade.py`

Add the `--snooze` option and handle it before the upgrade flow:

```python
@click.command('upgrade')
@click.option('--verbose', is_flag=True, help='Show detailed command output')
@click.option('--snooze', 'do_snooze', is_flag=True, help='Snooze update notification')
def upgrade_command(verbose: bool, do_snooze: bool) -> None:
    """Upgrade LinkedOut to the latest version."""
    if do_snooze:
        _handle_snooze()
        return

    # ... existing upgrade flow unchanged ...
```

### 3. Implement `_handle_snooze()` helper

In the same file (`upgrade.py`), add:

```python
def _handle_snooze() -> None:
    """Handle --snooze: snooze update notification with confirmation."""
    from linkedout.upgrade.update_checker import (
        check_for_update,
        get_snooze_duration,
        snooze_update,
    )

    info = check_for_update()
    if info is None or not info.is_outdated:
        click.echo('Already running the latest version.')
        return

    # Show what the snooze duration will be
    duration = get_snooze_duration(info.latest_version)
    snooze_update(info.latest_version)

    duration_str = _format_duration(duration)
    click.echo(
        f"Update v{info.latest_version} snoozed for {duration_str}. "
        f"Run 'linkedout upgrade' when ready."
    )


def _format_duration(td) -> str:
    """Format a timedelta as a human-readable duration string."""
    hours = td.total_seconds() / 3600
    if hours <= 24:
        return '24 hours'
    elif hours <= 48:
        return '48 hours'
    else:
        return '1 week'
```

Key details:
- `--snooze` calls `check_for_update()` (without `force` — respects cache) to get the latest version
- If not outdated, prints "Already running the latest version." and exits
- If outdated, calls `snooze_update(version)` and prints confirmation with duration
- `--snooze` skips the entire upgrade flow (early return before the `Upgrader` is instantiated)
- `--snooze` and `--verbose` can coexist (snooze ignores verbose)
- If `check_for_update()` returns `None` (network error), prints "Could not check for updates. Try again later."

### 4. Handle network error in snooze

Update `_handle_snooze()` to distinguish between "up to date" (info returned, not outdated) and "can't reach GitHub" (None returned):

The current `check_for_update()` returns `None` on network error AND when snoozed. For `--snooze`, we should still try even if already snoozed. Since `--snooze` doesn't pass `skip_snooze`, a snoozed version returns `None`. But calling `--snooze` on an already-snoozed version should still increment the count.

Approach: Use `check_for_update(skip_snooze=True)` to bypass the snooze filter, so we can still snooze an already-snoozed version (increments count). This requires SP02's `skip_snooze` parameter.

**If SP02 hasn't run yet:** Use `get_cached_update()` as a fallback to read the cached version info directly, bypassing snooze. This avoids a hard dependency:

```python
def _handle_snooze() -> None:
    from linkedout.upgrade.update_checker import (
        check_for_update,
        get_cached_update,
        get_snooze_duration,
        snooze_update,
    )

    # Try to get update info, bypassing snooze if supported
    try:
        info = check_for_update(skip_snooze=True)
    except TypeError:
        # skip_snooze not yet available (SP02 hasn't merged)
        info = check_for_update() or get_cached_update()

    if info is None:
        click.echo('Could not check for updates. Try again later.')
        return

    if not info.is_outdated:
        click.echo('Already running the latest version.')
        return

    duration = get_snooze_duration(info.latest_version)
    snooze_update(info.latest_version)

    duration_str = _format_duration(duration)
    click.echo(
        f"Update v{info.latest_version} snoozed for {duration_str}. "
        f"Run 'linkedout upgrade' when ready."
    )
```

**Simpler approach if SP02 is guaranteed to run first or in parallel:** Just use `skip_snooze=True` directly (if the param exists) or `check_for_update()` (falls through to not-snoozed for first snooze). For the MVP, `check_for_update()` without flags works for the first snooze. Subsequent snoozes on the same version can read cached update info via `get_cached_update()`.

### 5. Write unit tests

Add tests in `backend/tests/unit/upgrade/test_update_checker.py` for `get_snooze_duration()`:

1. **First snooze:** No snooze file exists. Returns `timedelta(hours=24)`.
2. **Second snooze:** Snooze file has `snooze_count=1`. Returns `timedelta(hours=48)`.
3. **Third+ snooze:** Snooze file has `snooze_count=2`. Returns `timedelta(weeks=1)`.
4. **Different version:** Snooze file has a different `snoozed_version`. Returns `timedelta(hours=24)` (resets).

Add CLI test for `--snooze` flag (can be in same file or `test_snooze.py`):

5. **`--snooze` with outdated version:** Mock `check_for_update()` to return outdated. Assert output: `"Update v0.3.0 snoozed for 24 hours."`. Assert `snooze_update` was called.
6. **`--snooze` when up to date:** Mock returns not outdated. Assert output: `"Already running the latest version."`.
7. **`--snooze` with network error:** Mock returns `None`. Assert output: `"Could not check for updates."`.
8. **`--snooze` with already snoozed version:** Mock `check_for_update()` returning outdated info + existing snooze file. Assert output shows increased duration (48 hours).

## Verification

```bash
# Run update checker tests (includes new get_snooze_duration tests)
pytest backend/tests/unit/upgrade/test_update_checker.py -v

# Run snooze tests
pytest backend/tests/unit/upgrade/test_snooze.py -v

# Run all upgrade tests
pytest backend/tests/unit/upgrade/ -v
```

## What NOT to Do

- Do not modify `cli.py` — that's SP01
- Do not add `--check` to the version command — that's SP02
- Do not modify skill templates — that's SP04
- Do not update specs — that's bundled into SP05
- Do not change the existing `snooze_update()` behavior — only add `get_snooze_duration()` alongside it
