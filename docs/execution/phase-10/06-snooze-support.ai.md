# Sub-Phase 06: Snooze Support

**Source task:** 10E
**Complexity:** M
**Dependencies:** Sub-phase 03 (update check mechanism)
**Can run in parallel with:** Sub-phase 05 (if sub-phase 03 is complete)

## Objective

Add escalating backoff for update notifications and an auto-upgrade config option. Users who dismiss the update notification get reminded with escalating intervals. Users who want hands-off upgrades can enable auto-upgrade.

## Context

Read `_shared_context.md` for project-level context. Key points:
- State files under `~/linkedout-data/state/`
- Config in `~/linkedout-data/config/config.yaml`
- This extends `update_checker.py` from sub-phase 03

## Deliverables

### Files to Modify

1. **`backend/src/linkedout/upgrade/update_checker.py`** (extend from sub-phase 03)

   Add snooze logic:
   - `is_snoozed(version: str) -> bool`:
     - Read `~/linkedout-data/state/update-snooze.json`
     - Return `True` if current time < `next_reminder` AND `snoozed_version` matches
   - `snooze_update(version: str)`:
     - Read current snooze state (or create new)
     - Increment `snooze_count`
     - Calculate `next_reminder` based on escalation: count 1 → +24h, count 2 → +48h, count 3+ → +1 week
     - Write to `~/linkedout-data/state/update-snooze.json`
   - `reset_snooze()`:
     - Delete or clear snooze file
     - Called when a new version is detected (different from `snoozed_version`)
   
   Integrate with `check_for_update()`:
   - Before returning outdated result, check `is_snoozed()`
   - If snoozed, return `None` (suppress notification)
   - If new version detected (different from snoozed version), call `reset_snooze()`

   Snooze state file format:
   ```json
   {
     "snoozed_at": "2026-04-07T14:30:00Z",
     "snooze_count": 1,
     "next_reminder": "2026-04-08T14:30:00Z",
     "snoozed_version": "0.2.0"
   }
   ```

2. **`backend/src/shared/config/config.py`** (or future `LinkedOutSettings`)
   - Add `auto_upgrade: bool = False` to config schema
   - Document the setting with a comment

3. **Auto-upgrade integration** (in update checker or a thin wrapper)
   - When `auto_upgrade: true` and update is available:
     - On skill invocation, trigger upgrade silently
     - Log output to `~/linkedout-data/logs/cli.log` (no terminal output)
     - If upgrade fails, fall back to notification mode (don't block user)
   - When `auto_upgrade: false` (default): notification only

### Tests to Create

4. **`backend/tests/unit/upgrade/test_snooze.py`**
   - Escalating backoff: first snooze → +24h, second → +48h, third+ → +1 week
   - `is_snoozed()` returns `True` within snooze window
   - `is_snoozed()` returns `False` after snooze expires
   - Snooze resets when new version detected (snoozed v0.2.0, now v0.3.0 available)
   - Snooze state persists across calls (read/write round-trip)
   - Missing snooze file → not snoozed
   - Corrupt snooze file → not snoozed (graceful handling)
   - Auto-upgrade config flag read correctly
   - Auto-upgrade triggers silent upgrade (mocked)
   - Auto-upgrade failure falls back to notification

## Acceptance Criteria

- [ ] Snooze escalation works: 24h → 48h → 1 week
- [ ] Snooze state persisted to `~/linkedout-data/state/update-snooze.json`
- [ ] Snooze resets when new version detected
- [ ] `check_for_update()` respects snooze state
- [ ] `auto_upgrade: true` in config triggers silent upgrade on skill invocation
- [ ] Auto-upgrade logs to file, not terminal
- [ ] Auto-upgrade failure falls back to notification mode (doesn't block user)
- [ ] `auto_upgrade: false` (default) — notification only
- [ ] All unit tests pass

## Verification

```bash
# Run snooze tests
cd backend && python -m pytest tests/unit/upgrade/test_snooze.py -v

# Verify config schema includes auto_upgrade
grep -r "auto_upgrade" backend/src/shared/config/

# Manual test: snooze escalation
python -c "
from linkedout.upgrade.update_checker import snooze_update, is_snoozed
snooze_update('0.2.0')  # First snooze
# Check next_reminder is +24h
"
```

## Notes

- The snooze UI (how the user triggers a snooze) should match the UX design doc from sub-phase 01
- Auto-upgrade is an advanced feature — keep the implementation simple for v1
- Consider: auto-upgrade should not run migrations silently if they could be destructive. For v1, auto-upgrade only pulls code and updates deps; migrations are logged but not auto-applied unless the upgrade report shows no breaking changes
