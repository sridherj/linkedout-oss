# SPDX-License-Identifier: Apache-2.0
"""Tests for linkedout.upgrade.update_checker — GitHub release checks and caching."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest

from linkedout.upgrade.update_checker import (
    CACHE_MAX_AGE_SECONDS,
    GITHUB_API_URL,
    UpdateInfo,
    _is_outdated,
    check_for_update,
    get_cached_update,
    save_update_cache,
)

_FAKE_REQUEST = httpx.Request('GET', GITHUB_API_URL)


@pytest.fixture()
def cache_file(tmp_path):
    """Redirect the cache file to a temp directory."""
    path = tmp_path / 'state' / 'update-check.json'
    with patch('linkedout.upgrade.update_checker.CACHE_FILE', path):
        yield path


def _github_response(tag: str = 'v0.2.0', status: int = 200) -> httpx.Response:
    """Build a mock GitHub API response with proper request attribute."""
    url = f'https://github.com/sridherj/linkedout-oss/releases/tag/{tag}'
    body = {'tag_name': tag, 'html_url': url}
    return httpx.Response(status, json=body, request=_FAKE_REQUEST)


def _make_update_info(
    latest: str = '0.2.0',
    current: str = '0.1.0',
    is_outdated: bool = True,
    checked_at: str | None = None,
) -> UpdateInfo:
    return UpdateInfo(
        latest_version=latest,
        current_version=current,
        release_url=f'https://github.com/sridherj/linkedout-oss/releases/tag/v{latest}',
        is_outdated=is_outdated,
        checked_at=checked_at or datetime.now(timezone.utc).isoformat(),
    )


def _patch_client(response=None, side_effect=None):
    """Return a patch context that replaces httpx.Client with a mock returning *response*."""
    p = patch('httpx.Client')

    class _Ctx:
        def __enter__(self_ctx):
            mock_cls = p.__enter__()
            instance = mock_cls.return_value
            instance.__enter__ = lambda s: s
            instance.__exit__ = lambda s, *a: None
            if side_effect is not None:
                instance.get.side_effect = side_effect
            else:
                instance.get.return_value = response
            self_ctx.mock_cls = mock_cls
            self_ctx.instance = instance
            return self_ctx

        def __exit__(self_ctx, *a):
            p.__exit__(*a)

    return _Ctx()


class TestIsOutdated:
    """Semver comparison via _is_outdated."""

    def test_newer_version_is_outdated(self):
        assert _is_outdated('0.1.0', '0.2.0') is True

    def test_same_version_not_outdated(self):
        assert _is_outdated('0.1.0', '0.1.0') is False

    def test_older_latest_not_outdated(self):
        assert _is_outdated('0.2.0', '0.1.0') is False

    def test_major_bump_is_outdated(self):
        assert _is_outdated('0.1.0', '1.0.0') is True

    def test_pre_release_less_than_release(self):
        # PEP 440: 1.0.0rc1 < 1.0.0
        assert _is_outdated('1.0.0rc1', '1.0.0') is True

    def test_release_not_outdated_vs_pre_release(self):
        assert _is_outdated('1.0.0', '1.0.0rc1') is False

    def test_invalid_version_returns_false(self):
        assert _is_outdated('0.1.0', 'not-a-version') is False

    def test_both_invalid_returns_false(self):
        assert _is_outdated('bad', 'also-bad') is False


class TestSaveAndReadCache:
    """Cache write/read round-trip."""

    def test_round_trip(self, cache_file):
        info = _make_update_info()
        save_update_cache(info)
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data['latest_version'] == '0.2.0'
        assert data['is_outdated'] is True

    def test_cache_creates_parent_dirs(self, cache_file):
        if cache_file.parent.exists():
            cache_file.parent.rmdir()
        info = _make_update_info()
        save_update_cache(info)
        assert cache_file.exists()


class TestGetCachedUpdate:
    """get_cached_update returns cached info only when fresh."""

    def test_returns_none_when_no_cache(self, cache_file):
        assert get_cached_update() is None

    def test_returns_info_when_fresh(self, cache_file):
        info = _make_update_info(checked_at=datetime.now(timezone.utc).isoformat())
        save_update_cache(info)
        result = get_cached_update()
        assert result is not None
        assert result.latest_version == '0.2.0'
        assert result.is_outdated is True

    def test_returns_none_when_stale(self, cache_file):
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=CACHE_MAX_AGE_SECONDS + 1)).isoformat()
        info = _make_update_info(checked_at=stale_time)
        save_update_cache(info)
        assert get_cached_update() is None

    def test_returns_none_on_corrupt_cache(self, cache_file):
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text('not json')
        assert get_cached_update() is None


class TestCheckForUpdate:
    """check_for_update — full flow with mocked HTTP."""

    def test_outdated_version(self, cache_file):
        with patch('linkedout.upgrade.update_checker.__version__', '0.1.0'), \
             _patch_client(_github_response('v0.2.0')):
            result = check_for_update()

        assert result is not None
        assert result.is_outdated is True
        assert result.latest_version == '0.2.0'
        assert result.current_version == '0.1.0'

    def test_up_to_date(self, cache_file):
        with patch('linkedout.upgrade.update_checker.__version__', '0.1.0'), \
             _patch_client(_github_response('v0.1.0')):
            result = check_for_update()

        assert result is not None
        assert result.is_outdated is False
        assert result.latest_version == '0.1.0'

    def test_pre_release_tag(self, cache_file):
        with patch('linkedout.upgrade.update_checker.__version__', '1.0.0'), \
             _patch_client(_github_response('v1.0.0rc1')):
            result = check_for_update()

        assert result is not None
        assert result.is_outdated is False

    def test_network_error_returns_none(self, cache_file):
        with _patch_client(side_effect=httpx.ConnectError('no internet')):
            result = check_for_update()

        assert result is None

    def test_http_error_returns_none(self, cache_file):
        resp = httpx.Response(403, request=_FAKE_REQUEST)
        with _patch_client(resp):
            result = check_for_update()

        assert result is None

    def test_caches_result_to_file(self, cache_file):
        with patch('linkedout.upgrade.update_checker.__version__', '0.1.0'), \
             _patch_client(_github_response('v0.2.0')):
            check_for_update()

        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data['latest_version'] == '0.2.0'

    def test_uses_cache_when_fresh(self, cache_file):
        """When cache is fresh, no HTTP call is made."""
        info = _make_update_info(checked_at=datetime.now(timezone.utc).isoformat())
        save_update_cache(info)

        with _patch_client(_github_response('v0.9.0')) as ctx:
            result = check_for_update()

        ctx.mock_cls.assert_not_called()
        assert result is not None
        assert result.latest_version == '0.2.0'

    def test_fetches_when_cache_stale(self, cache_file):
        """When cache is stale, a fresh HTTP call is made."""
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=CACHE_MAX_AGE_SECONDS + 1)).isoformat()
        info = _make_update_info(checked_at=stale_time)
        save_update_cache(info)

        with patch('linkedout.upgrade.update_checker.__version__', '0.1.0'), \
             _patch_client(_github_response('v0.3.0')):
            result = check_for_update()

        assert result is not None
        assert result.latest_version == '0.3.0'

    def test_strips_v_prefix_from_tag(self, cache_file):
        with patch('linkedout.upgrade.update_checker.__version__', '0.1.0'), \
             _patch_client(_github_response('v0.2.0')):
            result = check_for_update()

        assert result.latest_version == '0.2.0'  # not 'v0.2.0'


class TestGitHubToken:
    """GITHUB_TOKEN env var is used when available."""

    def test_token_sent_in_header(self, cache_file):
        with patch('linkedout.upgrade.update_checker.__version__', '0.1.0'), \
             patch.dict('os.environ', {'GITHUB_TOKEN': 'ghp_test123'}), \
             _patch_client(_github_response('v0.2.0')) as ctx:
            check_for_update()

        call_kwargs = ctx.instance.get.call_args
        headers = call_kwargs.kwargs.get('headers', {})
        assert headers.get('Authorization') == 'Bearer ghp_test123'

    def test_no_token_no_auth_header(self, cache_file):
        with patch('linkedout.upgrade.update_checker.__version__', '0.1.0'), \
             patch.dict('os.environ', {'GITHUB_TOKEN': ''}, clear=False), \
             _patch_client(_github_response('v0.2.0')) as ctx:
            check_for_update()

        call_kwargs = ctx.instance.get.call_args
        headers = call_kwargs.kwargs.get('headers', {})
        assert 'Authorization' not in headers
