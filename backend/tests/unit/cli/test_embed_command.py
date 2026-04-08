# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the ``linkedout embed`` CLI command.

Lightweight tests that verify CLI flag recognition, provider validation,
and output format without requiring a real database.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from linkedout.commands.embed import embed_command


@pytest.fixture
def runner():
    """Create a Click CliRunner for testing CLI commands."""
    return CliRunner()


class TestFlagRecognition:
    """Verify that CLI flags are recognized and parsed correctly."""

    def test_dry_run_flag_recognized(self, runner):
        """--dry-run flag should be accepted without error."""
        with patch('linkedout.commands.embed.get_embedding_provider') as mock_prov:
            prov = MagicMock()
            prov.model_name.return_value = 'text-embedding-3-small'
            prov.dimension.return_value = 1536
            prov.estimate_time.return_value = '~1 minute'
            prov.estimate_cost.return_value = '~$0.02'
            mock_prov.return_value = prov

            with patch('linkedout.commands.embed.get_progress_path') as mock_pp:
                mock_pp.return_value = MagicMock(exists=MagicMock(return_value=False))

                with patch('linkedout.commands.embed.EmbeddingProgress.load', return_value=None):
                    with patch('linkedout.commands.embed.db_session_manager') as mock_db:
                        mock_session = MagicMock()
                        mock_session.execute.return_value.fetchall.return_value = [
                            ('cp_1', 'John Doe', 'Engineer', 'About', 'Acme', 'SWE'),
                        ]
                        mock_db.get_session.return_value.__enter__ = MagicMock(
                            return_value=mock_session
                        )
                        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

                        result = runner.invoke(embed_command, ['--dry-run'])

        assert result.exit_code == 0
        assert 'DRY RUN' in result.output

    def test_force_flag_recognized(self, runner):
        """--force flag should be accepted."""
        # Just verify the flag is parsed, not the full execution
        result = runner.invoke(embed_command, ['--force', '--help'])
        # --help exits with 0 even with other flags
        assert result.exit_code == 0

    def test_provider_openai_accepted(self, runner):
        """--provider openai should be a valid choice."""
        result = runner.invoke(embed_command, ['--provider', 'openai', '--help'])
        assert result.exit_code == 0

    def test_provider_local_accepted(self, runner):
        """--provider local should be a valid choice."""
        result = runner.invoke(embed_command, ['--provider', 'local', '--help'])
        assert result.exit_code == 0

    def test_provider_invalid_rejected(self, runner):
        """--provider invalid should be rejected by Click."""
        result = runner.invoke(embed_command, ['--provider', 'invalid'])
        assert result.exit_code != 0
        assert 'invalid' in result.output.lower() or 'invalid' in (result.stderr or '').lower()

    def test_batch_flag_recognized(self, runner):
        """--batch flag should be accepted."""
        result = runner.invoke(embed_command, ['--batch', '--help'])
        assert result.exit_code == 0


class TestHelpText:
    """Verify the command help text is useful."""

    def test_help_includes_description(self, runner):
        result = runner.invoke(embed_command, ['--help'])
        assert result.exit_code == 0
        assert 'embedding' in result.output.lower() or 'embed' in result.output.lower()

    def test_help_shows_all_options(self, runner):
        result = runner.invoke(embed_command, ['--help'])
        assert '--provider' in result.output
        assert '--dry-run' in result.output
        assert '--force' in result.output
        assert '--batch' in result.output


class TestDryRunOutput:
    """Verify dry-run output format matches the operation result pattern."""

    def test_dry_run_shows_profile_count(self, runner):
        with patch('linkedout.commands.embed.get_embedding_provider') as mock_prov:
            prov = MagicMock()
            prov.model_name.return_value = 'text-embedding-3-small'
            prov.dimension.return_value = 1536
            prov.estimate_time.return_value = '~2 minutes'
            prov.estimate_cost.return_value = '~$0.04 for 4000 profiles'
            mock_prov.return_value = prov

            with patch('linkedout.commands.embed.get_progress_path') as mock_pp:
                mock_pp.return_value = MagicMock(exists=MagicMock(return_value=False))

                with patch('linkedout.commands.embed.EmbeddingProgress.load', return_value=None):
                    with patch('linkedout.commands.embed.db_session_manager') as mock_db:
                        # Return 3 profiles
                        mock_session = MagicMock()
                        mock_session.execute.return_value.fetchall.side_effect = [
                            [  # profiles query
                                ('cp_1', 'John Doe', 'Engineer', 'About', 'Acme', 'SWE'),
                                ('cp_2', 'Jane Smith', 'Designer', 'Bio', 'Corp', 'UX'),
                                ('cp_3', 'Bob Lee', 'PM', 'Summary', 'StartupCo', 'PM'),
                            ],
                            [],  # experiences query
                        ]
                        mock_db.get_session.return_value.__enter__ = MagicMock(
                            return_value=mock_session
                        )
                        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

                        result = runner.invoke(embed_command, ['--dry-run'])

        assert result.exit_code == 0
        assert 'DRY RUN' in result.output
        assert '3' in result.output  # profile count
        assert 'text-embedding-3-small' in result.output
        assert '1536' in result.output or '1,536' in result.output

    def test_dry_run_shows_cost_for_openai(self, runner):
        with patch('linkedout.commands.embed.get_embedding_provider') as mock_prov:
            prov = MagicMock()
            prov.model_name.return_value = 'text-embedding-3-small'
            prov.dimension.return_value = 1536
            prov.estimate_time.return_value = '~1 minute'
            prov.estimate_cost.return_value = '~$0.02'
            mock_prov.return_value = prov

            with patch('linkedout.commands.embed.get_progress_path') as mock_pp:
                mock_pp.return_value = MagicMock(exists=MagicMock(return_value=False))

                with patch('linkedout.commands.embed.EmbeddingProgress.load', return_value=None):
                    with patch('linkedout.commands.embed.db_session_manager') as mock_db:
                        mock_session = MagicMock()
                        mock_session.execute.return_value.fetchall.side_effect = [
                            [('cp_1', 'John', 'Eng', 'About', 'Acme', 'SWE')],
                            [],
                        ]
                        mock_db.get_session.return_value.__enter__ = MagicMock(
                            return_value=mock_session
                        )
                        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

                        result = runner.invoke(embed_command, ['--dry-run'])

        assert result.exit_code == 0
        assert '$' in result.output  # cost estimate present

    def test_dry_run_no_cost_for_local(self, runner):
        with patch('linkedout.commands.embed.get_embedding_provider') as mock_prov:
            prov = MagicMock()
            prov.model_name.return_value = 'nomic-embed-text-v1.5'
            prov.dimension.return_value = 768
            prov.estimate_time.return_value = '~5 minutes'
            prov.estimate_cost.return_value = None
            mock_prov.return_value = prov

            with patch('linkedout.commands.embed.get_progress_path') as mock_pp:
                mock_pp.return_value = MagicMock(exists=MagicMock(return_value=False))

                with patch('linkedout.commands.embed.EmbeddingProgress.load', return_value=None):
                    with patch('linkedout.commands.embed.db_session_manager') as mock_db:
                        mock_session = MagicMock()
                        mock_session.execute.return_value.fetchall.side_effect = [
                            [('cp_1', 'John', 'Eng', 'About', 'Acme', 'SWE')],
                            [],
                        ]
                        mock_db.get_session.return_value.__enter__ = MagicMock(
                            return_value=mock_session
                        )
                        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

                        result = runner.invoke(embed_command, ['--dry-run'])

        assert result.exit_code == 0
        assert 'nomic' in result.output
        # No cost line for local
        assert 'cost' not in result.output.lower() or 'Estimated cost' not in result.output


class TestZeroProfiles:
    """Verify clean exit when no profiles need embedding."""

    def test_no_profiles_exits_cleanly(self, runner):
        with patch('linkedout.commands.embed.get_embedding_provider') as mock_prov:
            prov = MagicMock()
            prov.model_name.return_value = 'text-embedding-3-small'
            prov.dimension.return_value = 1536
            mock_prov.return_value = prov

            with patch('linkedout.commands.embed.get_progress_path') as mock_pp:
                mock_pp.return_value = MagicMock(exists=MagicMock(return_value=False))

                with patch('linkedout.commands.embed.EmbeddingProgress.load', return_value=None):
                    with patch('linkedout.commands.embed.db_session_manager') as mock_db:
                        mock_session = MagicMock()
                        mock_session.execute.return_value.fetchall.return_value = []
                        mock_db.get_session.return_value.__enter__ = MagicMock(
                            return_value=mock_session
                        )
                        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

                        result = runner.invoke(embed_command, [])

        assert result.exit_code == 0
        assert 'no profiles' in result.output.lower()


class TestAlreadyCompleted:
    """Verify behavior when all profiles are already embedded."""

    def test_completed_without_force_exits(self, runner):
        """When progress shows completed, should exit early without --force."""
        with patch('linkedout.commands.embed.get_embedding_provider') as mock_prov:
            prov = MagicMock()
            prov.model_name.return_value = 'text-embedding-3-small'
            prov.dimension.return_value = 1536
            mock_prov.return_value = prov

            with patch('linkedout.commands.embed.get_progress_path') as mock_pp:
                mock_pp.return_value = MagicMock()

                progress = MagicMock()
                progress.status = "completed"
                progress.model = "text-embedding-3-small"
                progress.provider = "openai"
                with patch('linkedout.commands.embed.EmbeddingProgress.load', return_value=progress):
                    result = runner.invoke(embed_command, [])

        assert result.exit_code == 0
        assert 'already embedded' in result.output.lower()
        assert '--force' in result.output


class TestFormatDuration:
    """Test the _format_duration helper."""

    def test_seconds(self):
        from linkedout.commands.embed import _format_duration
        assert _format_duration(5.5) == "5.5s"

    def test_minutes(self):
        from linkedout.commands.embed import _format_duration
        assert _format_duration(125) == "2m 5s"

    def test_hours(self):
        from linkedout.commands.embed import _format_duration
        assert _format_duration(3661) == "1h 1m"
