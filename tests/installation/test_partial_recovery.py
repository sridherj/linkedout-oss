# SPDX-License-Identifier: Apache-2.0
"""Interrupted install recovery tests.

Verifies that the setup orchestrator correctly resumes from interrupted
states by reading the persisted ``setup-state.json``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from linkedout.setup.orchestrator import (
    SetupState,
    SetupStep,
    load_setup_state,
    save_setup_state,
    should_run_step,
)


def _noop(**kwargs):
    return None


class TestResumeAfterDbSetup:
    def test_resume_after_db_setup(self, temp_data_dir):
        """After DB setup completes, the orchestrator picks up at python_env."""
        state = SetupState(
            steps_completed={
                "prerequisites": "2026-04-07T10:00:00Z",
                "system_setup": "2026-04-07T10:01:00Z",
                "database": "2026-04-07T10:02:00Z",
            },
            setup_version="0.1.0",
        )
        save_setup_state(state, temp_data_dir)

        loaded = load_setup_state(temp_data_dir)

        # Completed steps should skip
        db_step = SetupStep(name="database", display_name="Database", number=3, function=_noop, can_skip=True)
        should_run, _ = should_run_step(db_step, loaded, "0.1.0")
        assert should_run is False

        # Next step should run
        py_step = SetupStep(name="python_env", display_name="Python Env", number=4, function=_noop, can_skip=True)
        should_run, reason = should_run_step(py_step, loaded, "0.1.0")
        assert should_run is True
        assert "not yet completed" in reason


class TestResumeAfterImport:
    def test_resume_after_import(self, temp_data_dir):
        """After CSV import, the orchestrator picks up at contacts_import."""
        state = SetupState(
            steps_completed={
                "prerequisites": "2026-04-07T10:00:00Z",
                "system_setup": "2026-04-07T10:01:00Z",
                "database": "2026-04-07T10:02:00Z",
                "python_env": "2026-04-07T10:03:00Z",
                "api_keys": "2026-04-07T10:04:00Z",
                "user_profile": "2026-04-07T10:05:00Z",
                "csv_import": "2026-04-07T10:06:00Z",
            },
            setup_version="0.1.0",
        )
        save_setup_state(state, temp_data_dir)

        loaded = load_setup_state(temp_data_dir)

        contacts_step = SetupStep(
            name="contacts_import", display_name="Contacts Import",
            number=8, function=_noop, can_skip=True,
        )
        should_run, reason = should_run_step(contacts_step, loaded, "0.1.0")
        assert should_run is True
        assert "not yet completed" in reason


class TestCorruptedStateFile:
    def test_corrupted_state_file(self, temp_data_dir):
        """Corrupt ``setup-state.json`` leads to graceful recovery (fresh state)."""
        state_path = temp_data_dir / "state" / "setup-state.json"
        state_path.write_text("{this is not valid json!!!}", encoding="utf-8")

        state = load_setup_state(temp_data_dir)

        assert state.steps_completed == {}
        assert state.setup_version == "0.0.0"

    def test_malformed_state_dict(self, temp_data_dir):
        """A JSON file that isn't a dict returns fresh state."""
        state_path = temp_data_dir / "state" / "setup-state.json"
        state_path.write_text('"just a string"', encoding="utf-8")

        state = load_setup_state(temp_data_dir)

        assert state.steps_completed == {}
        assert state.setup_version == "0.0.0"

    def test_malformed_steps_completed(self, temp_data_dir):
        """A state file with non-dict steps_completed returns fresh state."""
        state_path = temp_data_dir / "state" / "setup-state.json"
        state_path.write_text(
            json.dumps({"steps_completed": "not a dict"}),
            encoding="utf-8",
        )

        state = load_setup_state(temp_data_dir)

        assert state.steps_completed == {}

    def test_empty_state_file(self, temp_data_dir):
        """An empty state file returns fresh state."""
        state_path = temp_data_dir / "state" / "setup-state.json"
        state_path.write_text("", encoding="utf-8")

        state = load_setup_state(temp_data_dir)
        assert state.steps_completed == {}


class TestPartialMigration:
    def test_partial_migration_resumes(self, temp_data_dir):
        """If database step completed but migrations failed, state is partial.

        The orchestrator records a failure in ``last_failure`` and the
        database step can be re-run.
        """
        state = SetupState(
            steps_completed={
                "prerequisites": "2026-04-07T10:00:00Z",
                "system_setup": "2026-04-07T10:01:00Z",
                # database NOT in steps_completed — it failed
            },
            setup_version="0.1.0",
            last_failure={
                "step": "database",
                "error": "RuntimeError: Alembic migration failed",
                "timestamp": "2026-04-07T10:02:30Z",
            },
        )
        save_setup_state(state, temp_data_dir)

        loaded = load_setup_state(temp_data_dir)

        db_step = SetupStep(name="database", display_name="Database", number=3, function=_noop, can_skip=True)
        should_run, reason = should_run_step(db_step, loaded, "0.1.0")
        assert should_run is True
        assert "not yet completed" in reason

        # last_failure should be preserved
        assert loaded.last_failure is not None
        assert loaded.last_failure["step"] == "database"


class TestPartialEmbedding:
    def test_partial_embedding_resumes(self, temp_data_dir):
        """If embeddings step failed, it should re-run on resume."""
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
                # embeddings NOT in steps_completed — interrupted
            },
            setup_version="0.1.0",
        )
        save_setup_state(state, temp_data_dir)

        loaded = load_setup_state(temp_data_dir)

        emb_step = SetupStep(
            name="embeddings", display_name="Embeddings",
            number=10, function=_noop, can_skip=True,
        )
        should_run, reason = should_run_step(emb_step, loaded, "0.1.0")
        assert should_run is True
        assert "not yet completed" in reason
