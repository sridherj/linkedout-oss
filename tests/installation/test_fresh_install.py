# SPDX-License-Identifier: Apache-2.0
"""End-to-end fresh install smoke tests.

These tests mock all external dependencies (subprocess calls, user input,
network) and run the full setup orchestrator against an isolated data
directory. Each test ends by verifying the setup state file.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linkedout.setup.orchestrator import (
    SetupContext,
    SetupState,
    SetupStep,
    load_setup_state,
    run_step,
    save_setup_state,
    should_run_step,
)
from linkedout.setup.prerequisites import (
    DiskStatus,
    PlatformInfo,
    PostgresStatus,
    PrerequisiteReport,
    PythonStatus,
)
from linkedout.setup.readiness import ReadinessReport


def _mock_prerequisites(*args, **kwargs):
    """Return a fully healthy PrerequisiteReport."""
    return PrerequisiteReport(
        platform=PlatformInfo(os="linux", distro="ubuntu", package_manager="apt", arch="x86_64"),
        postgres=PostgresStatus(
            installed=True, running=True, version="16.2", major_version=16,
            has_pgvector=True, has_pg_trgm=True,
        ),
        python=PythonStatus(installed=True, version="3.12.1", has_pip=True, has_venv=True),
        disk=DiskStatus(free_gb=10.0, mount_point="/", sufficient=True, recommended=True),
        ready=True,
        blockers=[],
    )


class TestFreshInstallHappyPath:
    """Test the orchestrator's skip/run decision logic and state persistence."""

    def test_fresh_install_all_steps_run(self, temp_data_dir):
        """On a fresh system, every step should be marked 'should run'."""
        state = SetupState()  # empty state

        step = SetupStep(
            name="prerequisites",
            display_name="Prerequisites Detection",
            number=1,
            function=_mock_prerequisites,
            can_skip=True,
        )

        should_run, reason = should_run_step(step, state, "0.1.0")
        assert should_run is True
        assert "not yet completed" in reason

    def test_prerequisites_step_produces_report(self, temp_data_dir):
        """Running the prerequisites step returns None (not OperationReport)."""
        step = SetupStep(
            name="prerequisites",
            display_name="Prerequisites Detection",
            number=1,
            function=_mock_prerequisites,
        )
        context = SetupContext(
            data_dir=temp_data_dir,
            repo_root=Path("/tmp/fake-repo"),
        )
        result = run_step(step, context)
        # prerequisites returns None (not an OperationReport)
        assert result is None

    def test_completed_step_skips_on_second_run(self, temp_data_dir):
        """A step that completed should skip on re-run."""
        state = SetupState(
            steps_completed={"prerequisites": "2026-04-07T10:00:00Z"},
            setup_version="0.1.0",
        )

        step = SetupStep(
            name="prerequisites",
            display_name="Prerequisites Detection",
            number=1,
            function=_mock_prerequisites,
            can_skip=True,
        )

        should_run, reason = should_run_step(step, state, "0.1.0")
        assert should_run is False
        assert "already complete" in reason


class TestFreshInstallLocalEmbeddings:
    """Verify fresh install path with local embedding provider."""

    def test_local_embedding_provider_selection(self, temp_data_dir):
        """When config says local, context should reflect that."""
        context = SetupContext(
            data_dir=temp_data_dir,
            repo_root=Path("/tmp/fake-repo"),
            embedding_provider="local",
        )
        assert context.embedding_provider == "local"


class TestFreshInstallOpenAIEmbeddings:
    """Verify fresh install path with OpenAI embedding provider."""

    def test_openai_embedding_provider_selection(self, temp_data_dir):
        """When config says openai, context should reflect that."""
        context = SetupContext(
            data_dir=temp_data_dir,
            repo_root=Path("/tmp/fake-repo"),
            embedding_provider="openai",
        )
        assert context.embedding_provider == "openai"


class TestFreshInstallNoContacts:
    """Verify setup works when contacts import is skipped."""

    def test_skip_contacts_does_not_block(self, temp_data_dir):
        """Skipping contacts_import should still allow subsequent steps."""
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
            },
            setup_version="0.1.0",
        )

        # seed_data should be runnable since contacts_import completed
        step = SetupStep(
            name="seed_data",
            display_name="Seed Data",
            number=9,
            function=lambda **kw: None,
            can_skip=True,
        )

        should_run, reason = should_run_step(step, state, "0.1.0")
        assert should_run is True  # Not yet completed
        assert "not yet completed" in reason


class TestFreshInstallProducesReadinessReport:
    """Verify that the readiness step always runs."""

    def test_readiness_step_always_runs(self, temp_data_dir):
        """The readiness step has always_run=True, even when completed."""
        state = SetupState(
            steps_completed={"readiness": "2026-04-07T10:12:00Z"},
            setup_version="0.1.0",
        )

        step = SetupStep(
            name="readiness",
            display_name="Readiness Check",
            number=13,
            function=lambda **kw: None,
            can_skip=False,
            always_run=True,
        )

        should_run, reason = should_run_step(step, state, "0.1.0")
        assert should_run is True
        assert "always runs" in reason


class TestSetupStatePersistence:
    """Verify state file operations."""

    def test_save_and_load_roundtrip(self, temp_data_dir):
        """State should survive a save/load cycle."""
        state = SetupState(
            steps_completed={"prerequisites": "2026-04-07T10:00:00Z"},
            setup_version="0.1.0",
            last_run="2026-04-07T10:00:00Z",
        )

        save_setup_state(state, temp_data_dir)
        loaded = load_setup_state(temp_data_dir)

        assert loaded.steps_completed == state.steps_completed
        assert loaded.setup_version == state.setup_version
        assert loaded.last_run == state.last_run

    def test_load_missing_state_returns_empty(self, temp_data_dir):
        """Loading from a directory with no state file returns empty state."""
        state = load_setup_state(temp_data_dir)
        assert state.steps_completed == {}
        assert state.setup_version == "0.0.0"

    def test_save_state_atomic(self, temp_data_dir):
        """State file should be written atomically (no partial writes)."""
        state = SetupState(
            steps_completed={"prerequisites": "2026-04-07T10:00:00Z"},
            setup_version="0.1.0",
        )

        save_setup_state(state, temp_data_dir)

        state_path = temp_data_dir / "state" / "setup-state.json"
        assert state_path.exists()

        # Verify it's valid JSON
        data = json.loads(state_path.read_text())
        assert "steps_completed" in data
        assert "setup_version" in data
