# Sub-phase 4: Demo Nudges, Reset & Transition

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP4 |
| Dependencies | SP3 (demo mode detection and config switching) |
| Estimated effort | 1.5 sessions (~5 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-08-demo-seed-plan.md` — Sub-phase 4 |
| Spec reference | `backend/docs/specs/onboarding-experience.md` |

## Objective

While in demo mode, all CLI output includes a one-line footer nudging toward real setup. A `linkedout reset-demo` command re-restores from the cached dump. A `linkedout use-real-db` command switches config to the real database and optionally drops the demo DB.

## Context

These commands round out the demo experience by giving users a way to reset their demo data (after experimentation) and to transition to their real data when ready. The nudge footer ensures demo users always know how to move forward.

### Key existing files (read these before implementing)

- `backend/src/linkedout/cli.py` — Main CLI group, command registration
- `backend/src/linkedout/demo/__init__.py` — `is_demo_mode()`, `set_demo_mode()` (from SP1)
- `backend/src/linkedout/demo/db_utils.py` — `drop_demo_database`, `create_demo_database`, `restore_demo_dump`, `get_demo_stats` (from SP2)
- `backend/src/linkedout/commands/status.py` — `linkedout status` command
- `backend/src/linkedout/commands/restore_demo.py` — Reference for restore pattern (from SP2)

## Tasks

### 1. Implement nudge footer

Implement via a CLI hook in `backend/src/linkedout/cli.py`:

- Add a `result_callback` to the main CLI group that appends the nudge line after every command's output when `demo_mode` is True
- Implementation: `@cli.result_callback()` / `def _append_demo_nudge(**kwargs):`
- The nudge text: `"\nDemo mode · linkedout setup to use your own data"`
- Read demo_mode lazily (only import config when the callback runs) to avoid slowing down CLI startup
- Alternative approach if result_callback doesn't work well with lazy loading: use a `click.get_current_context().call_on_close()` pattern or a shared decorator. Prefer result_callback for DRY.

### 2. Create reset-demo command

Create `backend/src/linkedout/commands/reset_demo.py`:

- Click command `reset-demo` with `--yes/-y` confirmation skip
- Check demo dump exists at cache path
- Call `drop_demo_database` + `create_demo_database` + `restore_demo_dump` from `demo/db_utils.py`
- Do NOT re-download — reuse cached file (instant reset)
- Print success with profile count

### 3. Create use-real-db command

Create `backend/src/linkedout/commands/use_real_db.py`:

- Click command `use-real-db` with `--drop-demo` flag
- Check that demo mode is currently active (if not: "Already using real database")
- Call `set_demo_mode(data_dir, enabled=False)` to switch config
- If `--drop-demo`: call `drop_demo_database`
- Regenerate `agent-context.env`
- Print: "Switched to real database. Run `linkedout setup` to continue setup."

### 4. Update linkedout status

Update `backend/src/linkedout/commands/status.py`:

- Show `[DEMO]` indicator when demo mode is active
- Show which database is connected: `DB: linkedout_demo (demo)` vs `DB: linkedout`
- In JSON output, add `"demo_mode": true/false` and `"database_name": "..."` fields

### 5. Register commands in CLI

Register `reset-demo` and `use-real-db` commands in `cli.py` under the `# --- Demo ---` section.

### 6. Write tests

- `test_nudge_footer.py` — verify footer appears in demo mode, absent otherwise
- `test_reset_demo.py` — verify drop+restore cycle
- `test_use_real_db.py` — verify config switch and optional drop

## Verification Checklist

- [ ] In demo mode, every CLI command output ends with: `Demo mode · linkedout setup to use your own data`
- [ ] The nudge does not appear when `demo_mode: false`
- [ ] `linkedout reset-demo` drops and re-restores `linkedout_demo` from cached dump
- [ ] `linkedout reset-demo` without cached dump errors with "Run linkedout download-demo first"
- [ ] `linkedout use-real-db` sets `demo_mode: false`, points config at `linkedout` DB
- [ ] `linkedout use-real-db --drop-demo` also drops `linkedout_demo`
- [ ] `linkedout use-real-db` when not in demo mode says "Already using real database"
- [ ] `linkedout status` shows which database is active (demo vs real)
- [ ] All tests pass

## Design Notes

- **Naming:** `reset-demo` follows the `verb-noun` pattern. `use-real-db` is the most descriptive and unambiguous from skill context — no need to read help text.
- **Error paths:** `reset-demo` without a cached dump is a clear error with a recovery action. `use-real-db` when the real `linkedout` DB doesn't exist yet is fine — the user will run `linkedout setup` next.
- **Nudge footer:** Persistent one-liner is the simplest implementation — no state tracking, no dismissal, no frequency logic. Matches the resolved requirement exactly.
- **Nudge edge case:** `result_callback` may not fire for commands that call `sys.exit()`. Test with `reset-db`, `status`, and error cases. Fallback: decorator approach.
