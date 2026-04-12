# SPDX-License-Identifier: Apache-2.0
"""Tests for ``linkedout version --check`` flag."""
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from linkedout.cli import cli
from linkedout.upgrade.update_checker import UpdateInfo


def _make_update_info(
    is_outdated: bool = True,
    latest: str = '0.3.0',
    current: str = '0.2.0',
) -> UpdateInfo:
    return UpdateInfo(
        latest_version=latest,
        current_version=current,
        release_url=f'https://github.com/sridherj/linkedout-oss/releases/tag/v{latest}',
        is_outdated=is_outdated,
        checked_at='2026-04-12T00:00:00+00:00',
    )


@pytest.fixture()
def runner():
    return CliRunner()


_PATCH_CHECK = 'linkedout.upgrade.update_checker.check_for_update'


class TestVersionCheckFlag:
    """``linkedout version --check`` flag."""

    def test_check_outdated(self, runner):
        info = _make_update_info(is_outdated=True)
        with patch(_PATCH_CHECK, return_value=info):
            result = runner.invoke(cli, ['version', '--check'])

        assert result.exit_code == 1
        assert 'Update available: v0.2.0 -> v0.3.0. Run: linkedout upgrade' in result.output

    def test_check_up_to_date(self, runner):
        info = _make_update_info(is_outdated=False, latest='0.2.0', current='0.2.0')
        with patch(_PATCH_CHECK, return_value=info):
            result = runner.invoke(cli, ['version', '--check'])

        assert result.exit_code == 0
        assert 'Up to date (v0.2.0)' in result.output

    def test_check_json_outdated(self, runner):
        info = _make_update_info(is_outdated=True)
        with patch(_PATCH_CHECK, return_value=info):
            result = runner.invoke(cli, ['version', '--check', '--json'])

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data['update_available'] is True
        assert data['current'] == '0.2.0'
        assert data['latest'] == '0.3.0'
        assert 'release_url' in data

    def test_check_json_up_to_date(self, runner):
        info = _make_update_info(is_outdated=False, latest='0.2.0', current='0.2.0')
        with patch(_PATCH_CHECK, return_value=info):
            result = runner.invoke(cli, ['version', '--check', '--json'])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['update_available'] is False

    def test_check_network_error(self, runner):
        with patch(_PATCH_CHECK, return_value=None):
            result = runner.invoke(cli, ['version', '--check'])

        assert result.exit_code == 1
        assert 'Could not check for updates' in result.output

    def test_check_bypasses_snooze(self, runner):
        info = _make_update_info(is_outdated=True)
        with patch(_PATCH_CHECK, return_value=info) as mock_check:
            runner.invoke(cli, ['version', '--check'])

        mock_check.assert_called_once_with(force=True, skip_snooze=True)

    def test_version_without_check_unchanged(self, runner):
        with patch(_PATCH_CHECK, return_value=None):
            result = runner.invoke(cli, ['version'])

        assert result.exit_code == 0
        # Normal version output includes version string, not update check output
        assert 'Up to date' not in result.output
        assert 'Update available' not in result.output
        assert 'Could not check' not in result.output
