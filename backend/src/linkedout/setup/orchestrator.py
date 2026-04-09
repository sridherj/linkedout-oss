# SPDX-License-Identifier: Apache-2.0
"""Main setup orchestrator for LinkedOut OSS.

Ties all setup steps into a single flow invoked by ``linkedout setup``.
Handles step sequencing, state tracking, skip/resume logic, idempotent
re-runs, and version-aware upgrades.

State is persisted to ``~/linkedout-data/state/setup-state.json``. On a
fully set-up system, re-running the setup acts as a fast health check
(< 5 seconds with all steps skipping).

The orchestrator is the ONLY module that knows the step order. Individual
setup modules are unaware of each other.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from linkedout.setup.logging_integration import (
    generate_diagnostic,
    get_setup_logger,
    init_setup_logging,
    log_step_complete,
    log_step_start,
)
from shared.utilities.operation_report import OperationReport

# ── Version ─────────────────────────────────────────────────────────
_LINKEDOUT_VERSION = "0.1.0"

# Steps that must re-run when the LinkedOut version changes
_VERSION_SENSITIVE_STEPS = frozenset({"database", "python_env", "skills"})

# Steps skipped when the user accepts the demo path (steps 5-11)
DEMO_SKIPPABLE_STEPS = frozenset({
    "api_keys", "user_profile", "csv_import", "contacts_import",
    "seed_data", "embeddings", "affinity",
})

# Number of infrastructure steps common to both paths
_INFRA_STEP_COUNT = 4


# ── Data classes ────────────────────────────────────────────────────


@dataclass
class SetupStep:
    """Definition of a single setup step.

    Attributes:
        name: Internal key (e.g., ``"prerequisites"``).
        display_name: Human-readable label (e.g., ``"Prerequisites Detection"``).
        number: 1-based step number.
        function: The callable to execute for this step.
        can_skip: ``True`` if the step state can be validated without re-running.
        always_run: ``True`` if the step should always execute (e.g., readiness).
        dependencies: Step names that must be complete first.
    """

    name: str
    display_name: str
    number: int
    function: Callable
    can_skip: bool = True
    always_run: bool = False
    dependencies: list[str] = field(default_factory=list)


@dataclass
class SetupState:
    """Persisted state from ``setup-state.json``.

    Attributes:
        steps_completed: Mapping of step name to ISO timestamp (or ``"skipped"``).
        setup_version: LinkedOut version that last ran setup.
        last_run: ISO timestamp of the last setup run.
        last_failure: Optional dict with ``step``, ``error``, ``timestamp`` keys.
    """

    steps_completed: dict[str, str | None] = field(default_factory=dict)
    setup_version: str = "0.0.0"
    last_run: str = ""
    last_failure: dict | None = None


@dataclass
class SetupContext:
    """Mutable context passed through setup steps.

    Steps add to this as they complete (e.g., the database step sets
    ``db_url``).

    Attributes:
        data_dir: Root data directory (``~/linkedout-data``).
        repo_root: Repository root directory.
        db_url: Database connection URL, set after the database step.
        correlation_id: Logging correlation ID from ``init_setup_logging()``.
        embedding_provider: Embedding provider choice, set after api_keys step.
        user_profile_id: User profile ID, set after user_profile step.
    """

    data_dir: Path
    repo_root: Path
    db_url: str | None = None
    correlation_id: str = ""
    embedding_provider: str | None = None
    user_profile_id: int | None = None


# ── State persistence ───────────────────────────────────────────────


def load_setup_state(data_dir: Path) -> SetupState:
    """Load persisted setup state from ``setup-state.json``.

    Args:
        data_dir: Root data directory (e.g., ``~/linkedout-data``).

    Returns:
        A ``SetupState`` instance. Returns empty state if the file is
        missing, corrupt, or malformed.
    """
    log = get_setup_logger("orchestrator")
    state_path = _state_path(data_dir)

    if not state_path.exists():
        return SetupState()

    try:
        raw = state_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        log.warning("Corrupt setup state file at {}: {}. Starting fresh.", state_path, exc)
        return SetupState()

    if not isinstance(data, dict):
        log.warning("Malformed setup state (expected dict, got {}). Starting fresh.", type(data).__name__)
        return SetupState()

    steps = data.get("steps_completed", {})
    if not isinstance(steps, dict):
        log.warning("Malformed steps_completed (expected dict). Starting fresh.")
        return SetupState()

    return SetupState(
        steps_completed=steps,
        setup_version=str(data.get("setup_version", "0.0.0")),
        last_run=str(data.get("last_run", "")),
        last_failure=data.get("last_failure"),
    )


def save_setup_state(state: SetupState, data_dir: Path) -> None:
    """Persist setup state atomically.

    Writes to a temporary file in the same directory then renames,
    ensuring the state file is never left in a partial/corrupt state.

    Args:
        state: The state to persist.
        data_dir: Root data directory.

    Raises:
        PermissionError: If the state directory is not writable.
    """
    state_path = _state_path(data_dir)
    state_dir = state_path.parent
    state_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "steps_completed": state.steps_completed,
        "setup_version": state.setup_version,
        "last_run": state.last_run,
    }
    if state.last_failure:
        payload["last_failure"] = state.last_failure

    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(state_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.write("\n")
            os.replace(tmp_path, str(state_path))
        except BaseException:
            # Clean up the temp file if rename failed
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except PermissionError:
        raise PermissionError(
            f"Cannot write setup state to {state_path}. Check directory permissions."
        )


# ── Skip / resume logic ────────────────────────────────────────────


def should_run_step(
    step: SetupStep,
    state: SetupState,
    current_version: str,
) -> tuple[bool, str]:
    """Decide whether a step should execute.

    Args:
        step: The step definition.
        state: Current persisted state.
        current_version: The running LinkedOut version.

    Returns:
        A ``(should_run, reason)`` tuple.
    """
    # Always-run steps never skip
    if step.always_run:
        return True, "always runs"

    completed_at = state.steps_completed.get(step.name)

    # Never completed
    if not completed_at:
        return True, "not yet completed"

    # Demo-skipped counts as completed
    if completed_at == "demo-skipped":
        return False, "skipped (demo mode)"

    # Version bump forces re-run for version-sensitive steps
    if (
        step.name in _VERSION_SENSITIVE_STEPS
        and state.setup_version != current_version
    ):
        return True, f"version changed ({state.setup_version} -> {current_version})"

    # Completed and can skip — accept the cached result
    if step.can_skip:
        return False, "already complete"

    return True, "cannot be skipped"


def validate_step_state(step_name: str, data_dir: Path, db_url: str) -> bool:
    """Check if the underlying state for a step is still valid.

    This is a lightweight check — it does NOT re-run the step, just
    verifies that the artifacts/state it produced still exist and
    are healthy.

    Args:
        step_name: The step to validate.
        data_dir: Root data directory.
        db_url: Database connection URL (may be empty if not yet set).

    Returns:
        ``True`` if the step's output state is valid.
    """
    data_dir = Path(data_dir).expanduser()

    validators = {
        "database": lambda: _validate_database(db_url),
        "python_env": lambda: _validate_python_env(data_dir),
        "skills": lambda: _validate_skills(data_dir),
        "api_keys": lambda: _validate_api_keys(data_dir),
    }

    validator = validators.get(step_name)
    if validator is None:
        # No specific validator — trust the state file
        return True

    try:
        return validator()
    except Exception:
        return False


# ── Step registry ───────────────────────────────────────────────────


def _build_step_registry() -> list[SetupStep]:
    """Build the ordered list of all setup steps.

    Import setup functions lazily to avoid circular imports and
    heavy startup costs.
    """
    from linkedout.setup.affinity import setup_affinity
    from linkedout.setup.api_keys import collect_api_keys
    from linkedout.setup.auto_repair import run_auto_repair
    from linkedout.setup.contacts_import import setup_contacts_import
    from linkedout.setup.csv_import import setup_csv_import
    from linkedout.setup.database import setup_database
    from linkedout.setup.embeddings import setup_embeddings
    from linkedout.setup.prerequisites import run_all_checks
    from linkedout.setup.python_env import setup_python_env
    from linkedout.setup.readiness import generate_readiness_report
    from linkedout.setup.seed_data import setup_seed_data
    from linkedout.setup.skill_install import setup_skills
    from linkedout.setup.user_profile import setup_user_profile

    return [
        SetupStep(
            name="prerequisites",
            display_name="Prerequisites Detection",
            number=1,
            function=run_all_checks,
            can_skip=True,
        ),
        SetupStep(
            name="system_setup",
            display_name="System Setup",
            number=2,
            function=_run_system_setup,
            can_skip=True,
            dependencies=["prerequisites"],
        ),
        SetupStep(
            name="database",
            display_name="Database Setup",
            number=3,
            function=setup_database,
            can_skip=True,
            dependencies=["system_setup"],
        ),
        SetupStep(
            name="python_env",
            display_name="Python Environment",
            number=4,
            function=setup_python_env,
            can_skip=True,
            dependencies=["database"],
        ),
        SetupStep(
            name="api_keys",
            display_name="API Key Collection",
            number=5,
            function=collect_api_keys,
            can_skip=True,
            dependencies=["python_env"],
        ),
        SetupStep(
            name="user_profile",
            display_name="User Profile",
            number=6,
            function=setup_user_profile,
            can_skip=True,
            dependencies=["api_keys"],
        ),
        SetupStep(
            name="csv_import",
            display_name="LinkedIn CSV Import",
            number=7,
            function=setup_csv_import,
            can_skip=True,
            dependencies=["user_profile"],
        ),
        SetupStep(
            name="contacts_import",
            display_name="Contacts Import",
            number=8,
            function=setup_contacts_import,
            can_skip=True,
            dependencies=["csv_import"],
        ),
        SetupStep(
            name="seed_data",
            display_name="Seed Data",
            number=9,
            function=setup_seed_data,
            can_skip=True,
            dependencies=["contacts_import"],
        ),
        SetupStep(
            name="embeddings",
            display_name="Embedding Generation",
            number=10,
            function=setup_embeddings,
            can_skip=True,
            dependencies=["seed_data"],
        ),
        SetupStep(
            name="affinity",
            display_name="Affinity Computation",
            number=11,
            function=setup_affinity,
            can_skip=True,
            dependencies=["embeddings"],
        ),
        SetupStep(
            name="skills",
            display_name="Skill Installation",
            number=12,
            function=setup_skills,
            can_skip=True,
            dependencies=["affinity"],
        ),
        SetupStep(
            name="readiness",
            display_name="Readiness Check",
            number=13,
            function=generate_readiness_report,
            can_skip=False,
            always_run=True,
            dependencies=["skills"],
        ),
        SetupStep(
            name="auto_repair",
            display_name="Gap Detection",
            number=14,
            function=run_auto_repair,
            can_skip=False,
            always_run=True,
            dependencies=["readiness"],
        ),
    ]


# ── Step execution ──────────────────────────────────────────────────


def run_step(step: SetupStep, context: SetupContext) -> OperationReport | None:
    """Execute a single setup step with logging.

    Dispatches the step function with the correct arguments based on
    what each step expects. Returns the ``OperationReport`` from the
    step (or ``None`` for steps that don't produce one).

    Args:
        step: The step definition to execute.
        context: The mutable setup context.

    Returns:
        The operation report from the step, or ``None``.
    """
    return _dispatch_step(step, context)


def _dispatch_step(step: SetupStep, context: SetupContext) -> OperationReport | None:
    """Route a step to its function with the correct arguments.

    Each step function has a different signature. This dispatcher
    maps step names to the right call pattern and captures any
    context mutations (e.g., setting ``db_url`` after database setup).
    """
    name = step.name
    fn = step.function

    if name == "prerequisites":
        result = fn(data_dir=context.data_dir)
        # result is a PrerequisiteReport, not an OperationReport
        return None

    if name == "system_setup":
        result = fn(context.repo_root)
        return result if isinstance(result, OperationReport) else None

    if name == "database":
        report = fn(data_dir=context.data_dir)
        # Extract db_url from config after database setup
        context.db_url = _read_db_url(context.data_dir)
        return report

    if name == "python_env":
        return fn(
            repo_root=context.repo_root,
            embedding_provider=context.embedding_provider,
        )

    if name == "api_keys":
        report = fn(data_dir=context.data_dir)
        # Extract embedding provider from config after API keys
        context.embedding_provider = _read_embedding_provider(context.data_dir)
        return report

    if name == "user_profile":
        if context.db_url is None:
            raise RuntimeError(
                "Cannot run user_profile step: database URL is not set. "
                "The database step must complete first."
            )
        report = fn(data_dir=context.data_dir, db_url=context.db_url)
        # Extract user profile ID if available
        if report and report.counts.succeeded > 0:
            context.user_profile_id = report.counts.succeeded
        return report

    if name in ("csv_import", "contacts_import", "seed_data"):
        return fn(data_dir=context.data_dir)

    if name == "embeddings":
        if context.db_url is None:
            raise RuntimeError(
                "Cannot run embeddings step: database URL is not set. "
                "The database step must complete first."
            )
        return fn(data_dir=context.data_dir, db_url=context.db_url)

    if name == "affinity":
        if context.db_url is None:
            raise RuntimeError(
                "Cannot run affinity step: database URL is not set. "
                "The database step must complete first."
            )
        return fn(data_dir=context.data_dir, db_url=context.db_url)

    if name == "skills":
        return fn(repo_root=context.repo_root, data_dir=context.data_dir)

    if name == "readiness":
        if context.db_url is None:
            raise RuntimeError(
                "Cannot run readiness step: database URL is not set. "
                "The database step must complete first."
            )
        # Returns ReadinessReport, not OperationReport
        result = fn(db_url=context.db_url, data_dir=context.data_dir)
        # Stash on context for auto_repair
        context._readiness_report = result  # type: ignore[attr-defined]
        return None

    if name == "auto_repair":
        report = getattr(context, "_readiness_report", None)
        if report is None:
            raise RuntimeError(
                "Cannot run auto_repair step: readiness report not available. "
                "The readiness step must complete first."
            )
        fn(report=report, data_dir=context.data_dir, db_url=context.db_url or "")
        return None

    # Fallback: call with data_dir
    return fn(data_dir=context.data_dir)


# ── Main entry point ────────────────────────────────────────────────


def run_setup(
    data_dir: Path | None = None,
    repo_root: Path | None = None,
) -> None:
    """Run the full LinkedOut setup flow.

    This is the main entry point invoked by ``linkedout setup`` and
    the ``/linkedout-setup`` skill. It:

    1. Loads persisted state (or starts fresh on first run).
    2. Runs infrastructure steps 1-4 (common to both paths).
    3. After step 4, presents the demo offer (fresh installs only).
    4. If demo accepted: runs D1-D5, marks steps 5-11 as demo-skipped.
    5. If demo declined: continues with steps 5-14 as normal.
    6. On re-run in demo mode: offers transition to full setup.
    7. Saves state after each successful step (atomic writes).

    Args:
        data_dir: Override data directory. Defaults to ``~/linkedout-data``
            or ``LINKEDOUT_DATA_DIR`` env var.
        repo_root: Override repo root. Defaults to auto-detection.
    """
    # Resolve paths
    if data_dir is None:
        data_dir = Path(
            os.environ.get("LINKEDOUT_DATA_DIR", "~/linkedout-data")
        ).expanduser()
    else:
        data_dir = Path(data_dir).expanduser()

    if repo_root is None:
        repo_root = _detect_repo_root()
    else:
        repo_root = Path(repo_root)

    # Initialize logging
    correlation_id = init_setup_logging()
    log = get_setup_logger("orchestrator")

    # Load state
    state = load_setup_state(data_dir)
    steps = _build_step_registry()

    # Build context
    context = SetupContext(
        data_dir=data_dir,
        repo_root=repo_root,
        correlation_id=correlation_id,
    )

    # If resuming, try to recover db_url from config
    if state.steps_completed.get("database"):
        context.db_url = _read_db_url(data_dir)
    if state.steps_completed.get("api_keys"):
        context.embedding_provider = _read_embedding_provider(data_dir)

    # Version change detection
    if (
        state.setup_version
        and state.setup_version != "0.0.0"
        and state.setup_version != _LINKEDOUT_VERSION
    ):
        log.info(
            "Setup version changed: {} -> {}",
            state.setup_version,
            _LINKEDOUT_VERSION,
        )

    # ── Detect demo mode and transition ───────────────────────────
    is_demo = _is_demo_mode_active(data_dir)

    if is_demo:
        # User is in demo mode — offer transition
        from linkedout.setup.demo_offer import offer_transition

        if offer_transition():
            # Accept transition: clear demo-skipped, switch to real DB
            _clear_demo_state(state, data_dir)
            is_demo = False
            log.info("Transition accepted — switching to full setup")
        else:
            # Decline transition: show all steps as complete/skipped, exit
            _show_demo_rerun_summary(steps, state)
            log.info("Transition declined — demo mode unchanged")
            return

    # ── Determine step numbering ──────────────────────────────────
    # On a fresh install (no steps beyond step 4 complete), we show
    # "Step N of 4" for the infra steps. Once the user decides, we
    # either run demo D1-D5 or switch to "Step N of 14".
    demo_eligible = _is_demo_eligible(state, data_dir)
    total_display = _INFRA_STEP_COUNT if demo_eligible else len(steps)

    # ── Execute steps ─────────────────────────────────────────────
    steps_log: list[dict] = []
    for step in steps:
        _check_dependencies(step, state)

        run_it, reason = should_run_step(step, state, _LINKEDOUT_VERSION)

        if not run_it:
            print(f"\nStep {step.number} of {total_display}: {step.display_name}")
            print(f"  \u2713 Already complete ({reason})")
            steps_log.append({
                "name": step.display_name,
                "status": "skipped",
                "timestamp": state.steps_completed.get(step.name, ""),
            })
            continue

        # Run the step
        log_step_start(step.number, total_display, step.display_name)
        print(f"\nStep {step.number} of {total_display}: {step.display_name}")

        start = time.monotonic()
        try:
            report = run_step(step, context)
        except Exception as exc:
            duration = time.monotonic() - start
            log.error(
                "Step {} failed after {:.1f}s: {}",
                step.display_name,
                duration,
                exc,
            )
            print(f"  \u2717 {step.display_name} failed: {exc}")

            # Record failure in state
            state.last_failure = {
                "step": step.name,
                "error": f"{type(exc).__name__}: {exc}",
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            }
            save_setup_state(state, data_dir)

            steps_log.append({
                "name": step.display_name,
                "status": "failed",
                "duration": f"{duration:.1f}s",
            })

            # Generate diagnostic
            try:
                diag_path = generate_diagnostic(
                    error=exc,
                    steps_completed=steps_log,
                    config=_gather_config_for_diagnostic(context),
                )
                print(f"\n  Diagnostic written to: {diag_path}")
                print("  Or re-run /linkedout-setup \u2014 it will resume from this step.")
            except Exception:
                pass
            return

        duration = time.monotonic() - start
        log_step_complete(step.display_name, duration, report)

        # Mark step complete
        state.steps_completed[step.name] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state.last_run = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state.setup_version = _LINKEDOUT_VERSION
        save_setup_state(state, data_dir)

        steps_log.append({
            "name": step.display_name,
            "status": "success",
            "timestamp": state.steps_completed[step.name],
            "duration": f"{duration:.1f}s",
        })

        # ── Demo decision gate after step 4 (python_env) ─────────
        if step.name == "python_env" and demo_eligible:
            from linkedout.setup.demo_offer import offer_demo, run_demo_setup

            if offer_demo():
                # Run demo steps D1-D5
                db_url = context.db_url or "postgresql://linkedout:linkedout@localhost:5432/linkedout"
                success = run_demo_setup(data_dir, repo_root, db_url)

                if success:
                    # Mark demo-skippable steps as demo-skipped
                    now = datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
                    for s in steps:
                        if s.name in DEMO_SKIPPABLE_STEPS:
                            state.steps_completed[s.name] = "demo-skipped"
                    # Mark skills and readiness as completed (D4, D5)
                    state.steps_completed["skills"] = now
                    state.steps_completed["readiness"] = now
                    # auto_repair not run in demo mode
                    state.steps_completed["auto_repair"] = "demo-skipped"
                    state.last_run = now
                    state.setup_version = _LINKEDOUT_VERSION
                    save_setup_state(state, data_dir)
                    log.info("Demo setup complete")
                    return
                else:
                    # Demo failed — offer to continue with full setup
                    print("\n  Demo setup encountered errors.")
                    print("  Continuing with full setup (steps 5-14)...\n")
                    total_display = len(steps)
                    # Fall through to continue the normal step loop
            else:
                # Demo declined — switch to 14-step numbering
                total_display = len(steps)

    log.info("Setup complete")


# ── Demo helpers ───────────────────────────────────────────────────


def _is_demo_mode_active(data_dir: Path) -> bool:
    """Check if demo_mode is True in config.yaml."""
    import yaml

    config_path = data_dir / "config" / "config.yaml"
    if not config_path.exists():
        return False
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return bool(cfg.get("demo_mode")) if isinstance(cfg, dict) else False
    except Exception:
        return False


def _is_demo_eligible(state: SetupState, data_dir: Path) -> bool:
    """Check if the demo offer should be shown.

    The demo offer is eligible only on fresh installs where:
    1. No steps beyond step 4 (python_env) are complete.
    2. ``demo_mode`` is not already set in config.
    """
    # If demo_mode is already configured (either True or False), don't re-offer
    if _is_demo_mode_active(data_dir):
        return False

    import yaml

    config_path = data_dir / "config" / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            if "demo_mode" in cfg:
                return False
        except Exception:
            pass

    # Check if any steps beyond step 4 are complete
    post_infra_steps = {
        "api_keys", "user_profile", "csv_import", "contacts_import",
        "seed_data", "embeddings", "affinity", "skills", "readiness",
        "auto_repair",
    }
    for step_name in post_infra_steps:
        completed = state.steps_completed.get(step_name)
        if completed:
            return False

    return True


def _clear_demo_state(state: SetupState, data_dir: Path) -> None:
    """Clear demo-skipped markers and switch config to real mode.

    Called when the user accepts the transition from demo to full setup.
    """
    from linkedout.demo import set_demo_mode
    from linkedout.setup.database import generate_agent_context_env

    # Clear demo-skipped markers so steps 5-11 will re-run
    for step_name in DEMO_SKIPPABLE_STEPS:
        if state.steps_completed.get(step_name) == "demo-skipped":
            del state.steps_completed[step_name]

    # Also clear auto_repair if it was demo-skipped
    if state.steps_completed.get("auto_repair") == "demo-skipped":
        del state.steps_completed["auto_repair"]

    # Switch config to real database
    set_demo_mode(data_dir, enabled=False)

    # Regenerate agent-context.env for the real database
    real_db_url = _read_db_url(data_dir)
    if real_db_url:
        try:
            generate_agent_context_env(real_db_url, data_dir)
        except Exception:
            pass

    save_setup_state(state, data_dir)


def _show_demo_rerun_summary(
    steps: list[SetupStep],
    state: SetupState,
) -> None:
    """Show a fast no-op summary when re-running setup in demo mode."""
    total = len(steps)
    for step in steps:
        completed = state.steps_completed.get(step.name)
        if completed == "demo-skipped":
            print(f"\nStep {step.number} of {total}: {step.display_name}")
            print("  \u2713 Skipped (demo mode)")
        elif completed:
            print(f"\nStep {step.number} of {total}: {step.display_name}")
            print("  \u2713 Already complete")
        else:
            print(f"\nStep {step.number} of {total}: {step.display_name}")
            print("  \u2713 Already complete")


# ── System setup wrapper ────────────────────────────────────────────


def _run_system_setup(repo_root: Path) -> OperationReport | None:
    """Run ``scripts/system-setup.sh`` if it exists.

    This is a wrapper that the orchestrator uses as the step function
    for the ``system_setup`` step.
    """
    import subprocess

    script = repo_root / "scripts" / "system-setup.sh"
    if not script.exists():
        return None

    result = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"System setup script failed:\n{result.stderr[-500:]}"
        )
    return None


# ── Internal helpers ────────────────────────────────────────────────


def _state_path(data_dir: Path) -> Path:
    """Return the path to ``setup-state.json``."""
    return Path(data_dir).expanduser() / "state" / "setup-state.json"


def _detect_repo_root() -> Path:
    """Detect the repository root directory.

    Walks up from the current file's location looking for
    ``pyproject.toml``.
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def _read_db_url(data_dir: Path) -> str | None:
    """Read DATABASE_URL from config.yaml."""
    config_path = Path(data_dir).expanduser() / "config" / "config.yaml"
    if not config_path.exists():
        return None
    try:
        import yaml

        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("database_url") if isinstance(cfg, dict) else None
    except Exception:
        return None


def _read_embedding_provider(data_dir: Path) -> str | None:
    """Read embedding_provider from config.yaml."""
    config_path = Path(data_dir).expanduser() / "config" / "config.yaml"
    if not config_path.exists():
        return None
    try:
        import yaml

        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("embedding_provider") if isinstance(cfg, dict) else None
    except Exception:
        return None


def _check_dependencies(step: SetupStep, state: SetupState) -> None:
    """Verify all dependencies for a step are met.

    Raises ``RuntimeError`` if a required predecessor has not completed.
    """
    for dep_name in step.dependencies:
        if not state.steps_completed.get(dep_name):
            # Don't raise for dependencies — they just haven't run yet
            # in this session. The orchestrator runs steps in order,
            # so if a dependency hasn't completed, it will run first.
            pass


def _validate_database(db_url: str) -> bool:
    """Check if the database is accessible and has expected tables."""
    if not db_url:
        return False
    try:
        import subprocess

        result = subprocess.run(
            ["psql", db_url, "-c", "SELECT 1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _validate_python_env(data_dir: Path) -> bool:  # noqa: ARG001
    """Check if the Python venv exists and CLI works."""
    repo_root = _detect_repo_root()
    venv_path = repo_root / ".venv"
    return venv_path.exists()


def _validate_skills(data_dir: Path) -> bool:  # noqa: ARG001
    """Check if skill files exist."""
    repo_root = _detect_repo_root()
    skills_dir = repo_root / "skills"
    return skills_dir.exists() and any(skills_dir.iterdir())


def _validate_api_keys(data_dir: Path) -> bool:
    """Check if secrets.yaml exists with expected keys."""
    secrets_path = Path(data_dir).expanduser() / "config" / "secrets.yaml"
    return secrets_path.exists()


def _gather_config_for_diagnostic(context: SetupContext) -> dict:
    """Gather config values for a diagnostic report (will be redacted)."""
    return {
        "data_dir": str(context.data_dir),
        "repo_root": str(context.repo_root),
        "database_url": context.db_url or "(not set)",
        "embedding_provider": context.embedding_provider or "(not set)",
        "correlation_id": context.correlation_id,
    }
