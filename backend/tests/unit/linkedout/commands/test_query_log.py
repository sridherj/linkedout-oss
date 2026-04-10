# SPDX-License-Identifier: Apache-2.0
"""Tests for the ``linkedout log-query`` CLI command."""
from __future__ import annotations

import json

from click.testing import CliRunner

from linkedout.commands.query_log import log_query_command


class TestLogQueryCommand:
    """Tests for log_query_command via Click test runner."""

    def test_log_query_command_creates_jsonl(self, tmp_path, monkeypatch):
        """Invoking log-query creates a JSONL entry with correct fields."""
        monkeypatch.setenv('LINKEDOUT_DATA_DIR', str(tmp_path))

        runner = CliRunner()
        result = runner.invoke(
            log_query_command,
            ['who do I know at Stripe?', '--type', 'company_lookup', '--results', '5'],
        )

        assert result.exit_code == 0, result.output

        # Find the JSONL file
        queries_dir = tmp_path / 'queries'
        jsonl_files = list(queries_dir.glob('*.jsonl'))
        assert len(jsonl_files) == 1

        entries = [json.loads(line) for line in jsonl_files[0].read_text().splitlines()]
        assert len(entries) == 1

        entry = entries[0]
        assert entry['query_text'] == 'who do I know at Stripe?'
        assert entry['query_type'] == 'company_lookup'
        assert entry['result_count'] == 5
        assert entry['query_id'].startswith('q_')

    def test_log_query_command_default_type(self, tmp_path, monkeypatch):
        """Omitting --type defaults to 'general'."""
        monkeypatch.setenv('LINKEDOUT_DATA_DIR', str(tmp_path))

        runner = CliRunner()
        result = runner.invoke(log_query_command, ['test query'])

        assert result.exit_code == 0, result.output

        queries_dir = tmp_path / 'queries'
        jsonl_files = list(queries_dir.glob('*.jsonl'))
        assert len(jsonl_files) == 1

        entry = json.loads(jsonl_files[0].read_text().splitlines()[0])
        assert entry['query_type'] == 'general'
        assert entry['result_count'] == 0
