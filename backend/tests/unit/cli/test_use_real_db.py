# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``linkedout use-real-db`` CLI command."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from linkedout.commands.use_real_db import use_real_db_command


@pytest.fixture
def runner():
    return CliRunner()


class TestUseRealDbCommand:

    def test_already_using_real_db(self, runner):
        """Should report if not in demo mode."""
        with patch("linkedout.commands.use_real_db.is_demo_mode", return_value=False):
            result = runner.invoke(use_real_db_command)

        assert result.exit_code == 0
        assert "Already using real database" in result.output

    def test_switch_to_real_db(self, runner, tmp_path):
        """Happy path: switch config to real database."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "database_url: postgresql://user:pass@localhost:5432/linkedout_demo\n"
            "demo_mode: true\n"
        )

        import linkedout.setup.database  # noqa: F401

        with patch("linkedout.commands.use_real_db.is_demo_mode", return_value=True), \
             patch("linkedout.commands.use_real_db._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.use_real_db.set_demo_mode") as mock_set, \
             patch("linkedout.commands.use_real_db.drop_demo_database") as mock_drop, \
             patch("linkedout.setup.database.generate_agent_context_env"):

            result = runner.invoke(use_real_db_command)

        assert result.exit_code == 0
        assert "Switched to real database" in result.output
        assert "linkedout setup" in result.output
        mock_set.assert_called_once_with(tmp_path, enabled=False)
        mock_drop.assert_not_called()

    def test_switch_with_drop_demo(self, runner, tmp_path):
        """--drop-demo flag should also drop the demo database."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            "database_url: postgresql://user:pass@localhost:5432/linkedout_demo\n"
            "demo_mode: true\n"
        )

        import linkedout.setup.database  # noqa: F401

        with patch("linkedout.commands.use_real_db.is_demo_mode", return_value=True), \
             patch("linkedout.commands.use_real_db._get_data_dir", return_value=tmp_path), \
             patch("linkedout.commands.use_real_db.set_demo_mode") as mock_set, \
             patch("linkedout.commands.use_real_db.drop_demo_database") as mock_drop, \
             patch("linkedout.setup.database.generate_agent_context_env"):

            mock_drop.return_value = True
            result = runner.invoke(use_real_db_command, ["--drop-demo"])

        assert result.exit_code == 0
        assert "Dropping demo database" in result.output
        mock_drop.assert_called_once()
        mock_set.assert_called_once_with(tmp_path, enabled=False)
