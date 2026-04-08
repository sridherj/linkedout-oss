# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``linkedout restore-demo`` CLI command and demo db_utils.

DB operations are mocked — integration tests requiring a running Postgres
are marked with ``@pytest.mark.integration``.
"""
from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from linkedout.commands.restore_demo import restore_demo_command
from linkedout.demo.db_utils import (
    _build_maintenance_url,
    check_pg_restore,
    get_demo_stats,
)


@pytest.fixture
def runner():
    return CliRunner()


# ── db_utils unit tests ──────────────────────────────────────────────────────


class TestCheckPgRestore:

    def test_available(self):
        with patch("linkedout.demo.db_utils.shutil.which", return_value="/usr/bin/pg_restore"):
            assert check_pg_restore() is True

    def test_not_available(self):
        with patch("linkedout.demo.db_utils.shutil.which", return_value=None):
            assert check_pg_restore() is False


class TestBuildMaintenanceUrl:

    def test_replaces_db_name(self):
        url = _build_maintenance_url("postgresql://user:pass@localhost:5432/linkedout")
        assert url == "postgresql://user:pass@localhost:5432/postgres"

    def test_handles_no_password(self):
        url = _build_maintenance_url("postgresql://user@localhost:5432/linkedout")
        assert url == "postgresql://user@localhost:5432/postgres"


class TestGetDemoStats:

    def test_returns_counts(self):
        def mock_run(cmd, **_kwargs):
            # Find the SQL in the -c argument
            sql = " ".join(cmd)
            if "crawled_profile" in sql:
                return subprocess.CompletedProcess(cmd, 0, stdout="150\n", stderr="")
            if "company" in sql:
                return subprocess.CompletedProcess(cmd, 0, stdout="200\n", stderr="")
            if "connection" in sql:
                return subprocess.CompletedProcess(cmd, 0, stdout="500\n", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")

        with patch("linkedout.demo.db_utils.subprocess.run", side_effect=mock_run):
            stats = get_demo_stats("postgresql://user:pass@localhost:5432/linkedout_demo")

        assert stats["profiles"] == 150
        assert stats["companies"] == 200
        assert stats["connections"] == 500

    def test_returns_negative_on_failure(self):
        result = subprocess.CompletedProcess([], 1, stdout="", stderr="error")
        with patch("linkedout.demo.db_utils.subprocess.run", return_value=result):
            stats = get_demo_stats("postgresql://user:pass@localhost:5432/linkedout_demo")

        assert stats["profiles"] == -1


# ── restore-demo command tests ────────────────────────────────────────────────


class TestRestoreDemoCommand:

    def test_missing_pg_restore_errors(self, runner, tmp_path):
        """Missing pg_restore -> clear error message."""
        with patch("linkedout.commands.restore_demo._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.restore_demo.check_pg_restore", return_value=False):
            result = runner.invoke(restore_demo_command)

        assert result.exit_code != 0
        assert "pg_restore not found" in result.output

    def test_missing_dump_file_errors(self, runner, tmp_path):
        """Dump file not found -> tells user to run download-demo."""
        with patch("linkedout.commands.restore_demo._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.restore_demo.check_pg_restore", return_value=True):
            result = runner.invoke(restore_demo_command)

        assert result.exit_code != 0
        assert "download-demo" in result.output

    def test_successful_restore(self, runner, tmp_path):
        """Full happy path with all subprocess calls mocked."""
        # Create the dump file
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "demo-seed.dump").write_bytes(b"fake dump data")

        # Create config
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "database_url: postgresql://user:pass@localhost:5432/linkedout\n"
        )

        # Pre-import the module so patch target exists
        import linkedout.setup.database  # noqa: F401

        with patch("linkedout.commands.restore_demo._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.restore_demo.check_pg_restore", return_value=True), \
             patch("linkedout.commands.restore_demo.create_demo_database") as mock_create, \
             patch("linkedout.commands.restore_demo.restore_demo_dump") as mock_restore, \
             patch("linkedout.commands.restore_demo.set_demo_mode") as mock_set_mode, \
             patch("linkedout.commands.restore_demo.get_demo_stats") as mock_stats, \
             patch("linkedout.setup.database.generate_agent_context_env") as mock_agent_ctx:

            mock_create.return_value = "postgresql://user:pass@localhost:5432/linkedout_demo"
            mock_restore.return_value = True
            mock_stats.return_value = {"profiles": 150, "companies": 200, "connections": 500}
            mock_agent_ctx.return_value = tmp_path / "config" / "agent-context.env"

            result = runner.invoke(restore_demo_command)

        assert result.exit_code == 0
        assert "Demo database restored" in result.output
        assert "150" in result.output
        mock_set_mode.assert_called_once_with(tmp_path, enabled=True)
