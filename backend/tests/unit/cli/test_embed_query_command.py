# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the ``linkedout embed-query`` CLI command.

Lightweight tests that verify CLI flag recognition, output format,
and provider wiring without requiring a real database or model.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from linkedout.commands.embed_query import embed_query_command


@pytest.fixture
def runner():
    """Create a Click CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def mock_provider():
    """Return a mock embedding provider with a known vector."""
    prov = MagicMock()
    prov.embed_single.return_value = [0.1, -0.2, 0.3, 0.4, -0.5]
    return prov


class TestFlagRecognition:
    """Verify that CLI flags are recognized and parsed correctly."""

    def test_provider_openai_accepted(self, runner):
        """--provider openai should be a valid choice."""
        result = runner.invoke(embed_query_command, ['--provider', 'openai', '--help'])
        assert result.exit_code == 0

    def test_provider_local_accepted(self, runner):
        """--provider local should be a valid choice."""
        result = runner.invoke(embed_query_command, ['--provider', 'local', '--help'])
        assert result.exit_code == 0

    def test_provider_invalid_rejected(self, runner):
        """--provider invalid should be rejected by Click."""
        result = runner.invoke(embed_query_command, ['--provider', 'invalid', 'test'])
        assert result.exit_code != 0

    def test_format_json_accepted(self, runner):
        """--format json should be a valid choice."""
        result = runner.invoke(embed_query_command, ['--format', 'json', '--help'])
        assert result.exit_code == 0

    def test_format_raw_accepted(self, runner):
        """--format raw should be a valid choice."""
        result = runner.invoke(embed_query_command, ['--format', 'raw', '--help'])
        assert result.exit_code == 0

    def test_format_invalid_rejected(self, runner):
        """--format csv should be rejected by Click."""
        result = runner.invoke(embed_query_command, ['--format', 'csv', 'test'])
        assert result.exit_code != 0

    def test_text_argument_required(self, runner):
        """TEXT argument must be provided."""
        result = runner.invoke(embed_query_command, [])
        assert result.exit_code != 0


class TestHelpText:
    """Verify the command help text is useful."""

    def test_help_includes_description(self, runner):
        result = runner.invoke(embed_query_command, ['--help'])
        assert result.exit_code == 0
        assert 'embedding' in result.output.lower() or 'embed' in result.output.lower()

    def test_help_shows_all_options(self, runner):
        result = runner.invoke(embed_query_command, ['--help'])
        assert '--provider' in result.output
        assert '--format' in result.output


class TestJsonOutput:
    """Verify JSON output format (default)."""

    def test_outputs_valid_json_array(self, runner, mock_provider):
        """Default format should output a valid JSON array of floats."""
        with patch(
            'linkedout.commands.embed_query.get_embedding_provider',
            return_value=mock_provider,
        ):
            result = runner.invoke(embed_query_command, ['test query'])

        assert result.exit_code == 0
        parsed = json.loads(result.output.strip())
        assert isinstance(parsed, list)
        assert all(isinstance(v, float) for v in parsed)

    def test_outputs_correct_vector(self, runner, mock_provider):
        """Output should match the provider's embed_single return value."""
        with patch(
            'linkedout.commands.embed_query.get_embedding_provider',
            return_value=mock_provider,
        ):
            result = runner.invoke(embed_query_command, ['test query'])

        parsed = json.loads(result.output.strip())
        assert parsed == [0.1, -0.2, 0.3, 0.4, -0.5]

    def test_passes_text_to_provider(self, runner, mock_provider):
        """The TEXT argument should be passed directly to embed_single."""
        with patch(
            'linkedout.commands.embed_query.get_embedding_provider',
            return_value=mock_provider,
        ):
            runner.invoke(embed_query_command, ['distributed systems engineer'])

        mock_provider.embed_single.assert_called_once_with(
            'distributed systems engineer'
        )

    def test_no_prefix_added_to_text(self, runner, mock_provider):
        """Text should be passed as-is, no search_query: prefix."""
        with patch(
            'linkedout.commands.embed_query.get_embedding_provider',
            return_value=mock_provider,
        ):
            runner.invoke(embed_query_command, ['hello world'])

        mock_provider.embed_single.assert_called_once_with('hello world')


class TestRawOutput:
    """Verify raw output format."""

    def test_outputs_space_separated_floats(self, runner, mock_provider):
        """--format raw should output space-separated float values."""
        with patch(
            'linkedout.commands.embed_query.get_embedding_provider',
            return_value=mock_provider,
        ):
            result = runner.invoke(
                embed_query_command, ['--format', 'raw', 'test query']
            )

        assert result.exit_code == 0
        values = result.output.strip().split()
        assert len(values) == 5
        assert [float(v) for v in values] == [0.1, -0.2, 0.3, 0.4, -0.5]


class TestProviderSelection:
    """Verify --provider flag passes through to the factory."""

    def test_default_provider(self, runner, mock_provider):
        """Without --provider, factory is called with provider=None."""
        with patch(
            'linkedout.commands.embed_query.get_embedding_provider',
            return_value=mock_provider,
        ) as mock_factory:
            runner.invoke(embed_query_command, ['test'])

        mock_factory.assert_called_once_with(provider=None)

    def test_openai_provider(self, runner, mock_provider):
        """--provider openai passes 'openai' to the factory."""
        with patch(
            'linkedout.commands.embed_query.get_embedding_provider',
            return_value=mock_provider,
        ) as mock_factory:
            runner.invoke(embed_query_command, ['--provider', 'openai', 'test'])

        mock_factory.assert_called_once_with(provider='openai')

    def test_local_provider(self, runner, mock_provider):
        """--provider local passes 'local' to the factory."""
        with patch(
            'linkedout.commands.embed_query.get_embedding_provider',
            return_value=mock_provider,
        ) as mock_factory:
            runner.invoke(embed_query_command, ['--provider', 'local', 'test'])

        mock_factory.assert_called_once_with(provider='local')


class TestErrorHandling:
    """Verify errors from the provider are surfaced."""

    def test_provider_error_propagates(self, runner):
        """If embed_single raises, the command should fail with non-zero exit."""
        prov = MagicMock()
        prov.embed_single.side_effect = RuntimeError('Model not loaded')

        with patch(
            'linkedout.commands.embed_query.get_embedding_provider',
            return_value=prov,
        ):
            result = runner.invoke(embed_query_command, ['test'])

        assert result.exit_code != 0
