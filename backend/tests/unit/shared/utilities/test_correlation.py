# SPDX-License-Identifier: Apache-2.0
"""Tests for correlation ID generation and contextvar propagation."""
from __future__ import annotations

import re

import pytest
from loguru import logger

from shared.utilities.correlation import (
    correlation_id_var,
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
)


class TestGenerateCorrelationId:
    """Tests for generate_correlation_id()."""

    def test_default_prefix(self):
        """Default prefix is 'req'."""
        cid = generate_correlation_id()
        assert cid.startswith('req_')

    def test_custom_prefix(self):
        """Custom prefix is applied correctly."""
        cid = generate_correlation_id('cli')
        assert cid.startswith('cli_')

    def test_format_matches_spec(self):
        """Output matches {prefix}_{12chars} format."""
        cid = generate_correlation_id('req')
        # prefix + underscore + 12 chars
        match = re.match(r'^req_[A-Za-z0-9_-]{12}$', cid)
        assert match is not None, f"Correlation ID '{cid}' doesn't match expected format"

    def test_uniqueness(self):
        """Two generated IDs should not collide."""
        ids = {generate_correlation_id() for _ in range(100)}
        assert len(ids) == 100


class TestCorrelationIdContextvar:
    """Tests for get/set_correlation_id via contextvars."""

    @pytest.fixture(autouse=True)
    def _reset_contextvar(self):
        """Reset the contextvar before and after each test."""
        token = correlation_id_var.set(None)
        yield
        correlation_id_var.reset(token)

    def test_default_is_none(self):
        """Without setting, get_correlation_id returns None."""
        assert get_correlation_id() is None

    def test_roundtrip(self):
        """set then get returns the same value."""
        set_correlation_id('req_abc123def456')
        assert get_correlation_id() == 'req_abc123def456'

    def test_overwrite(self):
        """Setting a new value overwrites the previous one."""
        set_correlation_id('req_first')
        set_correlation_id('req_second')
        assert get_correlation_id() == 'req_second'


class TestCorrelationIdInLogRecords:
    """Tests that correlation ID auto-binds into log records when set."""

    @pytest.fixture(autouse=True)
    def _reset_contextvar(self):
        """Reset the contextvar before and after each test."""
        token = correlation_id_var.set(None)
        yield
        correlation_id_var.reset(token)

    def test_correlation_id_appears_in_log_extra(self):
        """When a correlation ID is set, it appears in the log record extras."""
        # Arrange
        set_correlation_id('req_test123test')
        captured_extras: list[dict] = []

        def capture_sink(message):
            captured_extras.append(dict(message.record['extra']))

        sink_id = logger.add(capture_sink, level='DEBUG')

        try:
            # Act
            logger.info('test message with correlation')
        finally:
            logger.remove(sink_id)

        # Assert
        assert len(captured_extras) >= 1
        assert captured_extras[0].get('correlation_id') == 'req_test123test'

    def test_no_correlation_id_when_unset(self):
        """When no correlation ID is set, the extra field is empty string."""
        captured_extras: list[dict] = []

        def capture_sink(message):
            captured_extras.append(dict(message.record['extra']))

        sink_id = logger.add(capture_sink, level='DEBUG')

        try:
            logger.info('test message without correlation')
        finally:
            logger.remove(sink_id)

        assert len(captured_extras) >= 1
        assert captured_extras[0].get('correlation_id') == ''
