# SPDX-License-Identifier: Apache-2.0
"""Re-run safety tests.

Verifies that running the setup orchestrator a second time skips
completed steps, produces a fresh readiness report, and doesn't
corrupt existing data.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedout.setup.orchestrator import (
    SetupState,
    SetupStep,
    load_setup_state,
    save_setup_state,
    should_run_step,
)


def _noop(**kwargs):
    """No-op step function for testing."""
    return None


class TestSecondRunSkipsCompleted:
    def test_second_run_skips_completed(self, temp_data_dir):
        """After a full run, all skippable steps show 'already complete'."""
        state = SetupState(
            steps_completed={
                "prerequisites": "2026-04-07T10:00:00Z",
                "system_setup": "2026-04-07T10:01:00Z",
                "database": "2026-04-07T10:02:00Z",
                "python_env": "2026-04-07T10:03:00Z",
                "api_keys": "2026-04-07T10:04:00Z",
                "user_profile": "2026-04-07T10:05:00Z",
                "csv_import": "2026-04-07T10:06:00Z",
                "contacts_import": "2026-04-07T10:07:00Z",
                "seed_data": "2026-04-07T10:08:00Z",
                "embeddings": "2026-04-07T10:09:00Z",
                "affinity": "2026-04-07T10:10:00Z",
                "skills": "2026-04-07T10:11:00Z",
                "readiness": "2026-04-07T10:12:00Z",
                "auto_repair": "2026-04-07T10:13:00Z",
            },
            setup_version="0.1.0",
        )

        skippable_steps = [
            SetupStep(name="prerequisites", display_name="Prerequisites", number=1, function=_noop, can_skip=True),
            SetupStep(name="system_setup", display_name="System Setup", number=2, function=_noop, can_skip=True),
            SetupStep(name="database", display_name="Database", number=3, function=_noop, can_skip=True),
            SetupStep(name="python_env", display_name="Python Env", number=4, function=_noop, can_skip=True),
            SetupStep(name="api_keys", display_name="API Keys", number=5, function=_noop, can_skip=True),
            SetupStep(name="user_profile", display_name="User Profile", number=6, function=_noop, can_skip=True),
            SetupStep(name="csv_import", display_name="CSV Import", number=7, function=_noop, can_skip=True),
            SetupStep(name="contacts_import", display_name="Contacts Import", number=8, function=_noop, can_skip=True),
            SetupStep(name="seed_data", display_name="Seed Data", number=9, function=_noop, can_skip=True),
            SetupStep(name="embeddings", display_name="Embeddings", number=10, function=_noop, can_skip=True),
            SetupStep(name="affinity", display_name="Affinity", number=11, function=_noop, can_skip=True),
            SetupStep(name="skills", display_name="Skills", number=12, function=_noop, can_skip=True),
        ]

        for step in skippable_steps:
            should_run, reason = should_run_step(step, state, "0.1.0")
            assert should_run is False, f"Step {step.name} should skip but got: {reason}"
            assert "already complete" in reason


class TestSecondRunProducesFreshReport:
    def test_second_run_produces_fresh_report(self, temp_data_dir):
        """Readiness and auto_repair always re-run, even when completed."""
        state = SetupState(
            steps_completed={
                "readiness": "2026-04-07T10:12:00Z",
                "auto_repair": "2026-04-07T10:13:00Z",
            },
            setup_version="0.1.0",
        )

        always_run_steps = [
            SetupStep(
                name="readiness", display_name="Readiness", number=13,
                function=_noop, can_skip=False, always_run=True,
            ),
            SetupStep(
                name="auto_repair", display_name="Auto Repair", number=14,
                function=_noop, can_skip=False, always_run=True,
            ),
        ]

        for step in always_run_steps:
            should_run, reason = should_run_step(step, state, "0.1.0")
            assert should_run is True, f"Step {step.name} should always run"
            assert "always runs" in reason


class TestSecondRunNoDataLoss:
    def test_second_run_no_data_loss(self, temp_data_dir, setup_state_json):
        """State data from the first run survives the second run."""
        # Load state from first "run"
        state = load_setup_state(temp_data_dir)
        original_steps = dict(state.steps_completed)

        # Simulate second run: update last_run timestamp
        state.last_run = "2026-04-08T10:00:00Z"
        save_setup_state(state, temp_data_dir)

        # Reload and verify nothing was lost
        reloaded = load_setup_state(temp_data_dir)
        for step_name, timestamp in original_steps.items():
            assert step_name in reloaded.steps_completed
            assert reloaded.steps_completed[step_name] == timestamp


class TestSecondRunNoDuplicates:
    def test_csv_import_idempotent_state(self, temp_data_dir):
        """Importing the same CSV twice should not duplicate state entries."""
        state = SetupState()

        # First "import"
        state.steps_completed["csv_import"] = "2026-04-07T10:06:00Z"
        save_setup_state(state, temp_data_dir)

        # Second "import" — same step name, updated timestamp
        state.steps_completed["csv_import"] = "2026-04-08T10:06:00Z"
        save_setup_state(state, temp_data_dir)

        reloaded = load_setup_state(temp_data_dir)
        # Should have exactly one csv_import entry, not two
        assert reloaded.steps_completed["csv_import"] == "2026-04-08T10:06:00Z"


class TestSecondRunFast:
    @pytest.mark.slow
    def test_second_run_fast(self, temp_data_dir, setup_state_json, sample_config_yaml):
        """Second run skip-logic completes quickly (< 5 seconds wall time).

        This tests only the decision logic, not actual step execution.
        """
        state = load_setup_state(temp_data_dir)

        steps = [
            SetupStep(name=name, display_name=name, number=i, function=_noop, can_skip=True)
            for i, name in enumerate(state.steps_completed.keys(), 1)
            if name not in ("readiness", "auto_repair")
        ]

        start = time.monotonic()
        for step in steps:
            should_run_step(step, state, "0.1.0")
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, f"Skip-logic took {elapsed:.2f}s, expected < 5s"
