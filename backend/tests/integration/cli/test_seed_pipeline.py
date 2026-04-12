# SPDX-License-Identifier: Apache-2.0
"""Integration tests for the seed data import pipeline.

Tests require a PostgreSQL database. They are skipped automatically if
``DATABASE_URL`` is not configured or points to SQLite.

Generates a test fixture dynamically from current entity schema via
``tests/fixtures/generate_test_seed.py``.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, text

from common.entities.base_entity import Base
from linkedout.commands.import_seed import (
    IMPORT_ORDER,
    import_seed_command,
)

pytestmark = pytest.mark.integration


def _base_db_url(engine) -> str:
    """Extract base database URL without search_path options."""
    url = engine.url
    return url.set(query={}).render_as_string(hide_password=False)


@pytest.fixture(scope='module')
def fixture_path(integration_db_engine):
    """Generate a test seed dump dynamically from current schema."""
    from tests.fixtures.generate_test_seed import generate

    base_url = _base_db_url(integration_db_engine)
    fd, tmp = tempfile.mkstemp(suffix='.dump')
    os.close(fd)
    output_path = Path(tmp)
    manifest_path = output_path.parent / 'seed-manifest.json'

    try:
        dump_path = generate(base_db_url=base_url, output_path=output_path)
        assert dump_path.exists(), f'Generated fixture not found: {dump_path}'
        yield dump_path
    finally:
        output_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)


@pytest.fixture(scope='module', autouse=True)
def public_tables(integration_db_engine, fixture_path):
    """Create entity tables in public schema for the seed import pipeline.

    Depends on fixture_path to ensure the dump is generated BEFORE public tables
    exist (otherwise generate_test_seed's checkfirst=True skips _seed_staging tables).
    """
    base_url = _base_db_url(integration_db_engine)
    engine = create_engine(base_url)
    seed_tables = [Base.metadata.tables[t] for t in IMPORT_ORDER]
    Base.metadata.create_all(engine, tables=seed_tables)
    yield engine
    with engine.connect() as conn:
        for table_name in reversed(IMPORT_ORDER):
            conn.execute(text(f'DROP TABLE IF EXISTS {table_name} CASCADE'))
        conn.commit()
    engine.dispose()


@pytest.fixture(scope='module')
def runner():
    return CliRunner()


@pytest.fixture(scope='module')
def expected_counts(fixture_path):
    """Get expected row counts from the dynamically generated manifest."""
    manifest_path = fixture_path.parent / 'seed-manifest.json'
    assert manifest_path.exists(), f'Manifest not found: {manifest_path}'
    manifest = json.loads(manifest_path.read_text())
    return manifest['table_counts']


def _count_rows(session, table_name: str) -> int:
    """Count rows in a public schema PostgreSQL table."""
    return session.execute(text(f'SELECT COUNT(*) FROM public.{table_name}')).scalar()


def _clear_seed_tables(session):
    """Truncate all seed tables in public schema."""
    tables = ', '.join(f'public.{t}' for t in IMPORT_ORDER)
    session.execute(text(f'TRUNCATE {tables} CASCADE'))
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

        # Verify row counts per table match manifest
        for table, expected in expected_counts.items():
            actual = _count_rows(integration_db_session, table)
            assert actual == expected, (
                f'{table}: expected {expected} rows, got {actual}'
            )

    def test_fk_relationships_intact(self, integration_db_session):
        """FK relationships are intact after import."""
        # company_alias records point to valid company IDs
        orphan_alias = integration_db_session.execute(text(
            'SELECT COUNT(*) FROM public.company_alias ca '
            'WHERE NOT EXISTS (SELECT 1 FROM public.company c WHERE c.id = ca.company_id)'
        )).scalar()
        assert orphan_alias == 0, f'{orphan_alias} company_alias records with invalid company_id'

        # funding_round records point to valid company IDs
        orphan_fr = integration_db_session.execute(text(
            'SELECT COUNT(*) FROM public.funding_round fr '
            'WHERE NOT EXISTS (SELECT 1 FROM public.company c WHERE c.id = fr.company_id)'
        )).scalar()
        assert orphan_fr == 0, f'{orphan_fr} funding_round records with invalid company_id'

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
        self, runner, fixture_path, integration_db_session,
    ):
        """Modify a company name in PG -> re-import dump -> one 'updated'."""
        _clear_seed_tables(integration_db_session)

        # First import
        result1 = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path)],
        )
        assert result1.exit_code == 0

        # Modify a company name directly in PostgreSQL
        integration_db_session.execute(
            text("UPDATE public.company SET canonical_name = 'MODIFIED' WHERE id = 'co_test_001'")
        )
        integration_db_session.commit()

        # Re-import the original dump — should detect the row as changed
        result2 = runner.invoke(
            import_seed_command,
            ['--seed-file', str(fixture_path)],
        )
        assert result2.exit_code == 0
        assert '1 updated' in result2.output or 'updated' in result2.output

        # Verify the original name was restored from the dump
        row = integration_db_session.execute(
            text("SELECT canonical_name FROM public.company WHERE id = 'co_test_001'")
        ).fetchone()
        assert row[0] != 'MODIFIED'


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
        assert 'role_alias' in result.output


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


# ── pg_restore availability ─────────────────────────────────────────────────


class TestPgRestoreAvailability:

    def test_import_with_pg_restore_unavailable(self, runner, fixture_path):
        """pg_restore not on PATH -> clear error about installing postgresql-client."""
        with patch('linkedout.commands.import_seed.shutil.which', return_value=None):
            result = runner.invoke(
                import_seed_command,
                ['--seed-file', str(fixture_path)],
            )
        assert result.exit_code != 0
        assert 'pg_restore' in result.output
        assert 'postgresql-client' in result.output
