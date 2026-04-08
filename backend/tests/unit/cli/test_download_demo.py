# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``linkedout download-demo`` CLI command.

Tests manifest parsing, checksum verification, cache hit/miss/force logic.
All HTTP calls are mocked.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from linkedout.commands.download_demo import (
    DEMO_BASE_URL,
    DEMO_RELEASE_TAG,
    _fetch_manifest,
    _format_size,
    _get_release_url,
    download_demo_command,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def valid_manifest():
    return {
        "name": "demo-seed.dump",
        "sha256": "abc123" * 10 + "ab",
        "size_bytes": 100_000_000,
    }


# ── Manifest parsing ─────────────────────────────────────────────────────────


class TestManifestParsing:

    def test_valid_manifest_parsed(self, valid_manifest):
        """Parse a valid demo manifest."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = valid_manifest

        with patch("linkedout.commands.download_demo.requests.get", return_value=resp):
            result = _fetch_manifest("https://example.com/release/demo-v1")

        assert result["name"] == "demo-seed.dump"
        assert "sha256" in result

    def test_manifest_missing_required_field_raises(self):
        """Manifest missing 'sha256' -> raises ClickException."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"name": "demo-seed.dump", "size_bytes": 100}

        with patch("linkedout.commands.download_demo.requests.get", return_value=resp):
            with pytest.raises(Exception, match="missing 'sha256'"):
                _fetch_manifest("https://example.com/release/demo-v1")

    def test_manifest_404_raises(self):
        """Manifest not found (404) -> raises clear error."""
        resp = MagicMock()
        resp.status_code = 404

        with patch("linkedout.commands.download_demo.requests.get", return_value=resp):
            with pytest.raises(Exception, match="Demo manifest not found"):
                _fetch_manifest("https://example.com/release/demo-v1")

    def test_manifest_invalid_json_raises(self):
        """Invalid JSON -> raises clear error."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = json.JSONDecodeError("bad", "", 0)

        with patch("linkedout.commands.download_demo.requests.get", return_value=resp):
            with pytest.raises(Exception, match="Manifest validation failed"):
                _fetch_manifest("https://example.com/release/demo-v1")


# ── URL construction ─────────────────────────────────────────────────────────


class TestURLConstruction:

    def test_default_url(self):
        """Default URL uses DEMO_RELEASE_TAG."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LINKEDOUT_DEMO_URL", None)
            url, tag = _get_release_url(None)
        assert url == f"{DEMO_BASE_URL}/{DEMO_RELEASE_TAG}"
        assert tag == DEMO_RELEASE_TAG

    def test_custom_version(self):
        """Explicit version overrides default tag."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LINKEDOUT_DEMO_URL", None)
            url, tag = _get_release_url("demo-v2")
        assert url == f"{DEMO_BASE_URL}/demo-v2"
        assert tag == "demo-v2"

    def test_env_var_overrides_url(self):
        """LINKEDOUT_DEMO_URL env var overrides base URL."""
        with patch.dict(os.environ, {"LINKEDOUT_DEMO_URL": "https://my-fork.example.com/releases"}):
            url, tag = _get_release_url(None)
        assert url == f"https://my-fork.example.com/releases/{DEMO_RELEASE_TAG}"


# ── Cache hit/miss/force logic ────────────────────────────────────────────────


class TestCacheLogic:

    def _invoke(self, runner, tmp_path, manifest, file_exists, checksum_match, force):
        """Helper to invoke download-demo with mocked HTTP and filesystem."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        dest = cache_dir / "demo-seed.dump"
        if file_exists:
            dest.write_bytes(b"existing data")

        args = []
        if force:
            args.append("--force")

        with patch("linkedout.commands.download_demo._get_cache_dir", return_value=cache_dir), \
             patch("linkedout.commands.download_demo._get_release_url") as mock_url, \
             patch("linkedout.commands.download_demo._fetch_manifest") as mock_manifest, \
             patch("linkedout.commands.download_demo.verify_checksum") as mock_verify, \
             patch("linkedout.commands.download_demo._download_file") as mock_download:

            mock_url.return_value = ("https://example.com/release/demo-v1", "demo-v1")
            mock_manifest.return_value = manifest

            if file_exists and checksum_match and not force:
                mock_verify.return_value = True
            else:
                # First call: cache check (miss), second call: post-download verify (pass)
                mock_verify.side_effect = [checksum_match, True] if file_exists else [True]

            # _download_file is mocked, so create the file it would produce
            def fake_download(url, d, size):
                d.write_bytes(b"downloaded data")

            mock_download.side_effect = fake_download

            result = runner.invoke(download_demo_command, args)

        return result, mock_download

    def test_cached_checksum_ok_skips(self, runner, tmp_path, valid_manifest):
        """File cached + checksum OK + no --force -> skip download."""
        result, mock_download = self._invoke(
            runner, tmp_path, valid_manifest,
            file_exists=True, checksum_match=True, force=False,
        )
        assert result.exit_code == 0
        assert "already cached" in result.output
        mock_download.assert_not_called()

    def test_cached_checksum_ok_force_downloads(self, runner, tmp_path, valid_manifest):
        """File cached + checksum OK + --force -> re-download."""
        result, mock_download = self._invoke(
            runner, tmp_path, valid_manifest,
            file_exists=True, checksum_match=True, force=True,
        )
        mock_download.assert_called_once()

    def test_cached_checksum_mismatch_downloads(self, runner, tmp_path, valid_manifest):
        """File cached + checksum mismatch -> re-download."""
        result, mock_download = self._invoke(
            runner, tmp_path, valid_manifest,
            file_exists=True, checksum_match=False, force=False,
        )
        assert "mismatched checksum" in result.output
        mock_download.assert_called_once()

    def test_not_cached_downloads(self, runner, tmp_path, valid_manifest):
        """File not cached -> download."""
        result, mock_download = self._invoke(
            runner, tmp_path, valid_manifest,
            file_exists=False, checksum_match=False, force=False,
        )
        mock_download.assert_called_once()


# ── Size formatting ──────────────────────────────────────────────────────────


class TestFormatSize:

    def test_bytes(self):
        assert _format_size(500) == "500 B"

    def test_kilobytes(self):
        assert _format_size(5_000) == "5 KB"

    def test_megabytes(self):
        assert _format_size(50_000_000) == "50 MB"

    def test_gigabytes(self):
        assert _format_size(1_500_000_000) == "1.5 GB"
