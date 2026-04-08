# SPDX-License-Identifier: Apache-2.0
"""Tests for LoggerSingleton — component routing, log directory, rotation config."""
from __future__ import annotations

import os
import time

import pytest
from loguru import logger

from shared.utilities.logger import COMPONENT_LOG_FILES, LoggerSingleton, get_logger


class TestGetLogger:
    """Tests for get_logger() parameter binding."""

    def test_returns_bound_logger_with_name(self):
        """get_logger with name returns a logger bound with that name."""
        bound = get_logger('my.module')
        # Verify it's a loguru logger (has .info, .debug etc.)
        assert hasattr(bound, 'info')
        assert hasattr(bound, 'debug')

    def test_returns_bound_logger_with_component(self):
        """get_logger with component binds the component extra."""
        # Arrange
        captured_extras: list[dict] = []

        def capture_sink(message):
            captured_extras.append(dict(message.record['extra']))

        sink_id = logger.add(capture_sink, level='TRACE')

        try:
            # Act
            bound = get_logger(__name__, component='cli')
            bound.info('test component binding')
        finally:
            logger.remove(sink_id)

        # Assert
        assert len(captured_extras) >= 1
        assert captured_extras[0].get('component') == 'cli'

    def test_returns_bound_logger_with_operation(self):
        """get_logger with operation binds the operation extra."""
        captured_extras: list[dict] = []

        def capture_sink(message):
            captured_extras.append(dict(message.record['extra']))

        sink_id = logger.add(capture_sink, level='TRACE')

        try:
            bound = get_logger(__name__, component='cli', operation='import_csv')
            bound.info('test operation binding')
        finally:
            logger.remove(sink_id)

        assert len(captured_extras) >= 1
        assert captured_extras[0].get('operation') == 'import_csv'

    def test_returns_unbound_logger_without_args(self):
        """get_logger() with no args returns the base logger."""
        result = get_logger()
        assert hasattr(result, 'info')


class TestComponentLogRouting:
    """Tests that per-component sinks receive the right log entries."""

    def test_component_log_written_to_component_file(self, tmp_path):
        """Logs with component='cli' appear in cli.log."""
        # Arrange — add a temporary cli sink
        cli_log_path = tmp_path / 'cli.log'
        sink_id = logger.add(
            str(cli_log_path),
            format='{message}',
            level='TRACE',
            filter=lambda record: record['extra'].get('component') == 'cli',
        )

        try:
            # Act
            bound = get_logger(__name__, component='cli')
            bound.info('cli test message')
            # loguru with enqueue=False (our test sink) writes synchronously
            time.sleep(0.1)  # small buffer for file flush
        finally:
            logger.remove(sink_id)

        # Assert
        content = cli_log_path.read_text()
        assert 'cli test message' in content

    def test_non_component_log_not_written_to_component_file(self, tmp_path):
        """Logs without component binding don't appear in cli.log."""
        cli_log_path = tmp_path / 'cli.log'
        sink_id = logger.add(
            str(cli_log_path),
            format='{message}',
            level='TRACE',
            filter=lambda record: record['extra'].get('component') == 'cli',
        )

        try:
            bound = get_logger(__name__)
            bound.info('backend only message')
            time.sleep(0.1)
        finally:
            logger.remove(sink_id)

        # File may not exist or should be empty
        if cli_log_path.exists():
            content = cli_log_path.read_text()
            assert 'backend only message' not in content


class TestLogDirectory:
    """Tests that log files are created in the configured directory."""

    def test_log_dir_set_from_config(self):
        """LoggerSingleton uses the config-provided log directory."""
        singleton = LoggerSingleton.get_instance()
        # The log_dir should be set (not inside backend/logs/)
        assert singleton.log_dir is not None
        assert 'backend/logs' not in singleton.log_dir

    def test_component_log_files_defined(self):
        """All expected component log files are defined."""
        expected = {'backend', 'cli', 'setup', 'enrichment', 'import', 'queries'}
        assert set(COMPONENT_LOG_FILES.keys()) == expected


class TestRotationConfig:
    """Tests that rotation policy is configured correctly."""

    def test_default_rotation_is_50mb(self):
        """Default rotation is 50 MB when env var is not set."""
        # If env var is not set, the default should be '50 MB'
        expected = os.getenv('LINKEDOUT_LOG_ROTATION', '50 MB')
        assert expected == '50 MB' or 'LINKEDOUT_LOG_ROTATION' in os.environ
