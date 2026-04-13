# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``linkedout download-seed`` CLI command.

Tests manifest parsing, checksum verification, URL construction,
skip-if-exists logic, and tier selection. All HTTP calls are mocked.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from linkedout.commands.download_seed import (
    DEFAULT_BASE_URL,
    _fetch_manifest,
    _format_size,
    _get_base_url,
    download_seed_command,
    get_release_url,
)
from shared.utils.checksum import compute_sha256, verify_checksum


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def valid_manifest():
    return {
        'version': '0.3.0',
        'created_at': '2026-01-01T00:00:00Z',
        'files': [
            {
                'name': 'seed.dump',
                'size_bytes': 50_000_000,
                'sha256': 'abc123' * 10 + 'ab',
                'table_counts': {'company': 237000},
            },
        ],
    }


# ── Manifest parsing and validation ─────────────────────────────────────────


class TestManifestParsing:

    def test_valid_manifest_parsed(self, valid_manifest):
        """Parse a valid manifest JSON -> correct structure."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = valid_manifest

        with patch('linkedout.commands.download_seed.requests.get', return_value=resp):
            result = _fetch_manifest('https://example.com/release/v1')

        assert result['version'] == '0.3.0'
        assert len(result['files']) == 1
        assert result['files'][0]['name'] == 'seed.dump'

    def test_manifest_missing_files_raises(self):
        """Manifest without 'files' array -> raises ClickException."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {'version': '1.0'}

        with patch('linkedout.commands.download_seed.requests.get', return_value=resp):
            with pytest.raises(Exception, match='missing or invalid'):
                _fetch_manifest('https://example.com/release/v1')

    def test_manifest_missing_required_field_raises(self):
        """Manifest file entry missing required field -> raises ClickException."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            'files': [{'name': 'seed.dump'}],
        }

        with patch('linkedout.commands.download_seed.requests.get', return_value=resp):
            with pytest.raises(Exception, match="missing 'sha256'"):
                _fetch_manifest('https://example.com/release/v1')

    def test_manifest_404_raises(self):
        """Manifest not found (404) -> raises clear error."""
        resp = MagicMock()
        resp.status_code = 404

        with patch('linkedout.commands.download_seed.requests.get', return_value=resp):
            with pytest.raises(Exception, match='Manifest not found'):
                _fetch_manifest('https://example.com/release/v1')

    def test_manifest_invalid_json_raises(self):
        """Manifest with invalid JSON -> raises clear error."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = json.JSONDecodeError('bad', '', 0)

        with patch('linkedout.commands.download_seed.requests.get', return_value=resp):
            with pytest.raises(Exception, match='Manifest validation failed'):
                _fetch_manifest('https://example.com/release/v1')


# ── Checksum verification ────────────────────────────────────────────────────


class TestChecksumVerification:

    def test_correct_checksum(self, tmp_path):
        """Correct checksum -> returns True."""
        f = tmp_path / 'test.dump'
        f.write_bytes(b'hello world')
        sha = compute_sha256(f)
        assert verify_checksum(f, sha) is True

    def test_incorrect_checksum(self, tmp_path):
        """Incorrect checksum -> returns False."""
        f = tmp_path / 'test.dump'
        f.write_bytes(b'hello world')
        assert verify_checksum(f, 'wrong_hash') is False

    def test_empty_file_checksum(self, tmp_path):
        """Empty file -> valid checksum (of empty content)."""
        f = tmp_path / 'empty.dump'
        f.write_bytes(b'')
        sha = compute_sha256(f)
        assert verify_checksum(f, sha) is True
        # SHA256 of empty string is a known constant
        assert sha == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'


# ── URL construction ─────────────────────────────────────────────────────────


class TestURLConstruction:

    def test_default_url(self):
        """Default URL -> uses GitHub releases URL."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('LINKEDOUT_SEED_URL', None)
            url = _get_base_url()
        assert 'github.com' in url
        assert 'sridherj/linkedout-oss' in url

    def test_env_var_overrides_url(self):
        """LINKEDOUT_SEED_URL env var overrides base URL."""
        with patch.dict(os.environ, {'LINKEDOUT_SEED_URL': 'https://my-fork.example.com/releases'}):
            url = _get_base_url()
        assert url == 'https://my-fork.example.com/releases'

    def test_version_appended_to_url(self):
        """Explicit version -> appended to base URL."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('LINKEDOUT_SEED_URL', None)
            url, version = get_release_url('seed-v0.1.0')
        assert url == f'{DEFAULT_BASE_URL}/seed-v0.1.0'
        assert version == 'seed-v0.1.0'

    def test_latest_version_from_github_api(self):
        """No version -> queries GitHub API for latest release."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {'tag_name': 'v0.2.0'}

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('LINKEDOUT_SEED_URL', None)
            os.environ.pop('GITHUB_TOKEN', None)
            with patch('linkedout.commands.download_seed.requests.get', return_value=resp):
                url, version = get_release_url(None)

        assert url == f'{DEFAULT_BASE_URL}/v0.2.0'
        assert version == '0.2.0'  # 'v' prefix stripped

    def test_rate_limit_raises(self):
        """GitHub API rate limit (403) -> raises clear error."""
        resp = MagicMock()
        resp.status_code = 403

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('LINKEDOUT_SEED_URL', None)
            with patch('linkedout.commands.download_seed.requests.get', return_value=resp):
                with pytest.raises(Exception, match='rate limit'):
                    get_release_url(None)


# ── Skip-if-exists logic ────────────────────────────────────────────────────


class TestSkipIfExists:

    def _mock_download_flow(self, runner, tmp_path, manifest, file_exists, checksum_match, force):
        """Helper to invoke download-seed with mocked HTTP and filesystem."""
        seed_dir = tmp_path / 'seed'
        seed_dir.mkdir()

        if file_exists:
            dest = seed_dir / 'seed.dump'
            dest.write_bytes(b'existing data')

        args = ['--output', str(seed_dir)]
        if force:
            args.append('--force')

        with patch('linkedout.commands.download_seed.get_release_url') as mock_url, \
             patch('linkedout.commands.download_seed._fetch_manifest') as mock_manifest, \
             patch('linkedout.commands.download_seed.verify_checksum') as mock_verify, \
             patch('linkedout.commands.download_seed._download_file') as mock_download, \
             patch('linkedout.commands.download_seed.OperationReport') as mock_report:

            mock_url.return_value = ('https://example.com/release/v1', '0.3.0')
            mock_manifest.return_value = manifest
            mock_verify.return_value = checksum_match

            # Make the post-download verify pass
            if not checksum_match or force:
                mock_verify.side_effect = [checksum_match, True]

            mock_report_instance = MagicMock()
            mock_report_instance.save.return_value = tmp_path / 'reports' / 'report.json'
            mock_report.return_value = mock_report_instance

            # Create the dest file for post-download stat()
            dest = seed_dir / 'seed.dump'
            if not dest.exists():
                dest.write_bytes(b'downloaded data')

            result = runner.invoke(download_seed_command, args)

        return result, mock_download

    def test_exists_checksum_matches_no_force_skips(self, runner, tmp_path, valid_manifest):
        """File exists + checksum matches + no --force -> skip."""
        result, mock_download = self._mock_download_flow(
            runner, tmp_path, valid_manifest,
            file_exists=True, checksum_match=True, force=False,
        )
        assert result.exit_code == 0
        assert 'already downloaded' in result.output
        mock_download.assert_not_called()

    def test_exists_checksum_matches_force_downloads(self, runner, tmp_path, valid_manifest):
        """File exists + checksum matches + --force -> download."""
        result, mock_download = self._mock_download_flow(
            runner, tmp_path, valid_manifest,
            file_exists=True, checksum_match=True, force=True,
        )
        mock_download.assert_called_once()

    def test_exists_checksum_mismatch_downloads(self, runner, tmp_path, valid_manifest):
        """File exists + checksum mismatch -> download."""
        result, mock_download = self._mock_download_flow(
            runner, tmp_path, valid_manifest,
            file_exists=True, checksum_match=False, force=False,
        )
        assert 'mismatched checksum' in result.output
        mock_download.assert_called_once()

    def test_not_exists_downloads(self, runner, tmp_path, valid_manifest):
        """File doesn't exist -> download."""
        result, mock_download = self._mock_download_flow(
            runner, tmp_path, valid_manifest,
            file_exists=False, checksum_match=False, force=False,
        )
        mock_download.assert_called_once()


# ── Size formatting ──────────────────────────────────────────────────────────


class TestFormatSize:

    def test_bytes(self):
        assert _format_size(500) == '500 B'

    def test_kilobytes(self):
        assert _format_size(5_000) == '5 KB'

    def test_megabytes(self):
        assert _format_size(50_000_000) == '50 MB'

    def test_gigabytes(self):
        assert _format_size(1_500_000_000) == '1.5 GB'
