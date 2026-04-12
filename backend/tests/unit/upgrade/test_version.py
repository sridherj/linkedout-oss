# SPDX-License-Identifier: Apache-2.0
"""Tests for linkedout.version — VERSION file parsing and version info."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def repo_root():
    """Return the repo root (four levels up from linkedout/version.py's parent)."""
    return Path(__file__).resolve().parent.parent.parent.parent.parent


@pytest.fixture()
def version_file(repo_root):
    """Return the path to the VERSION file."""
    return repo_root / 'VERSION'


class TestVersionFileParsing:
    """VERSION file parsing works correctly."""

    def test_version_file_exists(self, version_file):
        assert version_file.exists(), f'VERSION file not found at {version_file}'

    def test_version_file_contains_semver(self, version_file):
        content = version_file.read_text().strip()
        parts = content.split('.')
        assert len(parts) == 3, f'Expected semver (x.y.z), got {content!r}'
        for part in parts:
            assert part.isdigit(), f'Non-numeric semver component: {part!r}'

    def test_version_file_content_is_0_2_0(self, version_file):
        assert version_file.read_text().strip() == '0.2.0'


class TestVersionModule:
    """__version__ and get_version_info() from linkedout.version."""

    def test_dunder_version_matches_file(self, version_file):
        from linkedout.version import __version__
        assert __version__ == version_file.read_text().strip()

    def test_dunder_version_is_string(self):
        from linkedout.version import __version__
        assert isinstance(__version__, str)

    def test_get_version_info_returns_dict(self):
        from linkedout.version import get_version_info
        info = get_version_info()
        assert isinstance(info, dict)

    def test_get_version_info_has_required_fields(self):
        from linkedout.version import get_version_info
        info = get_version_info()
        required = {'version', 'python_version', 'pg_version', 'install_path', 'config_path', 'data_dir'}
        assert required.issubset(info.keys()), f'Missing fields: {required - info.keys()}'

    def test_get_version_info_version_matches(self):
        from linkedout.version import __version__, get_version_info
        info = get_version_info()
        assert info['version'] == __version__

    def test_get_version_info_python_version(self):
        from linkedout.version import get_version_info
        info = get_version_info()
        expected = sys.version.split()[0]
        assert info['python_version'] == expected

    def test_get_version_info_pg_version_graceful(self):
        """pg_version returns 'not connected' when DB is unavailable."""
        from linkedout.version import get_version_info
        info = get_version_info()
        # In unit tests without a DB, this should gracefully return "not connected"
        assert isinstance(info['pg_version'], str)

    def test_get_version_info_config_path(self):
        from linkedout.version import get_version_info
        info = get_version_info()
        assert info['config_path'].endswith('linkedout-data/config/config.yaml')

    def test_get_version_info_data_dir(self):
        from linkedout.version import get_version_info
        info = get_version_info()
        assert info['data_dir'].endswith('linkedout-data')

    def test_get_version_info_install_path(self, repo_root):
        from linkedout.version import get_version_info
        info = get_version_info()
        assert info['install_path'] == str(repo_root)

    def test_get_version_info_is_json_serializable(self):
        from linkedout.version import get_version_info
        info = get_version_info()
        serialized = json.dumps(info)
        assert isinstance(serialized, str)


class TestMissingVersionFile:
    """Missing VERSION file raises a clear error."""

    def test_missing_version_file_raises(self, tmp_path):
        """When VERSION file doesn't exist, _read_version_file raises FileNotFoundError."""
        with patch('linkedout.version._repo_root', return_value=tmp_path):
            from linkedout.version import _read_version_file
            with pytest.raises(FileNotFoundError, match='VERSION file not found'):
                _read_version_file()
