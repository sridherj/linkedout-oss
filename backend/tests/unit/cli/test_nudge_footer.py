# SPDX-License-Identifier: Apache-2.0
"""Unit tests for demo mode nudge footer on CLI output."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from linkedout.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestNudgeFooter:

    def test_nudge_appears_in_demo_mode(self, runner):
        """Nudge footer should appear after command output when demo mode is active."""
        with patch("linkedout.demo.is_demo_mode", return_value=True):
            result = runner.invoke(cli, ["version"])

        assert "Demo mode" in result.output
        assert "linkedout setup" in result.output

    def test_nudge_absent_when_not_demo(self, runner):
        """Nudge footer should not appear when demo mode is inactive."""
        with patch("linkedout.demo.is_demo_mode", return_value=False):
            result = runner.invoke(cli, ["version"])

        assert "Demo mode" not in result.output
