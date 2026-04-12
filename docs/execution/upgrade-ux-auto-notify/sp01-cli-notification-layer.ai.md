# Sub-phase 01: CLI Notification Layer

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP01 |
| Dependencies | None (can start immediately) |
| Estimated effort | 1 session (~2 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-12-upgrade-ux-auto-notify-holistic.collab.md` — Sub-phase 1 |
| Shared context | `_shared_context.md` |

## Objective

After every `linkedout` CLI command, if an update is available (and not snoozed, and cache says so), a single-line banner appears:

```
LinkedOut v{latest} available (you have v{current}). Run: linkedout upgrade
```

Demo nudge continues to work. Network errors are invisible. No delay beyond 3s worst-case on cold cache.

## Context

The `_append_demo_nudge` function in `backend/src/linkedout/cli.py` (line 117) is the result_callback for the CLI group. It currently only handles the demo mode nudge. We rename it and extend it to also show an update notification banner.

## Tasks

### 1. Rename `_append_demo_nudge` → `_post_command_hooks`

**File:** `backend/src/linkedout/cli.py` (line 117)

Rename the function and update the docstring to reflect its broader purpose. The function now handles multiple post-command concerns (demo nudge + update banner).

```python
@cli.result_callback()
@click.pass_context
def _post_command_hooks(ctx, *args, **kwargs):
    """Run post-command hooks: demo nudge + update notification banner."""
```

### 2. Add update notification banner

In the same `_post_command_hooks` function, after the demo nudge block, add the update check:

```python
    # Update notification banner (passive — never blocks, never errors)
    try:
        # Skip banner when running the upgrade command itself
        if ctx.invoked_subcommand == 'upgrade':
            return

        from linkedout.upgrade.update_checker import check_for_update

        info = check_for_update(timeout=3)
        if info and info.is_outdated:
            click.echo(
                f"\nLinkedOut v{info.latest_version} available "
                f"(you have v{info.current_version}). "
                f"Run: linkedout upgrade"
            )
    except Exception:
        pass
```

Key details:
- **Lazy import** `check_for_update` inside the function to keep CLI startup fast
- **3s timeout** (not 10s default) — the passive banner should fail fast on slow networks
- **Suppress during `upgrade`** — check `ctx.invoked_subcommand` and skip if it's `'upgrade'` (the upgrade command already handles its own update check)
- **Ordering** — demo nudge prints first, then update banner. Both are conditional and independent
- **try/except Exception: pass** — zero-failure guarantee; the result_callback must never break the CLI

### 3. Modify `check_for_update()` to accept `timeout` parameter

**File:** `backend/src/linkedout/upgrade/update_checker.py`

This task adds the `timeout` parameter only. SP02 adds `force` and `skip_snooze`.

Change the signature from:

```python
def check_for_update() -> UpdateInfo | None:
```

To:

```python
def check_for_update(*, timeout: float = 10) -> UpdateInfo | None:
```

Pass `timeout` through to `_fetch_and_cache()`:

```python
def check_for_update(*, timeout: float = 10) -> UpdateInfo | None:
    cached = get_cached_update()
    if cached is not None:
        info = cached
    else:
        try:
            info = _fetch_and_cache(timeout=timeout)
        except Exception:
            logger.debug('Update check failed — continuing without update info')
            return None
    # ... rest unchanged
```

Update `_fetch_and_cache()` to accept `timeout`:

```python
def _fetch_and_cache(timeout: float = 10) -> UpdateInfo | None:
    # ...
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(GITHUB_API_URL, headers=headers)
    # ...
```

**Note on coordination with SP02:** SP02 adds `force` and `skip_snooze` parameters to the same function. If SP01 and SP02 run in parallel, the second to merge will need to reconcile the signature. Both changes are additive keyword-only arguments, so the merge is straightforward. The final signature after both:

```python
def check_for_update(*, force: bool = False, skip_snooze: bool = False, timeout: float = 10) -> UpdateInfo | None:
```

### 4. Write unit test

**New file:** `backend/tests/unit/upgrade/test_cli_update_banner.py`

Test cases:

1. **Banner shown when outdated:** Mock `check_for_update()` to return `UpdateInfo(is_outdated=True, latest_version='0.3.0', current_version='0.2.0', ...)`. Invoke `linkedout version` via `CliRunner`. Assert output contains `"LinkedOut v0.3.0 available (you have v0.2.0). Run: linkedout upgrade"`.

2. **No banner when up to date:** Mock returns `UpdateInfo(is_outdated=False, ...)`. Assert banner text not in output.

3. **No banner when check returns None:** Mock returns `None` (network error). Assert no banner, no error.

4. **No banner when check raises:** Mock raises `Exception`. Assert no banner, no error.

5. **No banner during `upgrade` command:** Invoke `linkedout upgrade` (mock the upgrader). Assert no double banner.

6. **Demo nudge + update banner coexistence:** Mock both `is_demo_mode()=True` and `check_for_update()` returning outdated. Assert both messages appear in output, demo nudge first.

7. **No banner when snoozed:** This is handled inside `check_for_update()` itself (returns `None` when snoozed), so a mock returning `None` covers this case.

Use `unittest.mock.patch` targeting `linkedout.cli.check_for_update` (the import location in the result_callback). Use Click's `CliRunner(mix_stderr=False)` to capture stdout separately.

## Verification

```bash
# Run the new test
pytest backend/tests/unit/upgrade/test_cli_update_banner.py -v

# Run all upgrade tests (regression check)
pytest backend/tests/unit/upgrade/ -v

# Manual smoke test (optional — requires mock or stale cache)
# With a simulated outdated version:
linkedout version  # should show banner after version info
linkedout status   # should show banner after status output
```

## What NOT to Do

- Do not add `force` or `skip_snooze` parameters to `check_for_update()` — that's SP02
- Do not modify the version or upgrade commands — those are SP02 and SP03
- Do not update specs — that's bundled into SP05
- Do not add any configuration options — the banner is always-on (suppressed by snooze)
- Do not change the demo nudge behavior — only add to it
