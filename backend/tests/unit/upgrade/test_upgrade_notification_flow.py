# SPDX-License-Identifier: Apache-2.0
"""Integration tests for the full upgrade notification lifecycle.

These tests exercise multiple touchpoints (CLI banner, --check, --snooze)
together with shared file-system state (cache + snooze files) to verify
the notification experience is cohesive end-to-end.
"""
import json
from datetime import datetime, timedelta, timezone
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
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def state_dir(tmp_path):
    """Redirect both cache and snooze files to a temp directory."""
    cache_path = tmp_path / 'state' / 'update-check.json'
    snooze_path = tmp_path / 'state' / 'update-snooze.json'
    with patch('linkedout.upgrade.update_checker.CACHE_FILE', cache_path), \
         patch('linkedout.upgrade.update_checker.SNOOZE_FILE', snooze_path):
        yield {'cache': cache_path, 'snooze': snooze_path}


def _write_cache(cache_path, info: UpdateInfo) -> None:
    """Write an UpdateInfo to the cache file."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({
        'latest_version': info.latest_version,
        'current_version': info.current_version,
        'release_url': info.release_url,
        'is_outdated': info.is_outdated,
        'checked_at': info.checked_at,
    }, indent=2) + '\n')


class TestNotificationLifecycle:
    """Full flow: see banner -> snooze -> banner disappears -> snooze expires -> banner reappears."""

    def test_full_lifecycle(self, runner, state_dir):
        info = _make_update_info(is_outdated=True)
        _write_cache(state_dir['cache'], info)

        # Step 1: First command shows banner (reads from cache)
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=info):
            result = runner.invoke(cli, ['version'])
        assert 'LinkedOut v0.3.0 available (you have v0.2.0)' in result.output

        # Step 2: Snooze the update
        with patch('linkedout.upgrade.update_checker.check_for_update', return_value=info), \
             patch('linkedout.upgrade.update_checker.get_cached_update', return_value=info):
            result = runner.invoke(cli, ['upgrade', '--snooze'])
        assert 'snoozed for 24 hours' in result.output

        # Step 3: Next command — banner suppressed (snooze active)
        # check_for_update returns None when snoozed
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=info):
            result = runner.invoke(cli, ['version'])
        assert 'LinkedOut v0.3.0 available' not in result.output

        # Step 4: Fast-forward past snooze expiry
        snooze_data = json.loads(state_dir['snooze'].read_text())
        snooze_data['next_reminder'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        state_dir['snooze'].write_text(json.dumps(snooze_data))

        # Step 5: Banner reappears
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=info):
            result = runner.invoke(cli, ['version'])
        assert 'LinkedOut v0.3.0 available (you have v0.2.0)' in result.output


class TestUpgradeClearsNotification:
    """After a successful upgrade, the banner no longer shows."""

    def test_banner_gone_after_upgrade(self, runner, state_dir):
        outdated_info = _make_update_info(is_outdated=True)
        _write_cache(state_dir['cache'], outdated_info)

        # Step 1: Banner shows
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=outdated_info):
            result = runner.invoke(cli, ['version'])
        assert 'LinkedOut v0.3.0 available' in result.output

        # Step 2: Simulate upgrade completing — cache now reflects current version
        current_info = _make_update_info(is_outdated=False, latest='0.3.0', current='0.3.0')
        _write_cache(state_dir['cache'], current_info)

        # Step 3: No more banner
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=current_info):
            result = runner.invoke(cli, ['version'])
        assert 'LinkedOut v0.3.0 available' not in result.output


class TestCheckIndependentOfBanner:
    """--check gives truth regardless of snooze/cache state."""

    def test_check_bypasses_snooze(self, runner, state_dir):
        info = _make_update_info(is_outdated=True)
        _write_cache(state_dir['cache'], info)

        # Snooze the update
        from linkedout.upgrade.update_checker import snooze_update
        snooze_update('0.3.0')

        # Banner is suppressed (snoozed) — use version without --check
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=info):
            result = runner.invoke(cli, ['version'])
        assert 'LinkedOut v0.3.0 available' not in result.output

        # But --check still reports the update (force=True, skip_snooze=True)
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=info):
            result = runner.invoke(cli, ['version', '--check'])
        assert 'Update available' in result.output
        assert result.exit_code == 1


class TestSharedCacheState:
    """CLI banner and --check share the same cache file."""

    def test_check_populates_cache_for_banner(self, runner, state_dir):
        info = _make_update_info(is_outdated=True)

        def _fake_fetch_and_cache(**_kwargs):
            """Simulate _fetch_and_cache: return info AND write to cache."""
            from linkedout.upgrade.update_checker import save_update_cache
            save_update_cache(info)
            return info

        # Step 1: --check writes to cache (force=True hits API)
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', side_effect=_fake_fetch_and_cache):
            result = runner.invoke(cli, ['version', '--check'])
        assert 'Update available' in result.output

        # Step 2: CLI banner reads from cache (no API call needed)
        # Make _fetch_and_cache fail — banner should still show from cache
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', side_effect=Exception('API down')):
            result = runner.invoke(cli, ['version'])
        assert 'LinkedOut v0.3.0 available (you have v0.2.0)' in result.output


class TestNotificationFormatConsistency:
    """All notification messages follow the expected format patterns."""

    def test_cli_banner_format(self, runner, state_dir):
        info = _make_update_info(is_outdated=True, latest='0.3.0', current='0.2.0')
        _write_cache(state_dir['cache'], info)
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=info):
            result = runner.invoke(cli, ['version'])

        assert 'LinkedOut v0.3.0 available (you have v0.2.0). Run: linkedout upgrade' in result.output

    def test_check_outdated_format(self, runner):
        info = _make_update_info(is_outdated=True, latest='0.3.0', current='0.2.0')
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=info):
            result = runner.invoke(cli, ['version', '--check'])

        assert 'Update available: v0.2.0 -> v0.3.0. Run: linkedout upgrade' in result.output

    def test_check_current_format(self, runner):
        info = _make_update_info(is_outdated=False, latest='0.2.0', current='0.2.0')
        with patch('linkedout.upgrade.update_checker._fetch_and_cache', return_value=info):
            result = runner.invoke(cli, ['version', '--check'])

        assert 'Up to date (v0.2.0)' in result.output

    def test_snooze_confirmation_format(self, runner, state_dir):
        info = _make_update_info(is_outdated=True, latest='0.3.0', current='0.2.0')
        with patch('linkedout.upgrade.update_checker.check_for_update', return_value=info), \
             patch('linkedout.upgrade.update_checker.get_cached_update', return_value=info):
            result = runner.invoke(cli, ['upgrade', '--snooze'])

        assert "Update v0.3.0 snoozed for 24 hours. Run 'linkedout upgrade' when ready." in result.output
