# Sub-phase 06: Integration Testing and Polish

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP06 |
| Dependencies | SP05 (all code changes complete) |
| Estimated effort | 1 session (~1.5 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-12-upgrade-ux-auto-notify-holistic.collab.md` — Sub-phase 6 |
| Shared context | `_shared_context.md` |

## Objective

End-to-end verification that all notification touchpoints work together. The notification is consistent across CLI commands, `linkedout version --check`, and the skill preamble. Snooze works across all touchpoints. The upgrade experience feels cohesive.

## Context

SP01-SP05 have added:
- CLI result_callback update banner (SP01)
- `linkedout version --check` flag (SP02)
- `linkedout upgrade --snooze` flag (SP03)
- Skill preamble version check (SP04)
- Removed auto-upgrade, updated skill + specs (SP05)

This sub-phase writes integration tests and does a final verification pass.

## Tasks

### 1. Write notification lifecycle integration test

**New file:** `backend/tests/unit/upgrade/test_upgrade_notification_flow.py`

This test exercises the full notification lifecycle using Click's `CliRunner` with mocked HTTP responses and a temporary file system for cache/snooze state.

Use `tmp_path` fixture to isolate cache and snooze files. Monkeypatch `update_checker.CACHE_FILE` and `update_checker.SNOOZE_FILE` to point at temp paths.

**Test: Full notification lifecycle**

```python
def test_notification_lifecycle(tmp_path, monkeypatch):
    """Full flow: see banner → snooze → banner disappears → snooze expires → banner reappears."""
    # Setup: mock GitHub API to return a newer version
    # Monkeypatch CACHE_FILE and SNOOZE_FILE to tmp_path

    # Step 1: First command shows banner
    result = runner.invoke(cli, ['status'])
    assert 'LinkedOut v0.3.0 available' in result.output

    # Step 2: Snooze the update
    result = runner.invoke(cli, ['upgrade', '--snooze'])
    assert 'snoozed for 24 hours' in result.output

    # Step 3: Next command — banner suppressed
    result = runner.invoke(cli, ['status'])
    assert 'LinkedOut v0.3.0 available' not in result.output

    # Step 4: Fast-forward past snooze expiry (manipulate snooze file)
    # Set next_reminder to 1 hour ago
    snooze_data = json.loads(snooze_file.read_text())
    snooze_data['next_reminder'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    snooze_file.write_text(json.dumps(snooze_data))

    # Step 5: Banner reappears
    result = runner.invoke(cli, ['status'])
    assert 'LinkedOut v0.3.0 available' in result.output
```

**Test: Upgrade clears notification**

```python
def test_upgrade_clears_notification(tmp_path, monkeypatch):
    """After successful upgrade, banner no longer shows."""
    # Setup: outdated version in cache

    # Step 1: Banner shows
    result = runner.invoke(cli, ['version'])
    assert 'LinkedOut v0.3.0 available' in result.output

    # Step 2: Run upgrade (mock upgrader to succeed + update version)
    # After upgrade, version matches latest — no longer outdated

    # Step 3: No more banner
    result = runner.invoke(cli, ['version'])
    assert 'LinkedOut v0.3.0 available' not in result.output
```

**Test: `--check` works independently**

```python
def test_check_independent_of_banner(tmp_path, monkeypatch):
    """--check gives truth regardless of snooze/cache state."""
    # Setup: snoozed version in snooze file

    # Banner is suppressed (snoozed)
    result = runner.invoke(cli, ['version'])
    assert 'LinkedOut v0.3.0 available' not in result.output

    # But --check still reports the update (bypasses snooze)
    result = runner.invoke(cli, ['version', '--check'])
    assert 'Update available' in result.output
    assert result.exit_code == 1
```

**Test: All touchpoints share state**

```python
def test_shared_cache_state(tmp_path, monkeypatch):
    """CLI banner and --check share the same cache file."""
    # Step 1: --check writes to cache (force=True hits API)
    result = runner.invoke(cli, ['version', '--check'])

    # Step 2: CLI banner reads from cache (no API call)
    # Mock: make the API endpoint fail
    # Banner should still show (reads cached data from --check)
    result = runner.invoke(cli, ['version'])
    assert 'LinkedOut v0.3.0 available' in result.output
```

### 2. Verify notification format consistency

Add a test that verifies the notification text follows the expected patterns:

```python
def test_notification_format_consistency():
    """All notification messages follow the expected format."""
    # CLI banner format
    banner = f"\nLinkedOut v{latest} available (you have v{current}). Run: linkedout upgrade"

    # --check format (outdated)
    check_msg = f"Update available: v{current} -> v{latest}. Run: linkedout upgrade"

    # --check format (current)
    check_ok = f"Up to date (v{current})"

    # Snooze confirmation
    snooze_msg = f"Update v{latest} snoozed for 24 hours. Run 'linkedout upgrade' when ready."
```

### 3. Run full test suite

```bash
# All upgrade unit tests
pytest backend/tests/unit/upgrade/ -v

# Broader regression: CLI tests
pytest backend/tests/unit/cli/ -v

# Full unit test suite (if time permits)
pytest backend/tests/unit/ -v --timeout=60
```

### 4. Manual smoke test checklist

If feasible (e.g., with a mock GitHub release endpoint or by manipulating cache files):

- [ ] `linkedout version` — shows version info, update banner if outdated
- [ ] `linkedout version --check` — fresh check, correct exit code
- [ ] `linkedout version --check --json` — structured JSON output
- [ ] `linkedout status` — normal status, update banner if outdated
- [ ] `linkedout upgrade --snooze` — snoozes with confirmation
- [ ] After snooze: `linkedout status` — no banner
- [ ] `linkedout upgrade` — upgrade flow works
- [ ] After upgrade: `linkedout version` — no banner
- [ ] Demo mode: `linkedout version` — both demo nudge and banner appear
- [ ] No network: `linkedout version` — no banner, no error, no delay

### 5. Final cleanup

- Ensure no `TODO` or `FIXME` comments were left by SP01-SP05
- Ensure no unused imports were introduced
- Ensure test file names follow the convention (`test_*.py`)
- Verify `__init__.py` exists in `backend/tests/unit/upgrade/` (it does: already present)

## Verification

```bash
# All new tests pass
pytest backend/tests/unit/upgrade/test_upgrade_notification_flow.py -v

# All upgrade tests pass
pytest backend/tests/unit/upgrade/ -v

# No references to removed code
grep -rn 'try_auto_upgrade' backend/
grep -rn 'auto_upgrade' backend/src/ --include='*.py'

# Skills regenerated correctly
bin/generate-skills 2>&1 | tail -5
```

## What NOT to Do

- Do not add new features — this is a verification-only sub-phase
- Do not modify the notification format — that was decided in SP01-SP04
- Do not add configuration options — the banner is always-on (controlled by snooze)
- Do not write end-to-end tests that hit real GitHub API — mock everything
