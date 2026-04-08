# SPDX-License-Identifier: Apache-2.0
"""Tests for linkedout.upgrade.extension_updater — Chrome extension upgrade support."""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from linkedout.upgrade.extension_updater import (
    check_extension_installed,
    download_extension_zip,
    fetch_expected_checksum,
    get_sideload_instructions,
    verify_checksum,
)


class TestCheckExtensionInstalled:
    """check_extension_installed() detects prior extension installation."""

    def test_returns_true_when_directory_has_files(self, tmp_path: Path):
        ext_dir = tmp_path / 'extension'
        ext_dir.mkdir()
        (ext_dir / 'linkedout-extension-v0.1.0.zip').write_bytes(b'fake')

        with patch('linkedout.upgrade.extension_updater._EXTENSION_DIR', ext_dir):
            assert check_extension_installed() is True

    def test_returns_false_when_directory_missing(self, tmp_path: Path):
        ext_dir = tmp_path / 'extension'  # does not exist

        with patch('linkedout.upgrade.extension_updater._EXTENSION_DIR', ext_dir):
            assert check_extension_installed() is False

    def test_returns_false_when_directory_empty(self, tmp_path: Path):
        ext_dir = tmp_path / 'extension'
        ext_dir.mkdir()

        with patch('linkedout.upgrade.extension_updater._EXTENSION_DIR', ext_dir):
            assert check_extension_installed() is False


class TestDownloadExtensionZip:
    """download_extension_zip() downloads and saves the extension."""

    def test_successful_download(self, tmp_path: Path):
        content = b'PK\x03\x04fake-zip-content'

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_bytes = MagicMock(return_value=iter([content]))
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.upgrade.extension_updater.httpx.Client', return_value=mock_client):
            result = download_extension_zip('0.2.0', extension_dir=tmp_path)

        assert result == tmp_path / 'linkedout-extension-v0.2.0.zip'
        assert result.exists()
        assert result.read_bytes() == content

    def test_creates_directory_if_missing(self, tmp_path: Path):
        dest = tmp_path / 'new_dir'
        content = b'zip-data'

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_bytes = MagicMock(return_value=iter([content]))
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.upgrade.extension_updater.httpx.Client', return_value=mock_client):
            result = download_extension_zip('0.2.0', extension_dir=dest)

        assert dest.exists()
        assert result.exists()

    def test_network_error_raises(self, tmp_path: Path):
        mock_client = MagicMock()
        mock_client.stream = MagicMock(
            side_effect=httpx.ConnectError('Could not connect')
        )
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.upgrade.extension_updater.httpx.Client', return_value=mock_client):
            with pytest.raises(httpx.ConnectError):
                download_extension_zip('0.2.0', extension_dir=tmp_path)

    def test_http_error_raises(self, tmp_path: Path):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                'Not Found',
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )
        )
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.upgrade.extension_updater.httpx.Client', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                download_extension_zip('0.2.0', extension_dir=tmp_path)


class TestFetchExpectedChecksum:
    """fetch_expected_checksum() retrieves the .sha256 file."""

    def test_returns_checksum(self):
        expected = 'abcdef1234567890' * 4  # 64 hex chars
        mock_resp = MagicMock()
        mock_resp.text = f'{expected}  linkedout-extension-v0.2.0.zip\n'
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get = MagicMock(return_value=mock_resp)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.upgrade.extension_updater.httpx.Client', return_value=mock_client):
            result = fetch_expected_checksum('0.2.0')

        assert result == expected

    def test_returns_none_on_error(self):
        mock_client = MagicMock()
        mock_client.get = MagicMock(side_effect=httpx.ConnectError('fail'))
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.upgrade.extension_updater.httpx.Client', return_value=mock_client):
            result = fetch_expected_checksum('0.2.0')

        assert result is None

    def test_handles_bare_checksum_format(self):
        expected = 'a' * 64
        mock_resp = MagicMock()
        mock_resp.text = f'{expected}\n'
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get = MagicMock(return_value=mock_resp)
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.upgrade.extension_updater.httpx.Client', return_value=mock_client):
            result = fetch_expected_checksum('0.2.0')

        assert result == expected


class TestVerifyChecksum:
    """verify_checksum() compares SHA256 hashes."""

    def test_matching_checksum(self, tmp_path: Path):
        content = b'test file content'
        file_path = tmp_path / 'test.zip'
        file_path.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()

        assert verify_checksum(file_path, expected) is True

    def test_mismatched_checksum(self, tmp_path: Path):
        file_path = tmp_path / 'test.zip'
        file_path.write_bytes(b'actual content')

        assert verify_checksum(file_path, 'wrong' * 16) is False

    def test_case_insensitive_comparison(self, tmp_path: Path):
        content = b'test data'
        file_path = tmp_path / 'test.zip'
        file_path.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest().upper()

        assert verify_checksum(file_path, expected) is True


class TestGetSideloadInstructions:
    """get_sideload_instructions() returns proper text."""

    def test_returns_non_empty_string(self):
        result = get_sideload_instructions()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_key_phrases(self):
        result = get_sideload_instructions()
        assert 'chrome://extensions' in result
        assert 'Remove the old LinkedOut extension' in result
        assert 'Drag and drop' in result
        assert 'Load unpacked' in result


class TestExtensionUpdateInUpgrader:
    """Extension step integration with Upgrader.update_extension()."""

    def _make_upgrader(self, tmp_path: Path):
        from linkedout.upgrade.upgrader import Upgrader

        git_dir = tmp_path / '.git'
        git_dir.mkdir()
        with patch('linkedout.upgrade.upgrader.__version__', '0.1.0'):
            u = Upgrader(repo_root=tmp_path)
            u._from_version = '0.1.0'
        return u

    def test_skipped_when_not_installed(self, tmp_path: Path):
        upgrader = self._make_upgrader(tmp_path)

        with patch(
            'linkedout.upgrade.upgrader.check_extension_installed',
            return_value=False,
        ):
            result = upgrader.update_extension('0.2.0')

        assert result is None

    def test_success_when_installed(self, tmp_path: Path):
        upgrader = self._make_upgrader(tmp_path)
        zip_path = tmp_path / 'ext.zip'
        zip_path.write_bytes(b'fake')

        with (
            patch(
                'linkedout.upgrade.upgrader.check_extension_installed',
                return_value=True,
            ),
            patch(
                'linkedout.upgrade.upgrader.download_extension_zip',
                return_value=zip_path,
            ),
            patch(
                'linkedout.upgrade.upgrader.fetch_expected_checksum',
                return_value=None,
            ),
        ):
            result = upgrader.update_extension('0.2.0')

        assert result is not None
        assert result.status == 'success'
        assert 'Saved to' in result.detail
        assert 'chrome://extensions' in result.detail

    def test_download_failure_is_non_blocking(self, tmp_path: Path):
        upgrader = self._make_upgrader(tmp_path)

        with (
            patch(
                'linkedout.upgrade.upgrader.check_extension_installed',
                return_value=True,
            ),
            patch(
                'linkedout.upgrade.upgrader.download_extension_zip',
                side_effect=httpx.ConnectError('Network error'),
            ),
        ):
            result = upgrader.update_extension('0.2.0')

        assert result is not None
        assert result.status == 'failed'
        assert 'core upgrade succeeded' in result.detail

    def test_checksum_mismatch_reports_failure(self, tmp_path: Path):
        upgrader = self._make_upgrader(tmp_path)
        zip_path = tmp_path / 'ext.zip'
        zip_path.write_bytes(b'fake')

        with (
            patch(
                'linkedout.upgrade.upgrader.check_extension_installed',
                return_value=True,
            ),
            patch(
                'linkedout.upgrade.upgrader.download_extension_zip',
                return_value=zip_path,
            ),
            patch(
                'linkedout.upgrade.upgrader.fetch_expected_checksum',
                return_value='wrong' * 16,
            ),
            patch(
                'linkedout.upgrade.upgrader.verify_checksum',
                return_value=False,
            ),
        ):
            result = upgrader.update_extension('0.2.0')

        assert result is not None
        assert result.status == 'failed'
        assert 'checksum' in result.detail.lower()

    def test_extension_step_in_run_upgrade_when_installed(self, tmp_path: Path):
        """Extension step appears in upgrade report when extension is installed."""
        from linkedout.upgrade.update_checker import UpdateInfo

        upgrader = self._make_upgrader(tmp_path)
        zip_path = tmp_path / 'ext.zip'
        zip_path.write_bytes(b'fake')

        update_info = UpdateInfo(
            latest_version='0.2.0',
            current_version='0.1.0',
            release_url='https://github.com/sridherj/linkedout-oss/releases/tag/v0.2.0',
            is_outdated=True,
            checked_at='2026-04-08T14:30:00+00:00',
        )

        def subprocess_ok(*args, **kwargs):
            from subprocess import CompletedProcess
            return CompletedProcess(args=[], returncode=0, stdout='', stderr='')

        with (
            patch('subprocess.run', side_effect=subprocess_ok),
            patch('linkedout.upgrade.upgrader.check_for_update', return_value=update_info),
            patch('linkedout.upgrade.upgrader.run_version_migrations', return_value=[]),
            patch('linkedout.upgrade.upgrader.parse_changelog', return_value=''),
            patch('linkedout.upgrade.upgrader.write_upgrade_report', return_value=tmp_path / 'r.json'),
            patch.object(upgrader, '_save_last_upgrade_version'),
            patch('linkedout.upgrade.upgrader.check_extension_installed', return_value=True),
            patch('linkedout.upgrade.upgrader.download_extension_zip', return_value=zip_path),
            patch('linkedout.upgrade.upgrader.fetch_expected_checksum', return_value=None),
        ):
            report = upgrader.run_upgrade()

        ext_steps = [s for s in report.steps if s.step == 'extension_update']
        assert len(ext_steps) == 1
        assert ext_steps[0].status == 'success'
        assert 'Re-sideload' in report.next_steps[-1]

    def test_extension_step_skipped_in_run_upgrade_when_not_installed(self, tmp_path: Path):
        """Extension step does not appear when extension is not installed."""
        from linkedout.upgrade.update_checker import UpdateInfo

        upgrader = self._make_upgrader(tmp_path)

        update_info = UpdateInfo(
            latest_version='0.2.0',
            current_version='0.1.0',
            release_url='https://github.com/sridherj/linkedout-oss/releases/tag/v0.2.0',
            is_outdated=True,
            checked_at='2026-04-08T14:30:00+00:00',
        )

        def subprocess_ok(*args, **kwargs):
            from subprocess import CompletedProcess
            return CompletedProcess(args=[], returncode=0, stdout='', stderr='')

        with (
            patch('subprocess.run', side_effect=subprocess_ok),
            patch('linkedout.upgrade.upgrader.check_for_update', return_value=update_info),
            patch('linkedout.upgrade.upgrader.run_version_migrations', return_value=[]),
            patch('linkedout.upgrade.upgrader.parse_changelog', return_value=''),
            patch('linkedout.upgrade.upgrader.write_upgrade_report', return_value=tmp_path / 'r.json'),
            patch.object(upgrader, '_save_last_upgrade_version'),
            patch('linkedout.upgrade.upgrader.check_extension_installed', return_value=False),
        ):
            report = upgrader.run_upgrade()

        ext_steps = [s for s in report.steps if s.step == 'extension_update']
        assert len(ext_steps) == 0
        assert not any('extension' in s.lower() for s in report.next_steps)
