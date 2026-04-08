# SPDX-License-Identifier: Apache-2.0
"""Integration tests for the seed data import pipeline.

Tests require a PostgreSQL database. They are skipped automatically if
``DATABASE_URL`` is not configured or points to SQLite.

Uses the test fixture at ``backend/tests/fixtures/test-seed-core.sqlite``.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import text

from linkedout.commands.import_seed import (
    IMPORT_ORDER,
    import_seed_command,
    read_seed_metadata,
)

pytestmark = pytest.mark.integration

FIXTURE_PATH = Path(__file__).parent.parent.parent / 'fixtures' / 'test-seed-core.sqlite'


@pytest.fixture(scope='module')
def fixture_path():
    assert FIXTURE_PATH.exists(), f'Test fixture not found: {FIXTURE_PATH}'
    return FIXTURE_PATH


@pytest.fixture(scope='module')
def runner():
    return CliRunner()


@pytest.fixture(scope='module')
def expected_counts(fixture_path):
    """Get expected row counts from fixture metadata."""
    metadata = read_seed_metadata(fixture_path)
    return json.loads(metadata['table_counts'])


def _count_rows(session, table_name: str) -> int:
    """Count rows in a PostgreSQL table."""
    return session.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar()


def _clear_seed_tables(session):
    """Delete all seed data tables in reverse FK order."""
    for table in reversed(IMPORT_ORDER):
        session.execute(text(f'DELETE FROM {table}'))
    session.commit()


# ── Full import pipeline ────────────────────────────────────────────────────


class TestFullImport:
    """Test importing the test fixture into an empty PostgreSQL database."""

    def test_import_into_empty_db(
        self, runner, fixture_path, integration_db_session, expected_counts,
    ):
        """Import test fixture into empty PostgreSQL -> all rows inserted."""
        _clear_seed_tables(integration_db_session)

        result = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path)],
        )

        assert result.exit_code == 0, f'Import failed:\n{result.output}'
        assert 'Results:' in result.output

        # Verify row counts per table match fixture metadata
        for table, expected in expected_counts.items():
            actual = _count_rows(integration_db_session, table)
            assert actual == expected, (
                f'{table}: expected {expected} rows, got {actual}'
            )

    def test_fk_relationships_intact(self, integration_db_session):
        """FK relationships are intact after import."""
        # experience records point to valid crawled_profile IDs
        orphan_exp = integration_db_session.execute(text(
            'SELECT COUNT(*) FROM experience e '
            'WHERE NOT EXISTS (SELECT 1 FROM crawled_profile cp WHERE cp.id = e.crawled_profile_id)'
        )).scalar()
        assert orphan_exp == 0, f'{orphan_exp} experience records with invalid crawled_profile_id'

        # experience records point to valid company IDs
        orphan_co = integration_db_session.execute(text(
            'SELECT COUNT(*) FROM experience e '
            'WHERE e.company_id IS NOT NULL '
            'AND NOT EXISTS (SELECT 1 FROM company c WHERE c.id = e.company_id)'
        )).scalar()
        assert orphan_co == 0, f'{orphan_co} experience records with invalid company_id'

    def test_output_follows_operation_result_pattern(self, runner, fixture_path, integration_db_session):
        """CLI output follows the Operation Result Pattern."""
        _clear_seed_tables(integration_db_session)

        result = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path)],
        )
        assert 'Results:' in result.output
        assert 'Next steps:' in result.output
        assert 'Report saved:' in result.output


# ── Idempotency ─────────────────────────────────────────────────────────────


class TestIdempotency:
    """Test that importing the same data twice is safe."""

    def test_second_import_all_skipped(
        self, runner, fixture_path, integration_db_session, expected_counts,
    ):
        """Import test fixture twice -> second run shows all 'skipped'."""
        _clear_seed_tables(integration_db_session)

        # First import
        result1 = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path)],
        )
        assert result1.exit_code == 0

        # Second import
        result2 = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path)],
        )
        assert result2.exit_code == 0
        assert 'already up to date' in result2.output

        # Verify row counts unchanged
        for table, expected in expected_counts.items():
            actual = _count_rows(integration_db_session, table)
            assert actual == expected, (
                f'{table}: expected {expected} after second import, got {actual}'
            )


# ── Update detection ────────────────────────────────────────────────────────


class TestUpdateDetection:

    def test_modified_row_detected(
        self, runner, fixture_path, integration_db_session, tmp_path,
    ):
        """Modify a company name in SQLite -> re-import -> one 'updated'."""
        _clear_seed_tables(integration_db_session)

        # First import
        result1 = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path)],
        )
        assert result1.exit_code == 0

        # Copy fixture and modify one company name
        modified = tmp_path / 'modified-seed.sqlite'
        import shutil
        shutil.copy2(fixture_path, modified)

        conn = sqlite3.connect(str(modified))
        conn.execute(
            "UPDATE company SET canonical_name = 'MODIFIED Company 1' WHERE id = 'co_test_001'"
        )
        conn.commit()
        conn.close()

        # Re-import with modified data
        result2 = runner.invoke(
            import_seed_command,
            ['--seed-file', str(modified)],
        )
        assert result2.exit_code == 0
        # Should show at least one updated row
        assert '1 updated' in result2.output or 'updated' in result2.output

        # Verify the update took effect
        row = integration_db_session.execute(
            text("SELECT canonical_name FROM company WHERE id = 'co_test_001'")
        ).fetchone()
        assert row[0] == 'MODIFIED Company 1'


# ── Dry-run mode ────────────────────────────────────────────────────────────


class TestDryRun:

    def test_dry_run_no_writes(
        self, runner, fixture_path, integration_db_session,
    ):
        """Import with --dry-run -> verify no rows in PostgreSQL."""
        _clear_seed_tables(integration_db_session)

        result = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path), '--dry-run'],
        )
        assert result.exit_code == 0
        assert 'DRY RUN' in result.output

        # Verify no rows written
        for table in IMPORT_ORDER:
            count = _count_rows(integration_db_session, table)
            assert count == 0, f'{table} has {count} rows after dry-run'

    def test_dry_run_shows_counts(
        self, runner, fixture_path, integration_db_session,
    ):
        """Dry-run output shows correct counts of what would be imported."""
        _clear_seed_tables(integration_db_session)

        result = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path), '--dry-run'],
        )
        assert result.exit_code == 0
        # Should mention table names and row counts
        assert 'company' in result.output
        assert 'experience' in result.output


# ── Report generation ───────────────────────────────────────────────────────


class TestReportGeneration:

    def test_report_exists_after_import(
        self, runner, fixture_path, integration_db_session,
    ):
        """After import, verify JSON report exists at expected path."""
        _clear_seed_tables(integration_db_session)

        result = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path)],
        )
        assert result.exit_code == 0
        assert 'Report saved:' in result.output

        # Extract report path from output
        for line in result.output.splitlines():
            if 'Report saved:' in line:
                report_display = line.split('Report saved:')[1].strip()
                # Expand ~ if present
                report_path = Path(report_display.replace('~/', str(Path.home()) + '/'))
                assert report_path.exists(), f'Report not found at {report_path}'

                # Verify JSON structure
                with open(report_path) as f:
                    report = json.load(f)
                assert report['operation'] == 'import-seed'
                assert 'tables' in report
                assert 'totals' in report
                assert 'duration_ms' in report
                break
