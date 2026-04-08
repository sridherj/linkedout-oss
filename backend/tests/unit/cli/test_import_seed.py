# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``linkedout import-seed`` CLI command.

Tests SQLite reading, auto-detect logic, FK ordering, upsert SQL building,
and type conversion. Uses the test fixture SQLite file.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linkedout.commands.import_seed import (
    IMPORT_ORDER,
    _build_upsert_sql,
    _convert_row,
    _locate_seed_file,
    _validate_seed_file,
    get_sqlite_columns,
    get_sqlite_tables,
    read_seed_metadata,
    read_seed_table,
)

FIXTURE_PATH = Path(__file__).parent.parent.parent / 'fixtures' / 'test-seed-core.sqlite'


@pytest.fixture
def fixture_path():
    """Path to the test fixture SQLite file."""
    assert FIXTURE_PATH.exists(), f'Test fixture not found: {FIXTURE_PATH}'
    return FIXTURE_PATH


# ── SQLite reading ───────────────────────────────────────────────────────────


class TestSQLiteReading:

    def test_read_all_rows_correct_count(self, fixture_path):
        """Read all rows from a table -> correct count."""
        rows = read_seed_table(fixture_path, 'company')
        assert len(rows) == 10

    def test_read_rows_returns_dicts(self, fixture_path):
        """Rows are returned as dicts with correct keys."""
        rows = read_seed_table(fixture_path, 'company')
        assert isinstance(rows[0], dict)
        assert 'id' in rows[0]
        assert 'canonical_name' in rows[0]

    def test_read_metadata_correct_version(self, fixture_path):
        """Read _metadata table -> correct version."""
        metadata = read_seed_metadata(fixture_path)
        assert metadata['version'] == '0.0.1-test'

    def test_read_metadata_has_table_counts(self, fixture_path):
        """Read _metadata table -> table_counts present and parseable."""
        metadata = read_seed_metadata(fixture_path)
        counts = json.loads(metadata['table_counts'])
        assert counts['company'] == 10
        assert counts['experience'] == 40

    def test_get_sqlite_tables(self, fixture_path):
        """List tables in SQLite -> all 10 seed tables present."""
        tables = get_sqlite_tables(fixture_path)
        for table in IMPORT_ORDER:
            assert table in tables

    def test_get_sqlite_columns(self, fixture_path):
        """Get column names -> includes expected columns."""
        cols = get_sqlite_columns(fixture_path, 'company')
        assert 'id' in cols
        assert 'canonical_name' in cols
        assert 'industry' in cols

    def test_read_each_table_has_rows(self, fixture_path):
        """Every table in IMPORT_ORDER has at least 1 row."""
        for table in IMPORT_ORDER:
            rows = read_seed_table(fixture_path, table)
            assert len(rows) > 0, f'{table} has no rows'


# ── Auto-detect logic ────────────────────────────────────────────────────────


class TestAutoDetect:

    def test_core_file_found(self, tmp_path):
        """seed-core.sqlite in seed dir -> found."""
        seed_dir = tmp_path / 'seed'
        seed_dir.mkdir()
        (seed_dir / 'seed-core.sqlite').write_bytes(b'x')

        settings = MagicMock()
        settings.data_dir = str(tmp_path)

        with patch('linkedout.commands.import_seed.get_config', return_value=settings):
            result = _locate_seed_file(None)
        assert result.name == 'seed-core.sqlite'

    def test_full_file_found_when_no_core(self, tmp_path):
        """seed-full.sqlite in seed dir (no core) -> found."""
        seed_dir = tmp_path / 'seed'
        seed_dir.mkdir()
        (seed_dir / 'seed-full.sqlite').write_bytes(b'x')

        settings = MagicMock()
        settings.data_dir = str(tmp_path)

        with patch('linkedout.commands.import_seed.get_config', return_value=settings):
            result = _locate_seed_file(None)
        assert result.name == 'seed-full.sqlite'

    def test_no_sqlite_files_raises(self, tmp_path):
        """No SQLite files -> error pointing to download-seed."""
        seed_dir = tmp_path / 'seed'
        seed_dir.mkdir()

        settings = MagicMock()
        settings.data_dir = str(tmp_path)

        with patch('linkedout.commands.import_seed.get_config', return_value=settings):
            with pytest.raises(Exception, match='download-seed'):
                _locate_seed_file(None)

    def test_prefers_core_over_full(self, tmp_path):
        """Multiple files -> prefers core."""
        seed_dir = tmp_path / 'seed'
        seed_dir.mkdir()
        (seed_dir / 'seed-core.sqlite').write_bytes(b'core')
        (seed_dir / 'seed-full.sqlite').write_bytes(b'full')

        settings = MagicMock()
        settings.data_dir = str(tmp_path)

        with patch('linkedout.commands.import_seed.get_config', return_value=settings):
            result = _locate_seed_file(None)
        assert result.name == 'seed-core.sqlite'

    def test_explicit_path_used(self, fixture_path):
        """Explicit --seed-file path -> used directly."""
        result = _locate_seed_file(str(fixture_path))
        assert result == fixture_path


# ── FK ordering ──────────────────────────────────────────────────────────────


class TestFKOrdering:

    def test_import_order_starts_with_company(self):
        """company is first (no FK dependencies)."""
        assert IMPORT_ORDER[0] == 'company'

    def test_company_alias_after_company(self):
        """company_alias (FK -> company) comes after company."""
        assert IMPORT_ORDER.index('company_alias') > IMPORT_ORDER.index('company')

    def test_funding_round_after_company(self):
        """funding_round (FK -> company) comes after company."""
        assert IMPORT_ORDER.index('funding_round') > IMPORT_ORDER.index('company')

    def test_experience_after_crawled_profile(self):
        """experience (FK -> crawled_profile) comes after crawled_profile."""
        assert IMPORT_ORDER.index('experience') > IMPORT_ORDER.index('crawled_profile')

    def test_education_after_crawled_profile(self):
        """education (FK -> crawled_profile) comes after crawled_profile."""
        assert IMPORT_ORDER.index('education') > IMPORT_ORDER.index('crawled_profile')

    def test_profile_skill_after_crawled_profile(self):
        """profile_skill (FK -> crawled_profile) comes after crawled_profile."""
        assert IMPORT_ORDER.index('profile_skill') > IMPORT_ORDER.index('crawled_profile')

    def test_experience_after_company(self):
        """experience (FK -> company) comes after company."""
        assert IMPORT_ORDER.index('experience') > IMPORT_ORDER.index('company')

    def test_all_10_tables_present(self):
        """IMPORT_ORDER contains exactly 10 tables."""
        assert len(IMPORT_ORDER) == 10

    def test_expected_order(self):
        """Verify the hardcoded order matches expected FK dependencies."""
        expected = [
            'company', 'company_alias', 'role_alias',
            'funding_round', 'startup_tracking', 'growth_signal',
            'crawled_profile', 'experience', 'education', 'profile_skill',
        ]
        assert IMPORT_ORDER == expected


# ── Type conversion ──────────────────────────────────────────────────────────


class TestTypeConversion:

    def test_array_column_parsed_from_json(self):
        """JSON string in array column -> parsed to Python list."""
        row = {'id': 'co_1', 'enrichment_sources': '["linkedin", "pdl"]'}
        result = _convert_row(row, 'company')
        assert result['enrichment_sources'] == ['linkedin', 'pdl']

    def test_array_column_none_preserved(self):
        """None in array column -> stays None."""
        row = {'id': 'co_1', 'enrichment_sources': None}
        result = _convert_row(row, 'company')
        assert result['enrichment_sources'] is None

    def test_bool_column_converted(self):
        """Integer 0/1 in bool column -> Python bool."""
        row = {'id': 'st_1', 'watching': 1}
        result = _convert_row(row, 'startup_tracking')
        assert result['watching'] is True

    def test_bool_column_false(self):
        """Integer 0 -> False."""
        row = {'id': 'st_1', 'watching': 0}
        result = _convert_row(row, 'startup_tracking')
        assert result['watching'] is False

    def test_bool_column_none_preserved(self):
        """None in bool column -> stays None."""
        row = {'id': 'exp_1', 'is_current': None}
        result = _convert_row(row, 'experience')
        assert result['is_current'] is None

    def test_no_conversion_for_regular_table(self):
        """Table without array/bool mappings -> row unchanged."""
        row = {'id': 'ra_1', 'alias_title': 'SWE', 'canonical_title': 'Software Engineer'}
        result = _convert_row(row, 'role_alias')
        assert result == row

    def test_funding_round_investors_parsed(self):
        """funding_round array columns parsed correctly."""
        row = {
            'id': 'fr_1',
            'lead_investors': '["Sequoia"]',
            'all_investors': '["Sequoia", "YC"]',
        }
        result = _convert_row(row, 'funding_round')
        assert result['lead_investors'] == ['Sequoia']
        assert result['all_investors'] == ['Sequoia', 'YC']


# ── Upsert SQL building ─────────────────────────────────────────────────────


class TestUpsertSQL:

    def test_upsert_contains_on_conflict(self):
        """Built SQL uses ON CONFLICT (id) DO UPDATE."""
        sql = _build_upsert_sql('company', ['id', 'canonical_name', 'industry'])
        assert 'ON CONFLICT (id) DO UPDATE' in sql

    def test_upsert_contains_is_distinct_from(self):
        """Built SQL uses IS DISTINCT FROM for change detection."""
        sql = _build_upsert_sql('company', ['id', 'canonical_name', 'industry'])
        assert 'IS DISTINCT FROM' in sql

    def test_upsert_contains_returning(self):
        """Built SQL uses RETURNING to distinguish inserts from updates."""
        sql = _build_upsert_sql('company', ['id', 'canonical_name'])
        assert 'RETURNING' in sql

    def test_upsert_pk_not_in_set_clause(self):
        """id column is NOT in the SET clause."""
        sql = _build_upsert_sql('company', ['id', 'canonical_name', 'industry'])
        # SET clause should not set id
        assert 'id = EXCLUDED.id' not in sql

    def test_upsert_all_non_pk_columns_in_set(self):
        """All non-PK columns appear in SET clause."""
        cols = ['id', 'canonical_name', 'industry']
        sql = _build_upsert_sql('company', cols)
        assert 'canonical_name = EXCLUDED.canonical_name' in sql
        assert 'industry = EXCLUDED.industry' in sql


# ── Validate seed file ──────────────────────────────────────────────────────


class TestValidateSeedFile:

    def test_valid_fixture_passes(self, fixture_path):
        """Test fixture passes validation."""
        metadata = _validate_seed_file(fixture_path)
        assert metadata['version'] == '0.0.1-test'

    def test_missing_table_raises(self, tmp_path):
        """Seed file missing a required table -> raises error."""
        bad_file = tmp_path / 'bad.sqlite'
        conn = sqlite3.connect(str(bad_file))
        c = conn.cursor()
        c.execute('CREATE TABLE company (id TEXT PRIMARY KEY)')
        c.execute("CREATE TABLE _metadata (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("INSERT INTO _metadata VALUES ('version', '0.0.1')")
        c.execute("INSERT INTO _metadata VALUES ('table_counts', '{}')")
        conn.commit()
        conn.close()

        with pytest.raises(Exception, match='missing tables'):
            _validate_seed_file(bad_file)
