# Sub-phase 3: Orchestrator Integration & Demo Fork

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP3 |
| Dependencies | SP2 (download/restore commands) |
| Estimated effort | 2 sessions (~6 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-08-demo-seed-plan.md` — Sub-phase 3 |
| Spec reference | `backend/docs/specs/onboarding-experience.md` |

## Objective

When a user runs `linkedout setup`, after step 4 (Python Env) completes, they see a prompt offering to load demo data. Steps 1-4 are common infrastructure for ALL users. If the user accepts, setup runs demo-specific steps D1-D5 (download dump, download embedding model, restore DB, install skills, readiness check) with their own numbering. If they decline, setup continues with steps 5-14 as normal.

## Context

The setup orchestrator currently runs 14 steps sequentially. This sub-phase inserts a decision gate after step 4 that forks the experience into demo vs full setup paths. The demo path must feel like a complete, polished experience — not a shortcut.

### Key existing files (read these before implementing)

- `backend/src/linkedout/setup/orchestrator.py` — `run_setup()`, step execution loop, `should_run_step`
- `backend/src/linkedout/setup/state.py` — `SetupState`, `steps_completed` dict, `save_setup_state`
- `backend/src/linkedout/setup/skill_install.py` — `setup_skills()` (needs `auto_accept` param)
- `backend/src/linkedout/commands/download_demo.py` — `download_demo()` (from SP2)
- `backend/src/linkedout/commands/restore_demo.py` — `restore_demo()` (from SP2)
- `backend/src/linkedout/demo/__init__.py` — `is_demo_mode()`, `set_demo_mode()` (from SP1)

## Tasks

### 1. Create demo offer module

Create `backend/src/linkedout/setup/demo_offer.py`:

- `offer_demo(context: SetupContext) -> bool` — presents the demo prompt with download size (~375 MB), returns True if user accepts
- `run_demo_setup(context: SetupContext) -> OperationReport` — orchestrates D1-D5, returns combined report
- Demo offer prompt explicitly states: "~375 MB total download (demo data + search model)"
- Handles errors gracefully: if download fails (network), report the error and offer to continue with full setup instead

**Demo steps D1-D5** (executed only when user accepts demo):
```
D1: Downloading demo data (100 MB)...        -> download_demo()
D2: Downloading search model (275 MB)...     -> pre_download_model('local')
D3: Restoring demo database...               -> restore_demo()
D4: Installing skills for Claude Code...     -> setup_skills() with auto_accept=True
D5: Readiness check...                       -> generate_readiness_report()
```

These are NOT formal SetupSteps. They are inline in `run_demo_setup()` with D-prefixed output labels.

### 2. Modify orchestrator for demo fork

Modify `backend/src/linkedout/setup/orchestrator.py`:

- Insert a "decision gate" in `run_setup` after step 4 completes. NOT a formal `SetupStep`.
- After the python_env step succeeds:
  1. Check if this is a fresh setup (no steps beyond python_env are complete)
  2. Check if `demo_mode` is already set in config (don't re-offer)
  3. If eligible, call `offer_demo(context)` which presents the prompt
  4. If accepted, run the D1-D5 demo steps, then return — don't continue with steps 5-14
  5. Mark steps 5-11 as `"demo-skipped"` in `SetupState.steps_completed`
- Add `DEMO_SKIPPABLE_STEPS` constant: `{"api_keys", "user_profile", "csv_import", "contacts_import", "seed_data", "embeddings", "affinity"}`

**Step numbering logic:**
- When the demo offer is eligible (fresh setup, steps 1-4 only), display steps 1-4 as "Step N of 4"
- When demo is declined, restart numbering as "Step 5 of 14" for the remaining steps
- When demo is not eligible (re-run), show "Step N of 14" as normal

### 3. Modify setup_skills for auto_accept

Modify `setup_skills()` in `backend/src/linkedout/setup/skill_install.py`:

- Add `auto_accept: bool = False` parameter
- When `auto_accept=True` (demo mode), skip the Y/n prompt. Instead print what's being installed with "(skip with Ctrl+C)" note
- Default behavior (full setup) unchanged — Y/n prompt remains

### 4. Update should_run_step for demo-skipped state

Modify `should_run_step` to recognize `"demo-skipped"` as a completed state:

- Currently checks `if not completed_at:` — `"demo-skipped"` counts as completed

### 5. Implement transition flow

When `linkedout setup` detects `demo_mode: true` in config:

- Present transition prompt: "You're using demo data. Ready to set up with your own connections? [Y/n]"
- Below the prompt: "Your network, your profile — affinity scores will be personalized to you."
- If accepted: clear `"demo-skipped"` markers for steps 5-11, set `demo_mode: false`, update `database_url` to `linkedout`, regenerate `agent-context.env`, then run steps 5-14 as normal
- If declined: show all steps as complete/skipped (fast no-op), exit

### 6. Write tests

- `test_demo_offer_flow.py` — mock user input, verify D1-D5 execute in order
- `test_orchestrator_demo_mode.py` — verify demo steps run, steps 5-14 do NOT run
- `test_should_run_step_demo_skipped.py` — verify `"demo-skipped"` is treated as complete
- `test_step_numbering.py` — verify "Step N of 4" in demo-eligible run, "Step N of 14" otherwise
- `test_transition_flow.py` — verify accepting transition clears demo-skipped, runs 5-14
- `test_demo_rerun_noop.py` — verify re-running setup in demo mode (declining transition) is fast no-op

## Verification Checklist

- [ ] Fresh setup: after step 4, user sees the demo offer prompt
- [ ] Steps 1-4 show "Step N of 4" (not "of 14") when demo path is taken
- [ ] Accepting demo: D1-D5 execute with demo-specific labels
- [ ] Declining demo: steps 5-14 run as normal (steps show "Step N of 14")
- [ ] Re-running setup after demo: steps 1-4 skip (already complete), no re-prompt for demo
- [ ] `setup-state.json` records `demo_mode: true` when demo is accepted
- [ ] Demo steps show progress output with download sizes
- [ ] Transition flow: accepting clears demo-skipped, runs steps 5-14
- [ ] Transition flow: declining is a fast no-op
- [ ] All tests pass

## Design Notes

- **Architecture:** Inserting the demo offer as inline logic in `run_setup` rather than a formal step avoids re-numbering all 14 steps — a breaking change to `setup-state.json`.
- **D1-D5 numbering:** Presentation-only — no new SetupStep objects, no state file changes.
- **Error paths:** If any D-step fails, fall back to offering full setup. `setup-state.json` only records demo-skipped states after a successful D3 (restore).
- **Transition:** `linkedout setup` is the ONE path for transitioning. `use-real-db` exists as a power-user escape hatch. The nudge footer says "linkedout setup to use your own data" — consistent with the transition trigger.
- **Spec:** See `backend/docs/specs/onboarding-experience.md` for the full terminal narratives.
