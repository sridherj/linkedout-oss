# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``linkedout import-seed`` CLI command.

Tests auto-detect logic, FK ordering, staging upsert SQL building,
and manifest reading. Uses the pg_dump-based test fixture.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linkedout.commands.import_seed import (
    IMPORT_ORDER,
    _build_staging_upsert_sql,
    _locate_seed_file,
    _read_manifest,
)

@pytest.fixture
def fixture_path(tmp_path):
    """Create a temporary dump file for tests that need an existing file path."""
    dump = tmp_path / 'test-seed.dump'
    dump.write_bytes(b'fake dump content')
    return dump


# ── Auto-detect logic ────────────────────────────────────────────────────────


class TestAutoDetect:

    def test_seed_file_found(self, tmp_path):
        """seed.dump in seed dir -> found."""
        seed_dir = tmp_path / 'seed'
        seed_dir.mkdir()
        (seed_dir / 'seed.dump').write_bytes(b'x')

        settings = MagicMock()
        settings.data_dir = str(tmp_path)

        with patch('linkedout.commands.import_seed.get_config', return_value=settings):
            result = _locate_seed_file(None)
        assert result.name == 'seed.dump'

    def test_no_dump_files_raises(self, tmp_path):
        """No dump files -> error pointing to download-seed."""
        seed_dir = tmp_path / 'seed'
        seed_dir.mkdir()

        settings = MagicMock()
        settings.data_dir = str(tmp_path)

        with patch('linkedout.commands.import_seed.get_config', return_value=settings):
            with pytest.raises(Exception, match='download-seed'):
                _locate_seed_file(None)

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

    def test_all_6_tables_present(self):
        """IMPORT_ORDER contains exactly 6 company/reference tables."""
        assert len(IMPORT_ORDER) == 6

    def test_expected_order(self):
        """Verify the hardcoded order matches expected FK dependencies."""
        expected = [
            'company', 'company_alias', 'role_alias',
            'funding_round', 'startup_tracking', 'growth_signal',
        ]
        assert IMPORT_ORDER == expected


# ── Upsert SQL building (staging schema) ───────────────────────────────────


class TestUpsertSQL:

    def test_upsert_contains_on_conflict(self):
        """Built SQL uses ON CONFLICT (id) DO UPDATE."""
        sql = _build_staging_upsert_sql('company', ['id', 'canonical_name', 'industry'])
        assert 'ON CONFLICT (id) DO UPDATE' in sql

    def test_upsert_contains_is_distinct_from(self):
        """Built SQL uses IS DISTINCT FROM for change detection."""
        sql = _build_staging_upsert_sql('company', ['id', 'canonical_name', 'industry'])
        assert 'IS DISTINCT FROM' in sql

    def test_upsert_contains_returning(self):
        """Built SQL uses RETURNING to distinguish inserts from updates."""
        sql = _build_staging_upsert_sql('company', ['id', 'canonical_name'])
        assert 'RETURNING' in sql
        assert 'was_insert' in sql

    def test_upsert_pk_not_in_set_clause(self):
        """id column is NOT in the SET clause."""
        sql = _build_staging_upsert_sql('company', ['id', 'canonical_name', 'industry'])
        assert 'id = EXCLUDED.id' not in sql

    def test_upsert_all_non_pk_columns_in_set(self):
        """All non-PK columns appear in SET clause."""
        cols = ['id', 'canonical_name', 'industry']
        sql = _build_staging_upsert_sql('company', cols)
        assert 'canonical_name = EXCLUDED.canonical_name' in sql
        assert 'industry = EXCLUDED.industry' in sql


# ── Staging upsert SQL (additional assertions) ─────────────────────────────


class TestStagingUpsertSQL:

    def test_selects_from_staging_schema(self):
        """SQL reads from _seed_staging.{table} as source."""
        sql = _build_staging_upsert_sql('company', ['id', 'canonical_name'])
        assert '_seed_staging.company' in sql

    def test_uses_cte(self):
        """SQL uses WITH upserted AS (...) CTE pattern."""
        sql = _build_staging_upsert_sql('company', ['id', 'canonical_name'])
        assert 'WITH upserted AS' in sql

    def test_inserts_into_public_schema(self):
        """SQL targets public.{table} for the INSERT."""
        sql = _build_staging_upsert_sql('company', ['id', 'canonical_name'])
        assert 'INSERT INTO public.company' in sql


# ── Manifest reading ──────────────────────────────────────────────────────


class TestManifestReading:

    def test_valid_manifest_returns_dict(self, tmp_path):
        """Valid JSON manifest -> returns dict with expected fields."""
        manifest_data = {
            'version': '0.1.0',
            'format': 'pgdump',
            'table_counts': {'company': 10},
        }
        (tmp_path / 'seed-manifest.json').write_text(json.dumps(manifest_data))
        dump_file = tmp_path / 'test.dump'
        dump_file.write_bytes(b'x')

        result = _read_manifest(dump_file)
        assert result is not None
        assert result['version'] == '0.1.0'
        assert result['table_counts']['company'] == 10

    def test_missing_manifest_returns_none(self, tmp_path):
        """Missing manifest file -> returns None."""
        dump_file = tmp_path / 'test.dump'
        dump_file.write_bytes(b'x')

        result = _read_manifest(dump_file)
        assert result is None

    def test_malformed_json_raises(self, tmp_path):
        """Malformed JSON -> raises JSONDecodeError."""
        (tmp_path / 'seed-manifest.json').write_text('not valid json{{{')
        dump_file = tmp_path / 'test.dump'
        dump_file.write_bytes(b'x')

        with pytest.raises(json.JSONDecodeError):
            _read_manifest(dump_file)
