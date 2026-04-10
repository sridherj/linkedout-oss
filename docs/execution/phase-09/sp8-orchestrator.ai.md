# Sub-Phase 8: Setup Orchestrator

**Phase:** 9 — AI-Native Setup Flow
**Plan tasks:** 9Q (Idempotent Re-Run / Orchestrator)
**Dependencies:** sp2-sp7 (all setup modules must exist)
**Blocks:** sp9
**Can run in parallel with:** —

## Objective
Build the main setup orchestrator that ties all setup steps together into a single flow. This is the module that `/linkedout-setup` invokes. It handles step sequencing, state tracking, skip/resume logic, idempotent re-runs, and version-aware upgrades. This is L complexity — the integration layer for the entire setup flow.

## Context
- Read shared context: `docs/execution/phase-09/_shared_context.md`
- Read plan (9Q section): `docs/plan/phase-09-setup-flow.md`
- Read UX design doc: `docs/design/setup-flow-ux.md` (use exact wording for skip/resume messages)
- Read all setup modules from sp2-sp7 (understand their public APIs)
- Read config design: `docs/decision/env-config-design.md`
- Read logging strategy: `docs/decision/logging-observability-strategy.md`

## Deliverables

### 1. `backend/src/linkedout/setup/orchestrator.py` (NEW)

Main setup orchestrator with step tracking, skip/resume, and version awareness.

**Step definition:**
```python
@dataclass
class SetupStep:
    name: str               # e.g., "prerequisites", "database"
    display_name: str       # e.g., "Prerequisites Detection", "Database Setup"
    number: int             # 1-based step number
    function: Callable      # The setup function to call
    can_skip: bool          # True if step state can be validated without re-running
    always_run: bool        # True if step should always run (e.g., migrations, readiness)
    dependencies: list[str] # Step names that must be complete first
```

**Step registry (ordered):**
1. `prerequisites` — sp2 `run_all_checks()`
2. `system_setup` — sp3 `system-setup.sh` (if needed based on prerequisites)
3. `database` — sp3 `setup_database()`
4. `python_env` — sp3 `setup_python_env()`
5. `api_keys` — sp4 `collect_api_keys()`
6. `user_profile` — sp4 `setup_user_profile()`
7. `csv_import` — sp5 `setup_csv_import()`
8. `contacts_import` — sp5 `setup_contacts_import()`
9. `seed_data` — sp5 `setup_seed_data()`
10. `embeddings` — sp6 `setup_embeddings()`
11. `affinity` — sp6 `setup_affinity()`
12. `skills` — sp7 `setup_skills()`
13. `readiness` — sp7 `generate_readiness_report()` (always runs)
14. `auto_repair` — sp7 `run_auto_repair()` (always runs)

**State tracking:**
Persist step completion to `~/linkedout-data/state/setup-state.json`:
```json
{
  "steps_completed": {
    "prerequisites": "2026-04-07T14:20:00Z",
    "system_setup": "2026-04-07T14:21:00Z",
    "database": "2026-04-07T14:22:00Z"
  },
  "setup_version": "0.1.0",
  "last_run": "2026-04-07T14:37:00Z"
}
```

**Skip logic:**
For each step:
1. Check if step is marked complete in state file
2. If complete AND `can_skip=True` AND underlying state is valid → show "✓ Step N: Already complete (skipping)"
3. If complete but underlying state is invalid (e.g., DB exists but migrations behind) → re-run
4. If `always_run=True` → always execute regardless of state

**Re-run as health check:**
On an already-setup system:
- Skip all completed steps (showing ✓ for each)
- Run readiness check (always runs)
- Detect and offer repairs (always runs)
- Produce fresh readiness report
- Expected time: <5 seconds

**Version-aware re-runs:**
- If `setup_version` in state < current version → force re-run of relevant steps
- Specifically: always re-run `database` (new migrations), `python_env` (new dependencies), `skills` (updated skills)

**Error handling:**
- On step failure: log error, generate diagnostic (sp2), show error message, offer to retry or skip
- Partial state is saved — next run resumes from the failed step
- Never leave state file in an inconsistent state (write atomically)

**Key functions:**
- `load_setup_state(data_dir: Path) -> SetupState`
- `save_setup_state(state: SetupState, data_dir: Path)`
- `should_run_step(step: SetupStep, state: SetupState, current_version: str) -> tuple[bool, str]` — returns (should_run, reason)
- `validate_step_state(step_name: str, data_dir: Path, db_url: str) -> bool` — check if underlying state is valid
- `run_setup(data_dir: Path | None = None, repo_root: Path | None = None) -> ReadinessReport` — main entry point
- `run_step(step: SetupStep, context: SetupContext) -> OperationReport` — execute single step with logging

**SetupContext:**
```python
@dataclass
class SetupContext:
    data_dir: Path
    repo_root: Path
    db_url: str | None         # Set after database step
    correlation_id: str        # From logging init
    embedding_provider: str | None  # Set after api_keys step
    user_profile_id: int | None    # Set after user_profile step
```

### 2. CLI Entry Point Integration

Update the CLI to add the setup command. The orchestrator should be invocable as:
- `linkedout setup` — CLI command
- Called by `/linkedout-setup` skill

Add to the appropriate CLI module in `backend/src/dev_tools/cli/`:
```python
@click.command()
@click.option("--data-dir", type=click.Path(), default=None, help="Override data directory")
def setup(data_dir):
    """Run the LinkedOut setup flow."""
    from linkedout.setup.orchestrator import run_setup
    run_setup(data_dir=Path(data_dir) if data_dir else None)
```

### 3. Unit Tests (review finding 2026-04-07: expanded — this is the most complex module, no half measures)

**`backend/tests/linkedout/setup/test_orchestrator.py`** (NEW)

#### State File Loading (`TestLoadSetupState`)
- Missing state file (first install) → returns empty `SetupState` with no completed steps
- Valid state file → parses all fields correctly, timestamps preserved
- Corrupted JSON (truncated write, binary garbage) → returns empty state, logs warning, does NOT crash
- Malformed JSON (valid JSON but wrong schema, e.g., `steps_completed` is a list not dict) → returns empty state, logs warning
- State file with unknown fields (forward compat) → ignores unknown fields, parses known ones
- State file with missing `setup_version` → treats as version "0.0.0" (forces re-run of version-sensitive steps)

#### State File Writing (`TestSaveSetupState`)
- Writes valid JSON that `load_setup_state()` can round-trip
- Writes atomically: temp file + rename (verify no partial writes via mock crash mid-write)
- Handles `LINKEDOUT_DATA_DIR` override for state file path
- Read-only state directory → raises clear `PermissionError` with actionable message ("Cannot write setup state to {path}. Check directory permissions.")

#### Skip/Resume Logic (`TestShouldRunStep`)
- Uncompleted step → `(True, "not yet completed")`
- Completed step with `can_skip=True` + valid underlying state → `(False, "already complete")`
- Completed step with `always_run=True` → `(True, "always runs")` regardless of state
- Completed step but underlying state invalid (mock `validate_step_state` returns False) → `(True, "state invalid: {reason}")`
- Step with unmet dependency (previous step not complete) → raises clear error, not silent skip

#### Version-Aware Re-Runs (`TestVersionAwareReRuns`)
- `setup_version == current_version` → normal skip logic for all steps
- `setup_version < current_version` → forces re-run of `database` (new migrations), `python_env` (new deps), `skills` (updated skills)
- `setup_version < current_version` → does NOT force re-run of `api_keys`, `user_profile`, `csv_import` (user data, not version-sensitive)
- Missing `setup_version` in state → treated as "0.0.0", forces all version-sensitive steps

#### Partial Failure Recovery (`TestPartialFailureRecovery`)
- Step 6 fails → state file has steps 1-5 as complete, step 6 NOT marked
- Re-run after step 6 failure → skips steps 1-5 (shows ✓), retries step 6
- Step failure does NOT corrupt or remove already-completed step entries
- Multiple failures on same step → state still consistent, no duplicate entries
- Step fails, user fixes issue, re-run succeeds → step now marked complete

#### Step Ordering & Context (`TestStepOrdering`)
- Steps execute in registry order (1-14)
- Mutable `SetupContext` passes data forward: `db_url` set by step 3 is available to step 7
- Step that needs `db_url` but it's None (database step was skipped/failed) → clear error, not NPE
- All 14 steps registered and accounted for

#### Performance (`TestPerformance`)
- Second run on fully-complete setup with all steps valid → completes in < 5 seconds (mock all steps, verify `should_run_step` short-circuits without expensive I/O)
- No DB queries during skip evaluation for non-`always_run` steps

#### Validate Step State (`TestValidateStepState`)
- `database`: DB accessible + expected tables exist → True; DB inaccessible → False; DB exists but migrations behind → False
- `python_env`: `.venv/` exists + `linkedout --help` works → True; missing venv → False
- `skills`: skill files exist at expected paths → True; missing → False
- `api_keys`: `secrets.yaml` exists with expected keys → True; missing → False

## Verification
1. `python -c "from linkedout.setup.orchestrator import run_setup"` imports without error
2. `pytest backend/tests/linkedout/setup/test_orchestrator.py -v` passes
3. Mock end-to-end: create a test that mocks all step functions, runs the orchestrator, verifies step ordering and state persistence

## Notes
- This is the most complex module in Phase 9. Take care with error handling and state management.
- State file writes must be atomic — write to temp file, then rename. Never leave a corrupted state file.
- The orchestrator should be the ONLY module that knows the step order. Individual modules don't know about each other.
- The `SetupContext` is mutable — steps add to it as they complete (e.g., database step adds `db_url`).
- Use sp2 logging throughout — every step start/complete/skip/fail is logged with correlation ID.
- The CLI entry point should be a thin wrapper — all logic lives in the orchestrator module.
- Second run performance (<5 seconds) is an explicit acceptance criterion. Don't do expensive validation on skip.
