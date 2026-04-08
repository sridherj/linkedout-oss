# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``linkedout reset-demo`` CLI command."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from linkedout.commands.reset_demo import reset_demo_command


@pytest.fixture
def runner():
    return CliRunner()


class TestResetDemoCommand:

    def test_not_in_demo_mode_errors(self, runner, tmp_path):
        """Should error when not in demo mode."""
        with patch("linkedout.commands.reset_demo._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.reset_demo.is_demo_mode", return_value=False):
            result = runner.invoke(reset_demo_command)

        assert result.exit_code != 0
        assert "Not in demo mode" in result.output

    def test_missing_pg_restore_errors(self, runner, tmp_path):
        with patch("linkedout.commands.reset_demo._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.reset_demo.is_demo_mode", return_value=True), \
             patch("linkedout.commands.reset_demo.check_pg_restore", return_value=False):
            result = runner.invoke(reset_demo_command)

        assert result.exit_code != 0
        assert "pg_restore not found" in result.output

    def test_missing_dump_file_errors(self, runner, tmp_path):
        with patch("linkedout.commands.reset_demo._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.reset_demo.is_demo_mode", return_value=True), \
             patch("linkedout.commands.reset_demo.check_pg_restore", return_value=True):
            result = runner.invoke(reset_demo_command)

        assert result.exit_code != 0
        assert "download-demo" in result.output

    def test_successful_reset(self, runner, tmp_path):
        """Happy path: drop + create + restore from cache."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "demo-seed.dump").write_bytes(b"fake dump")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "database_url: postgresql://user:pass@localhost:5432/linkedout_demo\n"
            "demo_mode: true\n"
        )

        with patch("linkedout.commands.reset_demo._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.reset_demo.is_demo_mode", return_value=True), \
             patch("linkedout.commands.reset_demo.check_pg_restore", return_value=True), \
             patch("linkedout.commands.reset_demo.create_demo_database") as mock_create, \
             patch("linkedout.commands.reset_demo.restore_demo_dump") as mock_restore, \
             patch("linkedout.commands.reset_demo.get_demo_stats") as mock_stats:

            mock_create.return_value = "postgresql://user:pass@localhost:5432/linkedout_demo"
            mock_restore.return_value = True
            mock_stats.return_value = {"profiles": 150, "companies": 200, "connections": 500}

            result = runner.invoke(reset_demo_command, ["--yes"])

        assert result.exit_code == 0
        assert "reset to original state" in result.output
        assert "150" in result.output
        mock_create.assert_called_once()
        mock_restore.assert_called_once()

    def test_confirmation_prompt_aborts(self, runner, tmp_path):
        """Without --yes, user can abort at the confirmation prompt."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "demo-seed.dump").write_bytes(b"fake dump")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "database_url: postgresql://user:pass@localhost:5432/linkedout_demo\n"
        )

        with patch("linkedout.commands.reset_demo._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.reset_demo.is_demo_mode", return_value=True), \
             patch("linkedout.commands.reset_demo.check_pg_restore", return_value=True):
            result = runner.invoke(reset_demo_command, input="n\n")

        assert result.exit_code != 0
