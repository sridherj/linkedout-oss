# SPDX-License-Identifier: Apache-2.0
"""Tests for linkedout.upgrade.changelog_parser — CHANGELOG.md parsing."""
from __future__ import annotations

from pathlib import Path

from linkedout.upgrade.changelog_parser import parse_changelog

_SAMPLE_CHANGELOG = """\
# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-05-01

### Added
- Chrome extension auto-discovery of mutual connections
- New affinity scoring algorithm

### Fixed
- Seed data import for companies with Unicode names

## [0.2.0] - 2026-04-15

### Added
- Semantic search across all profile fields
- `linkedout export` command for CSV/JSON network export

### Fixed
- Affinity computation for networks with 10,000+ connections

### Changed
- Improved embedding generation speed by 3x with batched API calls

## [0.1.0] - 2026-04-01

### Added
- Initial release
- LinkedIn connection import
- Basic search and affinity scoring
"""


class TestSingleVersionExtraction:
    """Extract changelog for a single version upgrade."""

    def test_extracts_content_between_versions(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('0.1.0', '0.2.0', changelog_path=changelog)

        assert "What's New in v0.2.0" in result
        assert 'Semantic search across all profile fields' in result
        assert '`linkedout export` command' in result
        assert 'Affinity computation for networks with 10,000+ connections' in result

    def test_strips_category_headers(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('0.1.0', '0.2.0', changelog_path=changelog)

        assert '### Added' not in result
        assert '### Fixed' not in result
        assert '### Changed' not in result

    def test_formats_as_bullet_list(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('0.1.0', '0.2.0', changelog_path=changelog)

        lines = [l for l in result.split('\n') if l.startswith('- ')]
        assert len(lines) >= 3

    def test_header_and_separator(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('0.1.0', '0.2.0', changelog_path=changelog)
        lines = result.split('\n')

        assert lines[0] == "What's New in v0.2.0"
        assert lines[1] == '-' * len(lines[0])


class TestMultiVersionExtraction:
    """Extract changelog across multiple version jumps."""

    def test_includes_all_intermediate_versions(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('0.1.0', '0.3.0', changelog_path=changelog)

        assert "What's New since v0.1.0" in result
        assert 'v0.3.0:' in result
        assert 'v0.2.0:' in result

    def test_newest_first(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('0.1.0', '0.3.0', changelog_path=changelog)

        idx_03 = result.index('v0.3.0:')
        idx_02 = result.index('v0.2.0:')
        assert idx_03 < idx_02


class TestMissingVersions:
    """Edge cases with missing versions in the changelog."""

    def test_missing_old_version(self, tmp_path: Path):
        """When old version doesn't exist in changelog, extract up to new."""
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('0.0.1', '0.2.0', changelog_path=changelog)

        # Should include 0.1.0 and 0.2.0 since both are > 0.0.1
        assert 'v0.2.0' in result
        assert 'v0.1.0' in result

    def test_missing_new_version(self, tmp_path: Path):
        """When new version doesn't exist in changelog, return fallback."""
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('0.1.0', '0.5.0', changelog_path=changelog)

        # Should include 0.2.0 and 0.3.0 (everything between 0.1.0 and 0.5.0)
        assert 'v0.3.0' in result or 'v0.2.0' in result


class TestMalformedAndEmpty:
    """Handle malformed markdown and empty files gracefully."""

    def test_empty_changelog(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text('')

        result = parse_changelog('0.1.0', '0.2.0', changelog_path=changelog)

        assert 'No changelog entries found' in result
        assert 'v0.2.0' in result

    def test_missing_changelog_file(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        # File doesn't exist

        result = parse_changelog('0.1.0', '0.2.0', changelog_path=changelog)

        assert 'No changelog entries found' in result

    def test_changelog_with_no_version_headers(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text('# Changelog\n\nSome text but no version headers.\n')

        result = parse_changelog('0.1.0', '0.2.0', changelog_path=changelog)

        assert 'Changelog entry not found' in result

    def test_malformed_version_in_header(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text('## [not-a-version]\n\n- Some change\n')

        result = parse_changelog('0.1.0', '0.2.0', changelog_path=changelog)

        assert 'Changelog entry not found' in result

    def test_invalid_version_args(self, tmp_path: Path):
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('abc', '0.2.0', changelog_path=changelog)
        assert 'Changelog entry not found' in result

    def test_same_version(self, tmp_path: Path):
        """When from and to are the same, no entries match."""
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(_SAMPLE_CHANGELOG)

        result = parse_changelog('0.2.0', '0.2.0', changelog_path=changelog)

        # Range (0.2.0, 0.2.0] is empty
        assert 'Changelog entry not found' in result


class TestTruncation:
    """Long changelogs are truncated."""

    def test_truncates_long_content(self, tmp_path: Path):
        # Build a changelog with many entries
        entries = '\n'.join(f'- Change number {i}' for i in range(50))
        changelog_text = f'## [0.2.0] - 2026-04-15\n\n### Added\n{entries}\n\n## [0.1.0]\n\n- Initial\n'
        changelog = tmp_path / 'CHANGELOG.md'
        changelog.write_text(changelog_text)

        result = parse_changelog('0.1.0', '0.2.0', changelog_path=changelog)

        assert '... and' in result
        assert 'more changes' in result
        assert 'CHANGELOG.md' in result
