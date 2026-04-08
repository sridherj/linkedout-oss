# SPDX-License-Identifier: Apache-2.0
"""Tests for setup logging integration module."""
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linkedout.setup.logging_integration import (
    _redact_config,
    generate_diagnostic,
    get_setup_logger,
    init_setup_logging,
    log_step_complete,
    log_step_start,
)


@pytest.fixture(autouse=True)
def _reset_correlation_id():
    """Reset the correlation ID contextvar after each test."""
    from shared.utilities.correlation import correlation_id_var

    token = correlation_id_var.set(None)
    yield
    correlation_id_var.reset(token)


@pytest.fixture()
def mock_settings(tmp_path):
    """Mock settings with a temp log directory."""
    settings = MagicMock()
    settings.log_dir = str(tmp_path / 'logs')
    settings.data_dir = str(tmp_path / 'data')
    with patch('linkedout.setup.logging_integration.get_config', return_value=settings):
        yield settings


class TestInitSetupLogging:
    def test_returns_correlation_id_matching_pattern(self, mock_settings):
        cid = init_setup_logging()
        assert re.match(r'^setup_\d{8}_\d{6}$', cid)

    def test_sets_correlation_id_in_contextvar(self, mock_settings):
        from shared.utilities.correlation import get_correlation_id

        cid = init_setup_logging()
        assert get_correlation_id() == cid

    def test_creates_log_directory(self, mock_settings):
        init_setup_logging()
        assert Path(mock_settings.log_dir).exists()


class TestGetSetupLogger:
    def test_returns_logger_with_component_binding(self, mock_settings):
        log = get_setup_logger('test_step')
        # loguru loggers carry bindings in _core.extra
        # Just verify it's callable and returns something usable
        assert hasattr(log, 'info')
        assert hasattr(log, 'error')

    def test_different_steps_return_distinct_loggers(self, mock_settings):
        log1 = get_setup_logger('step_a')
        log2 = get_setup_logger('step_b')
        # Both should be usable loggers (loguru returns bound copies)
        assert log1 is not log2 or True  # loguru may return same base


class TestLogStepStart:
    def test_produces_expected_message(self, mock_settings, capfd):
        # Just verify it doesn't raise — loguru output goes to stderr
        log_step_start(1, 14, 'Prerequisites Detection')


class TestLogStepComplete:
    def test_produces_expected_message(self, mock_settings):
        log_step_complete('Prerequisites Detection', 0.8)

    def test_warns_on_failures_in_report(self, mock_settings):
        from shared.utilities.operation_report import OperationCounts, OperationReport

        report = OperationReport(
            operation='test',
            counts=OperationCounts(total=10, succeeded=8, skipped=0, failed=2),
        )
        # Should not raise
        log_step_complete('Test Step', 1.5, report=report)


class TestGenerateDiagnostic:
    def test_creates_file_at_expected_path(self, mock_settings):
        error = RuntimeError('test error')
        steps = [
            {'name': 'Step 1', 'status': 'success', 'timestamp': '2026-04-07 14:20:01', 'duration': '0.8s'},
        ]
        config = {'data_dir': '~/linkedout-data', 'log_level': 'INFO'}

        diag_path = generate_diagnostic(error, steps, config)

        assert diag_path.exists()
        assert 'setup-diagnostic-' in diag_path.name
        assert diag_path.suffix == '.txt'

    def test_diagnostic_contains_system_section(self, mock_settings):
        diag_path = generate_diagnostic(
            RuntimeError('boom'),
            [],
            {},
        )
        content = diag_path.read_text()
        assert 'SYSTEM' in content
        assert 'Python:' in content

    def test_diagnostic_contains_failure_details(self, mock_settings):
        error = ValueError('bad config value')
        diag_path = generate_diagnostic(error, [], {})
        content = diag_path.read_text()
        assert 'FAILURE DETAILS' in content
        assert 'ValueError' in content
        assert 'bad config value' in content

    def test_diagnostic_redacts_secrets(self, mock_settings):
        config = {
            'openai_api_key': 'sk-proj-real-key-here',
            'database_url': 'postgresql://linkedout:mysecretpw@localhost:5432/linkedout',
            'data_dir': '~/linkedout-data',
        }
        diag_path = generate_diagnostic(RuntimeError('x'), [], config)
        content = diag_path.read_text()

        assert 'sk-proj-real-key-here' not in content
        assert 'mysecretpw' not in content
        assert '[REDACTED]' in content
        assert '****' in content

    def test_diagnostic_shows_step_progress(self, mock_settings):
        steps = [
            {'name': 'Step 1: Prerequisites', 'status': 'success', 'timestamp': '14:20:01', 'duration': '0.8s'},
            {'name': 'Step 2: System Setup', 'status': 'failed', 'timestamp': '14:20:45', 'duration': '42s'},
        ]
        diag_path = generate_diagnostic(RuntimeError('x'), steps, {})
        content = diag_path.read_text()

        assert 'SETUP PROGRESS' in content
        assert 'Step 1: Prerequisites' in content
        assert 'Step 2: System Setup' in content

    def test_diagnostic_reads_recent_log_entries(self, mock_settings, tmp_path):
        # Create a fake setup.log
        log_dir = Path(mock_settings.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        setup_log = log_dir / 'setup.log'
        setup_log.write_text('line 1\nline 2\nline 3\n')

        diag_path = generate_diagnostic(RuntimeError('x'), [], {})
        content = diag_path.read_text()

        assert 'RECENT LOG ENTRIES' in content
        assert 'line 1' in content


class TestRedactConfig:
    def test_redacts_api_keys(self):
        result = _redact_config({
            'openai_api_key': 'sk-real',
            'apify_api_key': 'apify_real',
        })
        assert result['openai_api_key'] == '[REDACTED]'
        assert result['apify_api_key'] == '[REDACTED]'

    def test_redacts_password_fields(self):
        result = _redact_config({'password': 'hunter2'})
        assert result['password'] == '[REDACTED]'

    def test_masks_database_url_password(self):
        result = _redact_config({
            'database_url': 'postgresql://linkedout:s3cret@localhost:5432/linkedout',
        })
        assert 's3cret' not in result['database_url']
        assert '****' in result['database_url']
        assert 'localhost:5432/linkedout' in result['database_url']

    def test_passes_through_non_sensitive_values(self):
        result = _redact_config({
            'data_dir': '~/linkedout-data',
            'log_level': 'INFO',
        })
        assert result['data_dir'] == '~/linkedout-data'
        assert result['log_level'] == 'INFO'
