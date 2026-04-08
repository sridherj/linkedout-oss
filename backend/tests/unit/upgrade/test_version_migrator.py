# SPDX-License-Identifier: Apache-2.0
"""Tests for linkedout.upgrade.version_migrator — script discovery and execution."""
from __future__ import annotations

from pathlib import Path
import pytest

from linkedout.upgrade.version_migrator import find_migration_scripts, run_version_migrations


def _write_script(directory: Path, name: str, *, should_fail: bool = False) -> Path:
    """Write a minimal version migration script."""
    path = directory / name
    if should_fail:
        path.write_text(
            'def migrate(config):\n'
            '    raise RuntimeError("migration failed on purpose")\n'
        )
    else:
        path.write_text(
            'def migrate(config):\n'
            '    pass  # no-op migration\n'
        )
    return path


class TestFindMigrationScripts:
    """Script discovery in migrations/version/."""

    def test_finds_matching_scripts(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()
        _write_script(scripts_dir, 'v0_1_0_to_v0_2_0.py')
        _write_script(scripts_dir, 'v0_2_0_to_v0_3_0.py')

        result = find_migration_scripts('0.1.0', '0.3.0', scripts_dir=scripts_dir)

        names = [p.name for p in result]
        assert names == ['v0_1_0_to_v0_2_0.py', 'v0_2_0_to_v0_3_0.py']

    def test_returns_ascending_order(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()
        # Create out of order
        _write_script(scripts_dir, 'v0_2_0_to_v0_3_0.py')
        _write_script(scripts_dir, 'v0_1_0_to_v0_2_0.py')

        result = find_migration_scripts('0.1.0', '0.3.0', scripts_dir=scripts_dir)

        names = [p.name for p in result]
        assert names == ['v0_1_0_to_v0_2_0.py', 'v0_2_0_to_v0_3_0.py']

    def test_excludes_scripts_outside_range(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()
        _write_script(scripts_dir, 'v0_1_0_to_v0_2_0.py')
        _write_script(scripts_dir, 'v0_3_0_to_v0_4_0.py')  # outside range

        result = find_migration_scripts('0.1.0', '0.2.0', scripts_dir=scripts_dir)

        names = [p.name for p in result]
        assert names == ['v0_1_0_to_v0_2_0.py']
        assert 'v0_3_0_to_v0_4_0.py' not in names

    def test_empty_directory(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()

        result = find_migration_scripts('0.1.0', '0.2.0', scripts_dir=scripts_dir)

        assert result == []

    def test_nonexistent_directory(self, tmp_path: Path):
        scripts_dir = tmp_path / 'nonexistent'

        result = find_migration_scripts('0.1.0', '0.2.0', scripts_dir=scripts_dir)

        assert result == []

    def test_ignores_non_matching_files(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()
        _write_script(scripts_dir, 'v0_1_0_to_v0_2_0.py')
        (scripts_dir / 'README.md').write_text('# README')
        (scripts_dir / 'helpers.py').write_text('# not a migration')
        (scripts_dir / '__init__.py').write_text('')

        result = find_migration_scripts('0.1.0', '0.2.0', scripts_dir=scripts_dir)

        assert len(result) == 1
        assert result[0].name == 'v0_1_0_to_v0_2_0.py'

    def test_invalid_version_args(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()
        _write_script(scripts_dir, 'v0_1_0_to_v0_2_0.py')

        result = find_migration_scripts('invalid', '0.2.0', scripts_dir=scripts_dir)

        assert result == []


class TestRunVersionMigrations:
    """Script execution and error handling."""

    def test_runs_scripts_in_order(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()

        call_order: list[str] = []
        script1 = scripts_dir / 'v0_1_0_to_v0_2_0.py'
        script1.write_text(
            'def migrate(config):\n'
            '    config.append("0.1->0.2")\n'
        )
        script2 = scripts_dir / 'v0_2_0_to_v0_3_0.py'
        script2.write_text(
            'def migrate(config):\n'
            '    config.append("0.2->0.3")\n'
        )

        results = run_version_migrations(
            '0.1.0', '0.3.0', config=call_order, scripts_dir=scripts_dir
        )

        assert len(results) == 2
        assert results[0]['script'] == 'v0_1_0_to_v0_2_0.py'
        assert results[0]['status'] == 'success'
        assert results[1]['script'] == 'v0_2_0_to_v0_3_0.py'
        assert results[1]['status'] == 'success'
        assert call_order == ['0.1->0.2', '0.2->0.3']

    def test_returns_empty_list_when_no_scripts(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()

        results = run_version_migrations(
            '0.1.0', '0.2.0', config=None, scripts_dir=scripts_dir
        )

        assert results == []

    def test_calls_migrate_with_config(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()
        script = scripts_dir / 'v0_1_0_to_v0_2_0.py'
        script.write_text(
            'def migrate(config):\n'
            '    config["called"] = True\n'
        )

        config = {}
        run_version_migrations('0.1.0', '0.2.0', config=config, scripts_dir=scripts_dir)

        assert config == {'called': True}

    def test_raises_on_script_failure(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()
        _write_script(scripts_dir, 'v0_1_0_to_v0_2_0.py', should_fail=True)

        with pytest.raises(RuntimeError, match='migration failed on purpose'):
            run_version_migrations(
                '0.1.0', '0.2.0', config=None, scripts_dir=scripts_dir
            )

    def test_records_duration(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()
        _write_script(scripts_dir, 'v0_1_0_to_v0_2_0.py')

        results = run_version_migrations(
            '0.1.0', '0.2.0', config=None, scripts_dir=scripts_dir
        )

        assert results[0]['duration_ms'] >= 0

    def test_script_without_migrate_raises(self, tmp_path: Path):
        scripts_dir = tmp_path / 'version'
        scripts_dir.mkdir()
        script = scripts_dir / 'v0_1_0_to_v0_2_0.py'
        script.write_text('# no migrate function\nx = 1\n')

        with pytest.raises(AttributeError, match='does not define a migrate'):
            run_version_migrations(
                '0.1.0', '0.2.0', config=None, scripts_dir=scripts_dir
            )
