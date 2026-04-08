# SPDX-License-Identifier: Apache-2.0
"""Unit tests for orchestrator demo mode integration.

Tests cover:
- should_run_step with "demo-skipped" state
- Step numbering ("Step N of 4" vs "Step N of 14")
- Demo eligibility detection
- Transition flow (clearing demo-skipped, running steps 5-14)
- Re-run in demo mode is a fast no-op
- DEMO_SKIPPABLE_STEPS constant
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from linkedout.setup.orchestrator import (
    DEMO_SKIPPABLE_STEPS,
    SetupState,
    SetupStep,
    _is_demo_eligible,
    _is_demo_mode_active,
    should_run_step,
)


@pytest.fixture
def data_dir(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return tmp_path


def _write_config(data_dir: Path, config: dict) -> None:
    config_path = data_dir / "config" / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f)


def _make_step(name: str = "api_keys", number: int = 5) -> SetupStep:
    return SetupStep(
        name=name,
        display_name="API Key Collection",
        number=number,
        function=lambda: None,
        can_skip=True,
    )


# ── should_run_step with demo-skipped ──────────────────────────────────


class TestShouldRunStepDemoSkipped:

    def test_demo_skipped_treated_as_complete(self):
        """'demo-skipped' in steps_completed means the step should NOT run."""
        step = _make_step()
        state = SetupState(steps_completed={"api_keys": "demo-skipped"})

        should_run, reason = should_run_step(step, state, "0.1.0")

        assert should_run is False
        assert "demo" in reason.lower()

    def test_normal_completed_still_works(self):
        step = _make_step()
        state = SetupState(steps_completed={"api_keys": "2026-04-08T12:00:00Z"})

        should_run, reason = should_run_step(step, state, "0.1.0")

        assert should_run is False
        assert "already complete" in reason

    def test_not_completed_still_runs(self):
        step = _make_step()
        state = SetupState(steps_completed={})

        should_run, reason = should_run_step(step, state, "0.1.0")

        assert should_run is True

    def test_always_run_overrides_demo_skipped(self):
        """always_run=True steps should run even if demo-skipped."""
        step = SetupStep(
            name="readiness",
            display_name="Readiness Check",
            number=13,
            function=lambda: None,
            can_skip=False,
            always_run=True,
        )
        state = SetupState(steps_completed={"readiness": "demo-skipped"})

        # always_run check comes first in should_run_step
        should_run, reason = should_run_step(step, state, "0.1.0")

        assert should_run is True
        assert "always runs" in reason


# ── DEMO_SKIPPABLE_STEPS constant ─────────────────────────────────────


class TestDemoSkippableSteps:

    def test_contains_expected_steps(self):
        expected = {"api_keys", "user_profile", "csv_import", "contacts_import",
                    "seed_data", "embeddings", "affinity"}
        assert DEMO_SKIPPABLE_STEPS == expected

    def test_does_not_contain_infra_steps(self):
        for step in ("prerequisites", "system_setup", "database", "python_env"):
            assert step not in DEMO_SKIPPABLE_STEPS

    def test_does_not_contain_post_demo_steps(self):
        for step in ("skills", "readiness", "auto_repair"):
            assert step not in DEMO_SKIPPABLE_STEPS


# ── Demo eligibility ──────────────────────────────────────────────────


class TestDemoEligibility:

    def test_fresh_install_is_eligible(self, data_dir):
        state = SetupState(steps_completed={
            "prerequisites": "2026-04-08T12:00:00Z",
            "system_setup": "2026-04-08T12:00:00Z",
            "database": "2026-04-08T12:00:00Z",
            "python_env": "2026-04-08T12:00:00Z",
        })
        assert _is_demo_eligible(state, data_dir) is True

    def test_not_eligible_when_demo_mode_set_true(self, data_dir):
        _write_config(data_dir, {"demo_mode": True})
        state = SetupState()
        assert _is_demo_eligible(state, data_dir) is False

    def test_not_eligible_when_demo_mode_set_false(self, data_dir):
        _write_config(data_dir, {"demo_mode": False})
        state = SetupState()
        assert _is_demo_eligible(state, data_dir) is False

    def test_not_eligible_when_steps_beyond_4_complete(self, data_dir):
        state = SetupState(steps_completed={
            "prerequisites": "2026-04-08T12:00:00Z",
            "api_keys": "2026-04-08T12:00:00Z",
        })
        assert _is_demo_eligible(state, data_dir) is False

    def test_empty_state_is_eligible(self, data_dir):
        state = SetupState()
        assert _is_demo_eligible(state, data_dir) is True


# ── Demo mode detection ───────────────────────────────────────────────


class TestIsDemoModeActive:

    def test_true_when_config_says_true(self, data_dir):
        _write_config(data_dir, {"demo_mode": True})
        assert _is_demo_mode_active(data_dir) is True

    def test_false_when_config_says_false(self, data_dir):
        _write_config(data_dir, {"demo_mode": False})
        assert _is_demo_mode_active(data_dir) is False

    def test_false_when_no_config(self, data_dir):
        assert _is_demo_mode_active(data_dir) is False

    def test_false_when_config_missing_key(self, data_dir):
        _write_config(data_dir, {"database_url": "postgresql://localhost/linkedout"})
        assert _is_demo_mode_active(data_dir) is False


# ── Step numbering ────────────────────────────────────────────────────


class TestStepNumbering:

    @patch("linkedout.setup.orchestrator._is_demo_mode_active", return_value=False)
    @patch("linkedout.setup.orchestrator._is_demo_eligible", return_value=True)
    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="test-id")
    @patch("linkedout.setup.orchestrator.load_setup_state")
    @patch("linkedout.setup.orchestrator._build_step_registry")
    @patch("linkedout.setup.orchestrator.run_step")
    @patch("linkedout.setup.orchestrator.save_setup_state")
    def test_shows_of_4_when_demo_eligible(
        self,
        mock_save,
        mock_run_step,
        mock_registry,
        mock_load_state,
        mock_init,
        mock_eligible,
        mock_demo_active,
        data_dir,
        capsys,
    ):
        """When demo-eligible, infra steps should show 'Step N of 4'."""
        # Set up just the first step to run
        step1 = SetupStep(
            name="prerequisites",
            display_name="Prerequisites Detection",
            number=1,
            function=lambda: None,
            can_skip=True,
        )
        mock_registry.return_value = [step1]
        mock_load_state.return_value = SetupState()
        mock_run_step.return_value = None

        from linkedout.setup.orchestrator import run_setup

        run_setup(data_dir=data_dir, repo_root=data_dir)

        captured = capsys.readouterr()
        assert "Step 1 of 4" in captured.out

    @patch("linkedout.setup.orchestrator._is_demo_mode_active", return_value=False)
    @patch("linkedout.setup.orchestrator._is_demo_eligible", return_value=False)
    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="test-id")
    @patch("linkedout.setup.orchestrator.load_setup_state")
    @patch("linkedout.setup.orchestrator._build_step_registry")
    @patch("linkedout.setup.orchestrator.run_step")
    @patch("linkedout.setup.orchestrator.save_setup_state")
    def test_shows_of_14_when_not_demo_eligible(
        self,
        mock_save,
        mock_run_step,
        mock_registry,
        mock_load_state,
        mock_init,
        mock_eligible,
        mock_demo_active,
        data_dir,
        capsys,
    ):
        """When not demo-eligible, steps should show 'Step N of 14'."""
        steps = [
            SetupStep(
                name=f"step_{i}",
                display_name=f"Step {i}",
                number=i,
                function=lambda: None,
                can_skip=True,
            )
            for i in range(1, 15)
        ]
        mock_registry.return_value = steps
        mock_load_state.return_value = SetupState()
        mock_run_step.return_value = None

        from linkedout.setup.orchestrator import run_setup

        run_setup(data_dir=data_dir, repo_root=data_dir)

        captured = capsys.readouterr()
        assert "of 14" in captured.out


# ── Transition flow ───────────────────────────────────────────────────


class TestTransitionFlow:

    def test_clear_demo_state_removes_demo_skipped(self, data_dir):
        from linkedout.setup.orchestrator import _clear_demo_state, save_setup_state

        state = SetupState(steps_completed={
            "prerequisites": "2026-04-08T12:00:00Z",
            "system_setup": "2026-04-08T12:00:00Z",
            "database": "2026-04-08T12:00:00Z",
            "python_env": "2026-04-08T12:00:00Z",
            "api_keys": "demo-skipped",
            "user_profile": "demo-skipped",
            "csv_import": "demo-skipped",
            "contacts_import": "demo-skipped",
            "seed_data": "demo-skipped",
            "embeddings": "demo-skipped",
            "affinity": "demo-skipped",
            "skills": "2026-04-08T12:00:00Z",
            "readiness": "2026-04-08T12:00:00Z",
            "auto_repair": "demo-skipped",
        })

        _write_config(data_dir, {
            "demo_mode": True,
            "database_url": "postgresql://localhost/linkedout_demo",
        })

        with patch("linkedout.setup.database.generate_agent_context_env"):
            _clear_demo_state(state, data_dir)

        # Demo-skippable steps should be cleared
        for step_name in DEMO_SKIPPABLE_STEPS:
            assert step_name not in state.steps_completed

        # auto_repair should also be cleared
        assert "auto_repair" not in state.steps_completed

        # Infra steps should remain
        assert state.steps_completed["prerequisites"] == "2026-04-08T12:00:00Z"
        assert state.steps_completed["skills"] == "2026-04-08T12:00:00Z"


# ── Demo re-run no-op ─────────────────────────────────────────────────


class TestDemoRerunNoop:

    @patch("linkedout.setup.orchestrator._is_demo_mode_active", return_value=True)
    @patch("linkedout.setup.orchestrator.init_setup_logging", return_value="test-id")
    @patch("linkedout.setup.orchestrator.load_setup_state")
    @patch("linkedout.setup.orchestrator._build_step_registry")
    @patch("linkedout.setup.demo_offer.offer_transition", return_value=False)
    def test_declining_transition_is_noop(
        self,
        mock_transition,
        mock_registry,
        mock_load_state,
        mock_init,
        mock_demo_active,
        data_dir,
        capsys,
    ):
        """Declining transition in demo mode should print summary and exit."""
        steps = [
            SetupStep(
                name="prerequisites",
                display_name="Prerequisites Detection",
                number=1,
                function=lambda: None,
                can_skip=True,
            ),
            SetupStep(
                name="api_keys",
                display_name="API Key Collection",
                number=5,
                function=lambda: None,
                can_skip=True,
            ),
        ]
        mock_registry.return_value = steps
        mock_load_state.return_value = SetupState(
            steps_completed={
                "prerequisites": "2026-04-08T12:00:00Z",
                "api_keys": "demo-skipped",
            }
        )

        from linkedout.setup.orchestrator import run_setup

        # This should NOT run any steps — it should just show summary and return
        run_setup(data_dir=data_dir, repo_root=data_dir)

        captured = capsys.readouterr()
        assert "Already complete" in captured.out or "demo mode" in captured.out.lower()
        mock_transition.assert_called_once()
