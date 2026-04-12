# SPDX-License-Identifier: Apache-2.0
"""Tests for the setup orchestrator module.

Covers state file loading/writing, skip/resume logic, version-aware
re-runs, partial failure recovery, step ordering, performance, and
step state validation.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linkedout.setup.orchestrator import (
    SetupContext,
    SetupState,
    SetupStep,
    _LINKEDOUT_VERSION,
    _VERSION_SENSITIVE_STEPS,
    _build_step_registry,
    _dispatch_step,
    load_setup_state,
    run_setup,
    save_setup_state,
    should_run_step,
    validate_step_state,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory with state subdir."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return tmp_path


@pytest.fixture
def sample_state():
    """Return a sample SetupState with a few completed steps."""
    return SetupState(
        steps_completed={
            "prerequisites": "2026-04-07T14:20:00Z",
            "system_setup": "2026-04-07T14:21:00Z",
            "database": "2026-04-07T14:22:00Z",
        },
        setup_version=_LINKEDOUT_VERSION,
        last_run="2026-04-07T14:22:00Z",
    )


@pytest.fixture
def dummy_step():
    """Return a simple SetupStep for testing."""
    return SetupStep(
        name="prerequisites",
        display_name="Prerequisites Detection",
        number=1,
        function=lambda **kwargs: None,
        can_skip=True,
    )


@pytest.fixture
def always_run_step():
    """Return a step that always runs."""
    return SetupStep(
        name="readiness",
        display_name="Readiness Check",
        number=13,
        function=lambda **kwargs: None,
        can_skip=False,
        always_run=True,
    )


def _write_state_file(data_dir: Path, content: str) -> Path:
    """Helper to write raw content to setup-state.json."""
    state_path = data_dir / "state" / "setup-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(content, encoding="utf-8")
    return state_path


# ══════════════════════════════════════════════════════════════════════
# TestLoadSetupState
# ══════════════════════════════════════════════════════════════════════


class TestLoadSetupState:
    """Tests for loading and parsing setup-state.json."""

    def test_missing_state_file_returns_empty(self, tmp_data_dir):
        """First install: no state file exists."""
        state = load_setup_state(tmp_data_dir)
        assert state.steps_completed == {}
        assert state.setup_version == "0.0.0"
        assert state.last_run == ""

    def test_valid_state_file_parses_correctly(self, tmp_data_dir):
        """Valid JSON with all expected fields."""
        payload = {
            "steps_completed": {
                "prerequisites": "2026-04-07T14:20:00Z",
                "database": "2026-04-07T14:22:00Z",
            },
            "setup_version": "0.1.0",
            "last_run": "2026-04-07T14:22:00Z",
        }
        _write_state_file(tmp_data_dir, json.dumps(payload))

        state = load_setup_state(tmp_data_dir)
        assert state.steps_completed["prerequisites"] == "2026-04-07T14:20:00Z"
        assert state.steps_completed["database"] == "2026-04-07T14:22:00Z"
        assert state.setup_version == "0.1.0"
        assert state.last_run == "2026-04-07T14:22:00Z"

    def test_corrupted_json_returns_empty(self, tmp_data_dir):
        """Truncated write or binary garbage."""
        _write_state_file(tmp_data_dir, '{"steps_completed": {')

        state = load_setup_state(tmp_data_dir)
        assert state.steps_completed == {}

    def test_binary_garbage_returns_empty(self, tmp_data_dir):
        """Binary data instead of JSON."""
        state_path = tmp_data_dir / "state" / "setup-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_bytes(b"\x00\x01\x02\xff\xfe")

        state = load_setup_state(tmp_data_dir)
        assert state.steps_completed == {}

    def test_malformed_steps_completed_is_list(self, tmp_data_dir):
        """steps_completed is a list instead of dict."""
        payload = {
            "steps_completed": ["prerequisites", "database"],
            "setup_version": "0.1.0",
        }
        _write_state_file(tmp_data_dir, json.dumps(payload))

        state = load_setup_state(tmp_data_dir)
        assert state.steps_completed == {}

    def test_unknown_fields_ignored(self, tmp_data_dir):
        """Forward compat: unknown fields don't break parsing."""
        payload = {
            "steps_completed": {"prerequisites": "2026-04-07T14:20:00Z"},
            "setup_version": "0.1.0",
            "last_run": "2026-04-07T14:20:00Z",
            "future_field": "some-value",
            "another_unknown": 42,
        }
        _write_state_file(tmp_data_dir, json.dumps(payload))

        state = load_setup_state(tmp_data_dir)
        assert state.steps_completed["prerequisites"] == "2026-04-07T14:20:00Z"
        assert state.setup_version == "0.1.0"

    def test_missing_setup_version_treated_as_zero(self, tmp_data_dir):
        """Missing setup_version -> forces re-run of version-sensitive steps."""
        payload = {
            "steps_completed": {"prerequisites": "2026-04-07T14:20:00Z"},
            "last_run": "2026-04-07T14:20:00Z",
        }
        _write_state_file(tmp_data_dir, json.dumps(payload))

        state = load_setup_state(tmp_data_dir)
        assert state.setup_version == "0.0.0"

    def test_not_a_dict_returns_empty(self, tmp_data_dir):
        """State file is valid JSON but not a dict (e.g., a list)."""
        _write_state_file(tmp_data_dir, '["not", "a", "dict"]')

        state = load_setup_state(tmp_data_dir)
        assert state.steps_completed == {}

    def test_state_with_last_failure(self, tmp_data_dir):
        """State file includes last_failure info."""
        payload = {
            "steps_completed": {"prerequisites": "2026-04-07T14:20:00Z"},
            "setup_version": "0.1.0",
            "last_run": "2026-04-07T14:20:00Z",
            "last_failure": {
                "step": "embeddings",
                "error": "openai.RateLimitError: 429",
                "timestamp": "2026-04-07T14:35:42Z",
            },
        }
        _write_state_file(tmp_data_dir, json.dumps(payload))

        state = load_setup_state(tmp_data_dir)
        assert state.last_failure is not None
        assert state.last_failure["step"] == "embeddings"


# ══════════════════════════════════════════════════════════════════════
# TestSaveSetupState
# ══════════════════════════════════════════════════════════════════════


class TestSaveSetupState:
    """Tests for atomic state file writing."""

    def test_roundtrip(self, tmp_data_dir):
        """Write and read back produce identical state."""
        state = SetupState(
            steps_completed={
                "prerequisites": "2026-04-07T14:20:00Z",
                "database": "2026-04-07T14:22:00Z",
            },
            setup_version="0.1.0",
            last_run="2026-04-07T14:22:00Z",
        )
        save_setup_state(state, tmp_data_dir)
        loaded = load_setup_state(tmp_data_dir)

        assert loaded.steps_completed == state.steps_completed
        assert loaded.setup_version == state.setup_version
        assert loaded.last_run == state.last_run

    def test_creates_state_directory(self, tmp_path):
        """State dir is created if it doesn't exist."""
        data_dir = tmp_path / "fresh"
        state = SetupState(steps_completed={"prerequisites": "2026-04-07T14:20:00Z"})

        save_setup_state(state, data_dir)
        assert (data_dir / "state" / "setup-state.json").exists()

    def test_atomic_write_no_temp_file_left(self, tmp_data_dir):
        """After a successful write, no .tmp files remain."""
        state = SetupState(steps_completed={"a": "2026-04-07T14:20:00Z"})
        save_setup_state(state, tmp_data_dir)

        state_dir = tmp_data_dir / "state"
        tmp_files = list(state_dir.glob("*.tmp"))
        assert tmp_files == []

    def test_data_dir_env_override(self, tmp_path):
        """LINKEDOUT_DATA_DIR env var override for state file path."""
        custom_dir = tmp_path / "custom-data"
        state = SetupState(steps_completed={"x": "2026-04-07T14:20:00Z"})

        save_setup_state(state, custom_dir)
        loaded = load_setup_state(custom_dir)
        assert loaded.steps_completed["x"] == "2026-04-07T14:20:00Z"

    def test_read_only_directory_raises_permission_error(self, tmp_data_dir):
        """Non-writable state dir raises PermissionError with message."""
        state_dir = tmp_data_dir / "state"
        state_dir.mkdir(exist_ok=True)
        state_dir.chmod(0o444)

        try:
            state = SetupState(steps_completed={"a": "ts"})
            with pytest.raises(PermissionError, match="Cannot write setup state"):
                save_setup_state(state, tmp_data_dir)
        finally:
            state_dir.chmod(0o755)

    def test_last_failure_persisted(self, tmp_data_dir):
        """last_failure field is written and read back."""
        state = SetupState(
            steps_completed={},
            last_failure={"step": "database", "error": "timeout", "timestamp": "ts"},
        )
        save_setup_state(state, tmp_data_dir)
        loaded = load_setup_state(tmp_data_dir)
        assert loaded.last_failure is not None
        assert loaded.last_failure["step"] == "database"

    def test_valid_json_output(self, tmp_data_dir):
        """Written file is valid JSON."""
        state = SetupState(
            steps_completed={"a": "ts", "b": "ts2"},
            setup_version="0.1.0",
        )
        save_setup_state(state, tmp_data_dir)

        raw = (tmp_data_dir / "state" / "setup-state.json").read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        assert "steps_completed" in parsed


# ══════════════════════════════════════════════════════════════════════
# TestShouldRunStep
# ══════════════════════════════════════════════════════════════════════


class TestShouldRunStep:
    """Tests for the skip/resume decision logic."""

    def test_uncompleted_step_runs(self, dummy_step):
        """Step not in state -> must run."""
        state = SetupState()
        should_run, reason = should_run_step(dummy_step, state, _LINKEDOUT_VERSION)
        assert should_run is True
        assert "not yet completed" in reason

    def test_completed_skippable_step_skips(self, dummy_step):
        """Completed + can_skip + same version -> skip."""
        state = SetupState(
            steps_completed={"prerequisites": "2026-04-07T14:20:00Z"},
            setup_version=_LINKEDOUT_VERSION,
        )
        should_run, reason = should_run_step(dummy_step, state, _LINKEDOUT_VERSION)
        assert should_run is False
        assert "already complete" in reason

    def test_always_run_step_always_runs(self, always_run_step):
        """always_run=True -> runs even if completed."""
        state = SetupState(
            steps_completed={"readiness": "2026-04-07T14:30:00Z"},
            setup_version=_LINKEDOUT_VERSION,
        )
        should_run, reason = should_run_step(always_run_step, state, _LINKEDOUT_VERSION)
        assert should_run is True
        assert "always runs" in reason

    def test_always_run_step_runs_when_not_completed(self, always_run_step):
        """always_run=True -> runs even if never completed."""
        state = SetupState()
        should_run, reason = should_run_step(always_run_step, state, _LINKEDOUT_VERSION)
        assert should_run is True

    def test_step_with_skipped_value_skips(self, dummy_step):
        """User-declined step (value "skipped") is treated as complete."""
        state = SetupState(
            steps_completed={"prerequisites": "skipped"},
            setup_version=_LINKEDOUT_VERSION,
        )
        should_run, reason = should_run_step(dummy_step, state, _LINKEDOUT_VERSION)
        assert should_run is False


# ══════════════════════════════════════════════════════════════════════
# TestVersionAwareReRuns
# ══════════════════════════════════════════════════════════════════════


class TestVersionAwareReRuns:
    """Tests for version-aware step re-execution."""

    def test_same_version_uses_normal_skip(self):
        """No version change -> normal skip logic."""
        step = SetupStep(
            name="database",
            display_name="Database Setup",
            number=3,
            function=lambda **kw: None,
            can_skip=True,
        )
        state = SetupState(
            steps_completed={"database": "2026-04-07T14:22:00Z"},
            setup_version="0.1.0",
        )
        should_run, reason = should_run_step(step, state, "0.1.0")
        assert should_run is False

    def test_version_change_forces_rerun_of_database(self):
        """Version bump forces re-run of database (new migrations)."""
        step = SetupStep(
            name="database",
            display_name="Database Setup",
            number=3,
            function=lambda **kw: None,
            can_skip=True,
        )
        state = SetupState(
            steps_completed={"database": "2026-04-07T14:22:00Z"},
            setup_version="0.1.0",
        )
        should_run, reason = should_run_step(step, state, "0.2.0")
        assert should_run is True
        assert "version changed" in reason

    def test_version_change_forces_rerun_of_python_env(self):
        """Version bump forces re-run of python_env (new deps)."""
        step = SetupStep(
            name="python_env",
            display_name="Python Environment",
            number=4,
            function=lambda **kw: None,
            can_skip=True,
        )
        state = SetupState(
            steps_completed={"python_env": "2026-04-07T14:22:00Z"},
            setup_version="0.1.0",
        )
        should_run, reason = should_run_step(step, state, "0.2.0")
        assert should_run is True
        assert "version changed" in reason

    def test_version_change_forces_rerun_of_skills(self):
        """Version bump forces re-run of skills (updated skills)."""
        step = SetupStep(
            name="skills",
            display_name="Skill Installation",
            number=12,
            function=lambda **kw: None,
            can_skip=True,
        )
        state = SetupState(
            steps_completed={"skills": "2026-04-07T14:22:00Z"},
            setup_version="0.1.0",
        )
        should_run, reason = should_run_step(step, state, "0.2.0")
        assert should_run is True

    def test_version_change_does_not_force_rerun_of_api_keys(self):
        """Version bump does NOT force re-run of user data steps."""
        for step_name in ("api_keys", "user_profile", "csv_import"):
            step = SetupStep(
                name=step_name,
                display_name=step_name,
                number=5,
                function=lambda **kw: None,
                can_skip=True,
            )
            state = SetupState(
                steps_completed={step_name: "2026-04-07T14:22:00Z"},
                setup_version="0.1.0",
            )
            should_run, reason = should_run_step(step, state, "0.2.0")
            assert should_run is False, f"{step_name} should not re-run on version change"

    def test_missing_version_treated_as_zero(self):
        """Missing setup_version (0.0.0) forces all version-sensitive steps."""
        for step_name in _VERSION_SENSITIVE_STEPS:
            step = SetupStep(
                name=step_name,
                display_name=step_name,
                number=1,
                function=lambda **kw: None,
                can_skip=True,
            )
            state = SetupState(
                steps_completed={step_name: "2026-04-07T14:22:00Z"},
                setup_version="0.0.0",
            )
            should_run, reason = should_run_step(step, state, _LINKEDOUT_VERSION)
            assert should_run is True, f"{step_name} should re-run when version is 0.0.0"

    def test_version_sensitive_steps_are_correct(self):
        """The set of version-sensitive steps matches the spec."""
        assert _VERSION_SENSITIVE_STEPS == {"database", "python_env", "skills"}


# ══════════════════════════════════════════════════════════════════════
# TestPartialFailureRecovery
# ══════════════════════════════════════════════════════════════════════


class TestPartialFailureRecovery:
    """Tests for state consistency after partial failures."""

    def test_step6_fails_leaves_steps1to5_complete(self, tmp_data_dir):
        """Steps 1-5 remain marked complete after step 6 failure."""
        state = SetupState(
            steps_completed={
                "prerequisites": "2026-04-07T14:20:00Z",
                "system_setup": "2026-04-07T14:21:00Z",
                "database": "2026-04-07T14:22:00Z",
                "python_env": "2026-04-07T14:23:00Z",
                "api_keys": "2026-04-07T14:24:00Z",
            },
            setup_version=_LINKEDOUT_VERSION,
        )

        # Simulate step 6 failure: state is saved without user_profile
        state.last_failure = {
            "step": "user_profile",
            "error": "ConnectionError: database unavailable",
            "timestamp": "2026-04-07T14:25:00Z",
        }
        save_setup_state(state, tmp_data_dir)

        loaded = load_setup_state(tmp_data_dir)
        assert "prerequisites" in loaded.steps_completed
        assert "system_setup" in loaded.steps_completed
        assert "database" in loaded.steps_completed
        assert "python_env" in loaded.steps_completed
        assert "api_keys" in loaded.steps_completed
        assert "user_profile" not in loaded.steps_completed

    def test_resume_skips_completed_retries_failed(self, tmp_data_dir):
        """After failure, re-run skips 1-5 and retries step 6."""
        state = SetupState(
            steps_completed={
                "prerequisites": "2026-04-07T14:20:00Z",
                "system_setup": "2026-04-07T14:21:00Z",
                "database": "2026-04-07T14:22:00Z",
                "python_env": "2026-04-07T14:23:00Z",
                "api_keys": "2026-04-07T14:24:00Z",
            },
            setup_version=_LINKEDOUT_VERSION,
        )

        completed_step = SetupStep(
            name="prerequisites",
            display_name="Prerequisites",
            number=1,
            function=lambda **kw: None,
            can_skip=True,
        )
        failed_step = SetupStep(
            name="user_profile",
            display_name="User Profile",
            number=6,
            function=lambda **kw: None,
            can_skip=True,
        )

        should_run_c, _ = should_run_step(completed_step, state, _LINKEDOUT_VERSION)
        should_run_f, reason = should_run_step(failed_step, state, _LINKEDOUT_VERSION)

        assert should_run_c is False
        assert should_run_f is True
        assert "not yet completed" in reason

    def test_failure_does_not_corrupt_completed_entries(self, tmp_data_dir):
        """Multiple saves after failure keep completed entries intact."""
        state = SetupState(
            steps_completed={"prerequisites": "2026-04-07T14:20:00Z"},
            setup_version=_LINKEDOUT_VERSION,
        )

        # First save
        save_setup_state(state, tmp_data_dir)

        # Simulate failure and save
        state.last_failure = {"step": "database", "error": "err", "timestamp": "ts"}
        save_setup_state(state, tmp_data_dir)

        # Another save
        save_setup_state(state, tmp_data_dir)

        loaded = load_setup_state(tmp_data_dir)
        assert loaded.steps_completed["prerequisites"] == "2026-04-07T14:20:00Z"

    def test_multiple_failures_no_duplicate_entries(self, tmp_data_dir):
        """Repeated failures on same step don't create duplicates."""
        state = SetupState(
            steps_completed={"prerequisites": "2026-04-07T14:20:00Z"},
            setup_version=_LINKEDOUT_VERSION,
        )

        for i in range(5):
            state.last_failure = {
                "step": "database",
                "error": f"error {i}",
                "timestamp": f"ts{i}",
            }
            save_setup_state(state, tmp_data_dir)

        loaded = load_setup_state(tmp_data_dir)
        assert len(loaded.steps_completed) == 1  # Only prerequisites
        assert loaded.last_failure is not None
        assert loaded.last_failure["error"] == "error 4"

    def test_step_fails_then_succeeds_marks_complete(self, tmp_data_dir):
        """After fixing an issue, re-running marks the step complete."""
        state = SetupState(
            steps_completed={"prerequisites": "2026-04-07T14:20:00Z"},
            setup_version=_LINKEDOUT_VERSION,
        )
        save_setup_state(state, tmp_data_dir)

        # Step now succeeds
        state.steps_completed["database"] = "2026-04-07T14:30:00Z"
        state.last_failure = None
        save_setup_state(state, tmp_data_dir)

        loaded = load_setup_state(tmp_data_dir)
        assert "database" in loaded.steps_completed
        assert loaded.last_failure is None


# ══════════════════════════════════════════════════════════════════════
# TestStepOrdering
# ══════════════════════════════════════════════════════════════════════


class TestStepOrdering:
    """Tests for step ordering and context mutation."""

    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="corr-id")
    def test_step_registry_has_15_steps(self, mock_logging):
        """All 15 setup steps are registered."""
        steps = _build_step_registry()
        assert len(steps) == 15

    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="corr-id")
    def test_steps_numbered_1_to_15(self, mock_logging):
        """Steps are numbered sequentially 1-15."""
        steps = _build_step_registry()
        numbers = [s.number for s in steps]
        assert numbers == list(range(1, 16))

    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="corr-id")
    def test_step_names_match_spec(self, mock_logging):
        """Step names match the specification."""
        steps = _build_step_registry()
        names = [s.name for s in steps]
        expected = [
            "prerequisites",
            "system_setup",
            "database",
            "python_env",
            "api_keys",
            "user_profile",
            "csv_import",
            "contacts_import",
            "enrichment",
            "seed_data",
            "embeddings",
            "affinity",
            "skills",
            "readiness",
            "auto_repair",
        ]
        assert names == expected

    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="corr-id")
    def test_readiness_and_auto_repair_always_run(self, mock_logging):
        """Steps 14 and 15 have always_run=True."""
        steps = _build_step_registry()
        readiness = steps[13]
        auto_repair = steps[14]
        assert readiness.always_run is True
        assert auto_repair.always_run is True

    def test_context_db_url_propagation(self):
        """SetupContext.db_url set by one step is visible to later steps."""
        context = SetupContext(
            data_dir=Path("/tmp/test"),
            repo_root=Path("/tmp/repo"),
        )
        assert context.db_url is None

        context.db_url = "postgresql://user:pass@localhost/linkedout"
        assert context.db_url == "postgresql://user:pass@localhost/linkedout"

    def test_context_embedding_provider_propagation(self):
        """SetupContext.embedding_provider set by api_keys is available later."""
        context = SetupContext(
            data_dir=Path("/tmp/test"),
            repo_root=Path("/tmp/repo"),
        )
        assert context.embedding_provider is None

        context.embedding_provider = "openai"
        assert context.embedding_provider == "openai"

    def test_step_needing_db_url_when_none_raises(self):
        """Steps that need db_url raise RuntimeError when it's None."""
        from linkedout.setup.orchestrator import _dispatch_step

        mock_fn = MagicMock()
        step = SetupStep(
            name="user_profile",
            display_name="User Profile",
            number=6,
            function=mock_fn,
        )
        context = SetupContext(
            data_dir=Path("/tmp/test"),
            repo_root=Path("/tmp/repo"),
            db_url=None,
        )

        with pytest.raises(RuntimeError, match="database URL is not set"):
            _dispatch_step(step, context)

    def test_embeddings_step_needs_db_url(self):
        """Embeddings step raises RuntimeError when db_url is None."""
        from linkedout.setup.orchestrator import _dispatch_step

        step = SetupStep(
            name="embeddings",
            display_name="Embedding Generation",
            number=10,
            function=MagicMock(),
        )
        context = SetupContext(
            data_dir=Path("/tmp/test"),
            repo_root=Path("/tmp/repo"),
            db_url=None,
        )

        with pytest.raises(RuntimeError, match="database URL is not set"):
            _dispatch_step(step, context)

    def test_affinity_step_needs_db_url(self):
        """Affinity step raises RuntimeError when db_url is None."""
        from linkedout.setup.orchestrator import _dispatch_step

        step = SetupStep(
            name="affinity",
            display_name="Affinity Computation",
            number=11,
            function=MagicMock(),
        )
        context = SetupContext(
            data_dir=Path("/tmp/test"),
            repo_root=Path("/tmp/repo"),
            db_url=None,
        )

        with pytest.raises(RuntimeError, match="database URL is not set"):
            _dispatch_step(step, context)


# ══════════════════════════════════════════════════════════════════════
# TestPerformance
# ══════════════════════════════════════════════════════════════════════


class TestPerformance:
    """Tests for re-run performance on fully complete setup."""

    def test_should_run_step_fast_for_skippable(self, dummy_step):
        """should_run_step for a completed skippable step is fast (no I/O)."""
        state = SetupState(
            steps_completed={"prerequisites": "2026-04-07T14:20:00Z"},
            setup_version=_LINKEDOUT_VERSION,
        )

        start = time.monotonic()
        for _ in range(10_000):
            should_run_step(dummy_step, state, _LINKEDOUT_VERSION)
        elapsed = time.monotonic() - start

        # 10,000 calls should complete well under 1 second
        assert elapsed < 1.0

    def test_full_skip_evaluation_fast(self):
        """Evaluating all 14 steps with all completed is fast."""
        all_names = [
            "prerequisites", "system_setup", "database", "python_env",
            "api_keys", "user_profile", "csv_import", "contacts_import",
            "seed_data", "embeddings", "affinity", "skills",
            "readiness", "auto_repair",
        ]
        state = SetupState(
            steps_completed={n: "2026-04-07T14:20:00Z" for n in all_names},
            setup_version=_LINKEDOUT_VERSION,
        )

        steps = [
            SetupStep(
                name=n,
                display_name=n,
                number=i + 1,
                function=lambda **kw: None,
                can_skip=(n not in ("readiness", "auto_repair")),
                always_run=(n in ("readiness", "auto_repair")),
            )
            for i, n in enumerate(all_names)
        ]

        start = time.monotonic()
        results = [should_run_step(s, state, _LINKEDOUT_VERSION) for s in steps]
        elapsed = time.monotonic() - start

        # Only readiness and auto_repair should run
        should_run_names = [
            steps[i].name for i, (run, _) in enumerate(results) if run
        ]
        assert should_run_names == ["readiness", "auto_repair"]
        assert elapsed < 0.01  # Essentially zero I/O


# ══════════════════════════════════════════════════════════════════════
# TestValidateStepState
# ══════════════════════════════════════════════════════════════════════


class TestValidateStepState:
    """Tests for validate_step_state."""

    def test_unknown_step_returns_true(self, tmp_data_dir):
        """Steps without a validator are assumed valid."""
        assert validate_step_state("contacts_import", tmp_data_dir, "") is True

    @patch("linkedout.setup.orchestrator._validate_database")
    def test_database_accessible_returns_true(self, mock_validate, tmp_data_dir):
        """DB accessible + expected tables -> True."""
        mock_validate.return_value = True
        assert validate_step_state("database", tmp_data_dir, "postgresql://x") is True

    @patch("linkedout.setup.orchestrator._validate_database")
    def test_database_inaccessible_returns_false(self, mock_validate, tmp_data_dir):
        """DB inaccessible -> False."""
        mock_validate.return_value = False
        assert validate_step_state("database", tmp_data_dir, "postgresql://x") is False

    @patch("linkedout.setup.orchestrator._validate_python_env")
    def test_python_env_valid_returns_true(self, mock_validate, tmp_data_dir):
        """Valid .venv -> True."""
        mock_validate.return_value = True
        assert validate_step_state("python_env", tmp_data_dir, "") is True

    @patch("linkedout.setup.orchestrator._validate_python_env")
    def test_python_env_missing_returns_false(self, mock_validate, tmp_data_dir):
        """Missing .venv -> False."""
        mock_validate.return_value = False
        assert validate_step_state("python_env", tmp_data_dir, "") is False

    @patch("linkedout.setup.orchestrator._validate_skills")
    def test_skills_exist_returns_true(self, mock_validate, tmp_data_dir):
        """Skill files exist -> True."""
        mock_validate.return_value = True
        assert validate_step_state("skills", tmp_data_dir, "") is True

    @patch("linkedout.setup.orchestrator._validate_skills")
    def test_skills_missing_returns_false(self, mock_validate, tmp_data_dir):
        """Missing skills -> False."""
        mock_validate.return_value = False
        assert validate_step_state("skills", tmp_data_dir, "") is False

    @patch("linkedout.setup.orchestrator._validate_api_keys")
    def test_api_keys_exist_returns_true(self, mock_validate, tmp_data_dir):
        """secrets.yaml exists -> True."""
        mock_validate.return_value = True
        assert validate_step_state("api_keys", tmp_data_dir, "") is True

    @patch("linkedout.setup.orchestrator._validate_api_keys")
    def test_api_keys_missing_returns_false(self, mock_validate, tmp_data_dir):
        """Missing secrets.yaml -> False."""
        mock_validate.return_value = False
        assert validate_step_state("api_keys", tmp_data_dir, "") is False

    def test_validator_exception_returns_false(self, tmp_data_dir):
        """If a validator throws, return False (safe fallback)."""
        with patch(
            "linkedout.setup.orchestrator._validate_database",
            side_effect=OSError("connection refused"),
        ):
            assert validate_step_state("database", tmp_data_dir, "x") is False


# ══════════════════════════════════════════════════════════════════════
# TestRunSetup (end-to-end with mocked steps)
# ══════════════════════════════════════════════════════════════════════


class TestRunSetup:
    """End-to-end tests with all step functions mocked."""

    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="test-corr")
    @patch("linkedout.setup.orchestrator._build_step_registry")
    @patch("linkedout.setup.orchestrator._read_db_url", return_value=None)
    @patch("linkedout.setup.orchestrator._read_embedding_provider", return_value=None)
    def test_fresh_install_runs_all_steps(
        self, mock_embed, mock_db, mock_registry, mock_logging, tmp_data_dir
    ):
        """First run with no state file runs all steps."""
        call_order = []

        def make_step_fn(name):
            def fn(**kwargs):
                call_order.append(name)
                return None
            return fn

        mock_registry.return_value = [
            SetupStep(
                name=f"step_{i}",
                display_name=f"Step {i}",
                number=i,
                function=make_step_fn(f"step_{i}"),
                can_skip=True,
            )
            for i in range(1, 4)
        ]

        run_setup(data_dir=tmp_data_dir, repo_root=Path("/tmp/repo"))

        assert call_order == ["step_1", "step_2", "step_3"]

        # State file should exist with all steps marked complete
        state = load_setup_state(tmp_data_dir)
        assert "step_1" in state.steps_completed
        assert "step_2" in state.steps_completed
        assert "step_3" in state.steps_completed

    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="test-corr")
    @patch("linkedout.setup.orchestrator._build_step_registry")
    @patch("linkedout.setup.orchestrator._read_db_url", return_value=None)
    @patch("linkedout.setup.orchestrator._read_embedding_provider", return_value=None)
    def test_resume_skips_completed_steps(
        self, mock_embed, mock_db, mock_registry, mock_logging, tmp_data_dir
    ):
        """Resume after partial failure skips completed steps."""
        # Pre-populate state with step_1 complete
        state = SetupState(
            steps_completed={"step_1": "2026-04-07T14:20:00Z"},
            setup_version=_LINKEDOUT_VERSION,
        )
        save_setup_state(state, tmp_data_dir)

        call_order = []

        def make_step_fn(name):
            def fn(**kwargs):
                call_order.append(name)
                return None
            return fn

        mock_registry.return_value = [
            SetupStep(
                name="step_1",
                display_name="Step 1",
                number=1,
                function=make_step_fn("step_1"),
                can_skip=True,
            ),
            SetupStep(
                name="step_2",
                display_name="Step 2",
                number=2,
                function=make_step_fn("step_2"),
                can_skip=True,
            ),
        ]

        run_setup(data_dir=tmp_data_dir, repo_root=Path("/tmp/repo"))

        assert call_order == ["step_2"]

    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="test-corr")
    @patch("linkedout.setup.orchestrator._build_step_registry")
    @patch("linkedout.setup.orchestrator._read_db_url", return_value=None)
    @patch("linkedout.setup.orchestrator._read_embedding_provider", return_value=None)
    @patch("linkedout.setup.orchestrator.generate_diagnostic", return_value=Path("/tmp/diag.txt"))
    def test_step_failure_saves_partial_state(
        self, mock_diag, mock_embed, mock_db, mock_registry, mock_logging, tmp_data_dir
    ):
        """Step failure saves state for completed steps, not failed one."""
        call_order = []

        def succeed(**kwargs):
            call_order.append("succeed")

        def fail(**kwargs):
            call_order.append("fail")
            raise RuntimeError("step 2 broke")

        mock_registry.return_value = [
            SetupStep(
                name="step_1",
                display_name="Step 1",
                number=1,
                function=succeed,
                can_skip=True,
            ),
            SetupStep(
                name="step_2",
                display_name="Step 2",
                number=2,
                function=fail,
                can_skip=True,
            ),
            SetupStep(
                name="step_3",
                display_name="Step 3",
                number=3,
                function=succeed,
                can_skip=True,
            ),
        ]

        run_setup(data_dir=tmp_data_dir, repo_root=Path("/tmp/repo"))

        assert call_order == ["succeed", "fail"]

        state = load_setup_state(tmp_data_dir)
        assert "step_1" in state.steps_completed
        assert "step_2" not in state.steps_completed
        assert "step_3" not in state.steps_completed
        assert state.last_failure is not None
        assert state.last_failure["step"] == "step_2"

    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="test-corr")
    @patch("linkedout.setup.orchestrator._build_step_registry")
    @patch("linkedout.setup.orchestrator._read_db_url", return_value=None)
    @patch("linkedout.setup.orchestrator._read_embedding_provider", return_value=None)
    def test_always_run_steps_execute_on_rerun(
        self, mock_embed, mock_db, mock_registry, mock_logging, tmp_data_dir
    ):
        """always_run steps execute even when previously completed."""
        state = SetupState(
            steps_completed={
                "step_1": "2026-04-07T14:20:00Z",
                "step_2": "2026-04-07T14:21:00Z",
            },
            setup_version=_LINKEDOUT_VERSION,
        )
        save_setup_state(state, tmp_data_dir)

        call_order = []

        def make_fn(name):
            def fn(**kwargs):
                call_order.append(name)
            return fn

        mock_registry.return_value = [
            SetupStep(
                name="step_1",
                display_name="Step 1",
                number=1,
                function=make_fn("step_1"),
                can_skip=True,
            ),
            SetupStep(
                name="step_2",
                display_name="Step 2",
                number=2,
                function=make_fn("step_2"),
                can_skip=False,
                always_run=True,
            ),
        ]

        run_setup(data_dir=tmp_data_dir, repo_root=Path("/tmp/repo"))

        # step_1 skipped, step_2 always runs
        assert call_order == ["step_2"]
