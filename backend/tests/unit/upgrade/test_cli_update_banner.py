# SPDX-License-Identifier: Apache-2.0
"""Tests for the CLI update notification banner in the result_callback."""
from unittest.mock import MagicMock, patch

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
_PATCH_DEMO = 'linkedout.demo.is_demo_mode'


class TestUpdateBanner:
    """CLI result_callback update notification banner."""

    def test_banner_shown_when_outdated(self, runner):
        info = _make_update_info(is_outdated=True)
        with patch(_PATCH_CHECK, return_value=info):
            result = runner.invoke(cli, ['version'])

        assert 'LinkedOut v0.3.0 available (you have v0.2.0). Run: linkedout upgrade' in result.output

    def test_no_banner_when_up_to_date(self, runner):
        info = _make_update_info(is_outdated=False, latest='0.2.0', current='0.2.0')
        with patch(_PATCH_CHECK, return_value=info):
            result = runner.invoke(cli, ['version'])

        assert 'available' not in result.output

    def test_no_banner_when_check_returns_none(self, runner):
        with patch(_PATCH_CHECK, return_value=None):
            result = runner.invoke(cli, ['version'])

        assert 'available' not in result.output
        assert result.exit_code == 0

    def test_no_banner_when_check_raises(self, runner):
        with patch(_PATCH_CHECK, side_effect=Exception('boom')):
            result = runner.invoke(cli, ['version'])

        assert 'available' not in result.output
        assert result.exit_code == 0

    def test_no_banner_during_upgrade_command(self, runner):
        with patch('linkedout.upgrade.upgrader.Upgrader') as mock_upgrader_cls:
            mock_upgrader = MagicMock()
            mock_upgrader.detect_install_type.return_value = 'not_git'
            mock_upgrader_cls.return_value = mock_upgrader
            with patch(_PATCH_CHECK) as mock_check:
                runner.invoke(cli, ['upgrade'])

            mock_check.assert_not_called()

    def test_demo_nudge_and_banner_coexist(self, runner):
        info = _make_update_info(is_outdated=True)
        with patch(_PATCH_DEMO, return_value=True), \
             patch(_PATCH_CHECK, return_value=info):
            result = runner.invoke(cli, ['version'])

        output = result.output
        demo_pos = output.find('Demo mode')
        banner_pos = output.find('LinkedOut v0.3.0 available')
        assert demo_pos != -1, 'Demo nudge should appear'
        assert banner_pos != -1, 'Update banner should appear'
        assert demo_pos < banner_pos, 'Demo nudge should appear before update banner'
