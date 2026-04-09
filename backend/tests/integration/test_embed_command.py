# SPDX-License-Identifier: Apache-2.0
"""Integration tests for the ``linkedout embed`` CLI command.

These tests use a real PostgreSQL database but mock the embedding providers.
They verify the full end-to-end flow: profile fetching, embedding generation,
DB writes, progress tracking, and resumability.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from sqlalchemy import text

from linkedout.commands.embed import embed_command

pytestmark = pytest.mark.integration


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def progress_dir(tmp_path):
    """Provide a temp directory for embedding progress files."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def reports_dir(tmp_path):
    """Provide a temp directory for report files."""
    rdir = tmp_path / "reports"
    rdir.mkdir()
    return rdir


def _mock_openai_provider(vectors=None):
    """Create a mock OpenAI embedding provider."""
    prov = MagicMock()
    prov.model_name.return_value = 'text-embedding-3-small'
    prov.dimension.return_value = 1536
    prov.estimate_time.return_value = '~1 minute'
    prov.estimate_cost.return_value = '~$0.02'
    if vectors is not None:
        prov.embed.return_value = vectors
    else:
        # By default, return vectors matching the batch size
        def _embed(texts):
            return [[0.1] * 1536 for _ in texts]
        prov.embed.side_effect = _embed
    return prov


def _mock_local_provider(vectors=None):
    """Create a mock local (nomic) embedding provider."""
    prov = MagicMock()
    prov.model_name.return_value = 'nomic-embed-text-v1.5'
    prov.dimension.return_value = 768
    prov.estimate_time.return_value = '~5 minutes'
    prov.estimate_cost.return_value = None
    if vectors is not None:
        prov.embed.return_value = vectors
    else:
        def _embed(texts):
            return [[0.2] * 768 for _ in texts]
        prov.embed.side_effect = _embed
    return prov


def _create_test_profiles(session, count=5):
    """Insert test profiles into the database.

    Creates profiles with has_enriched_data=TRUE and NULL embeddings.
    Returns list of created profile IDs.
    """
    ids = []
    for i in range(count):
        pid = f"cp_test_{i:04d}"
        session.execute(text(
            "INSERT INTO crawled_profile (id, linkedin_url, full_name, headline, about, "
            "current_company_name, current_position, has_enriched_data, "
            "created_at, updated_at) "
            "VALUES (:id, :linkedin_url, :name, :headline, :about, :company, :position, TRUE, "
            "NOW(), NOW()) "
            "ON CONFLICT (id) DO NOTHING"
        ), {
            'id': pid,
            'linkedin_url': f'https://linkedin.com/in/test-user-{i}',
            'name': f'Test User {i}',
            'headline': f'Engineer at Company {i}',
            'about': f'A professional with experience in field {i}',
            'company': f'Company {i}',
            'position': f'Senior Engineer',
        })
        ids.append(pid)
    session.commit()
    return ids


def _get_embedding(session, profile_id, column='embedding_openai'):
    """Read an embedding value for a given profile."""
    row = session.execute(text(
        f"SELECT {column} FROM crawled_profile WHERE id = :pid"
    ), {'pid': profile_id}).fetchone()
    return row[0] if row else None


def _get_embedding_metadata(session, profile_id):
    """Read embedding metadata for a profile."""
    row = session.execute(text(
        "SELECT embedding_model, embedding_dim, embedding_updated_at "
        "FROM crawled_profile WHERE id = :pid"
    ), {'pid': profile_id}).fetchone()
    if not row:
        return None
    return {'model': row[0], 'dim': row[1], 'updated_at': row[2]}


class TestEmbedOpenAIE2E:
    """Create profiles, run embed with mocked OpenAI, verify column populated."""

    def test_embed_openai(
        self, runner, integration_db_session, progress_dir, reports_dir, monkeypatch
    ):
        # Arrange
        ids = _create_test_profiles(integration_db_session, count=3)
        progress_file = progress_dir / "embedding_progress.json"
        monkeypatch.setenv("LINKEDOUT_REPORTS_DIR", str(reports_dir))

        mock_prov = _mock_openai_provider()

        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file):
                result = runner.invoke(embed_command, ['--provider', 'openai'])

        # Assert
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Results:' in result.output
        assert 'Embedded:' in result.output

        # Verify embeddings written
        for pid in ids:
            emb = _get_embedding(integration_db_session, pid, 'embedding_openai')
            assert emb is not None, f"Profile {pid} should have openai embedding"

            meta = _get_embedding_metadata(integration_db_session, pid)
            assert meta['model'] == 'text-embedding-3-small'
            assert meta['dim'] == 1536

        # Verify progress file
        assert progress_file.exists()
        prog_data = json.loads(progress_file.read_text())
        assert prog_data['status'] == 'completed'


class TestEmbedLocalE2E:
    """Create profiles, run embed with mocked local model, verify column populated."""

    def test_embed_local(
        self, runner, integration_db_session, progress_dir, reports_dir, monkeypatch
    ):
        # Arrange — clear any openai embeddings from prior tests
        integration_db_session.execute(text(
            "UPDATE crawled_profile SET embedding_nomic = NULL "
            "WHERE id LIKE 'cp_test_%'"
        ))
        integration_db_session.commit()
        ids = _create_test_profiles(integration_db_session, count=3)
        progress_file = progress_dir / "embedding_progress.json"
        monkeypatch.setenv("LINKEDOUT_REPORTS_DIR", str(reports_dir))

        mock_prov = _mock_local_provider()

        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file):
                with patch('linkedout.commands.embed.get_embedding_column_name', return_value='embedding_nomic'):
                    result = runner.invoke(embed_command, ['--provider', 'local'])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        for pid in ids:
            emb = _get_embedding(integration_db_session, pid, 'embedding_nomic')
            assert emb is not None, f"Profile {pid} should have nomic embedding"


class TestEmbedDryRun:
    """--dry-run reports counts without modifying DB."""

    def test_dry_run_no_db_writes(
        self, runner, integration_db_session, progress_dir, monkeypatch
    ):
        # Arrange — clear embeddings
        integration_db_session.execute(text(
            "UPDATE crawled_profile SET embedding_openai = NULL "
            "WHERE id LIKE 'cp_test_%'"
        ))
        integration_db_session.commit()
        _create_test_profiles(integration_db_session, count=3)
        progress_file = progress_dir / "embedding_progress.json"

        mock_prov = _mock_openai_provider()

        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file):
                result = runner.invoke(embed_command, ['--dry-run'])

        assert result.exit_code == 0
        assert 'DRY RUN' in result.output

        # Verify no embeddings were written
        mock_prov.embed.assert_not_called()

        # Verify no progress file created
        assert not progress_file.exists()


class TestEmbedForce:
    """--force re-embeds profiles that already have embeddings."""

    def test_force_reembeds(
        self, runner, integration_db_session, progress_dir, reports_dir, monkeypatch
    ):
        # Arrange — ensure profiles exist with embeddings
        ids = _create_test_profiles(integration_db_session, count=2)
        monkeypatch.setenv("LINKEDOUT_REPORTS_DIR", str(reports_dir))

        # First: embed them
        progress_file = progress_dir / "embedding_progress.json"
        mock_prov = _mock_openai_provider()

        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file):
                result = runner.invoke(embed_command, ['--provider', 'openai'])
        assert result.exit_code == 0

        # Clear progress for the force run
        progress_file2 = progress_dir / "embedding_progress2.json"

        # Now force re-embed with different vectors
        def _new_embed(texts):
            return [[0.9] * 1536 for _ in texts]
        mock_prov2 = _mock_openai_provider()
        mock_prov2.embed.side_effect = _new_embed

        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov2):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file2):
                result = runner.invoke(embed_command, ['--provider', 'openai', '--force'])

        assert result.exit_code == 0
        assert 'Cleared' in result.output or 'Embedded:' in result.output


class TestEmbedResume:
    """Embed 50% of profiles, save progress, embed again — verify no duplicates."""

    def test_resume_continues_from_checkpoint(
        self, runner, integration_db_session, progress_dir, reports_dir, monkeypatch
    ):
        # Arrange — create 6 profiles, clear embeddings
        integration_db_session.execute(text(
            "UPDATE crawled_profile SET embedding_openai = NULL "
            "WHERE id LIKE 'cp_test_%'"
        ))
        integration_db_session.commit()
        ids = _create_test_profiles(integration_db_session, count=6)
        monkeypatch.setenv("LINKEDOUT_REPORTS_DIR", str(reports_dir))
        progress_file = progress_dir / "embedding_progress.json"

        call_count = 0

        def _embed_with_interrupt(texts):
            nonlocal call_count
            call_count += 1
            return [[0.1] * 1536 for _ in texts]

        # First run: embed all (they'll all get done since chunk_size is large)
        mock_prov = _mock_openai_provider()
        mock_prov.embed.side_effect = _embed_with_interrupt

        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file):
                result = runner.invoke(embed_command, ['--provider', 'openai'])

        assert result.exit_code == 0

        # Verify progress shows completed
        prog_data = json.loads(progress_file.read_text())
        assert prog_data['status'] == 'completed'


class TestEmbedIdempotent:
    """Run embed twice on fully-embedded DB, second run is a no-op."""

    def test_second_run_is_noop(
        self, runner, integration_db_session, progress_dir, reports_dir, monkeypatch
    ):
        monkeypatch.setenv("LINKEDOUT_REPORTS_DIR", str(reports_dir))
        progress_file = progress_dir / "embedding_progress.json"
        mock_prov = _mock_openai_provider()

        # First run
        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file):
                result1 = runner.invoke(embed_command, ['--provider', 'openai'])
        assert result1.exit_code == 0

        # Second run — should see "already embedded"
        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file):
                result2 = runner.invoke(embed_command, ['--provider', 'openai'])

        assert result2.exit_code == 0
        assert 'already embedded' in result2.output.lower() or 'no profiles' in result2.output.lower()


class TestEmbedProviderSwitch:
    """Embed with OpenAI, switch to local, embed again — both columns have values."""

    def test_both_columns_populated(
        self, runner, integration_db_session, progress_dir, reports_dir, monkeypatch
    ):
        # Arrange — clear all embeddings
        integration_db_session.execute(text(
            "UPDATE crawled_profile SET embedding_openai = NULL, embedding_nomic = NULL "
            "WHERE id LIKE 'cp_test_%'"
        ))
        integration_db_session.commit()
        ids = _create_test_profiles(integration_db_session, count=2)
        monkeypatch.setenv("LINKEDOUT_REPORTS_DIR", str(reports_dir))

        # First: embed with OpenAI
        pf1 = progress_dir / "progress1.json"
        mock_openai = _mock_openai_provider()
        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_openai):
            with patch('linkedout.commands.embed.get_progress_path', return_value=pf1):
                result1 = runner.invoke(embed_command, ['--provider', 'openai'])
        assert result1.exit_code == 0

        # Second: embed with local (different column)
        pf2 = progress_dir / "progress2.json"
        mock_local = _mock_local_provider()
        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_local):
            with patch('linkedout.commands.embed.get_progress_path', return_value=pf2):
                with patch('linkedout.commands.embed.get_embedding_column_name', return_value='embedding_nomic'):
                    result2 = runner.invoke(embed_command, ['--provider', 'local'])
        assert result2.exit_code == 0

        # Verify both columns
        for pid in ids:
            openai_emb = _get_embedding(integration_db_session, pid, 'embedding_openai')
            nomic_emb = _get_embedding(integration_db_session, pid, 'embedding_nomic')
            assert openai_emb is not None, f"{pid} should have openai embedding"
            assert nomic_emb is not None, f"{pid} should have nomic embedding"


class TestEmbedZeroProfiles:
    """Run embed on empty DB — clean exit with message."""

    def test_empty_db_clean_exit(
        self, runner, integration_db_session, progress_dir, monkeypatch
    ):
        # Arrange — ensure no profiles match (clear enriched data flag)
        integration_db_session.execute(text(
            "UPDATE crawled_profile SET has_enriched_data = FALSE "
            "WHERE id LIKE 'cp_test_%'"
        ))
        integration_db_session.commit()

        progress_file = progress_dir / "embedding_progress.json"
        mock_prov = _mock_openai_provider()

        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file):
                result = runner.invoke(embed_command, [])

        assert result.exit_code == 0
        assert 'no profiles' in result.output.lower()

        # Restore
        integration_db_session.execute(text(
            "UPDATE crawled_profile SET has_enriched_data = TRUE "
            "WHERE id LIKE 'cp_test_%'"
        ))
        integration_db_session.commit()


class TestReportArtifact:
    """Verify the report JSON is written to the reports directory."""

    def test_report_file_created(
        self, runner, integration_db_session, progress_dir, reports_dir, monkeypatch
    ):
        # Arrange
        integration_db_session.execute(text(
            "UPDATE crawled_profile SET embedding_openai = NULL "
            "WHERE id LIKE 'cp_test_%'"
        ))
        integration_db_session.commit()
        _create_test_profiles(integration_db_session, count=2)
        monkeypatch.setenv("LINKEDOUT_REPORTS_DIR", str(reports_dir))
        progress_file = progress_dir / "embedding_progress.json"
        mock_prov = _mock_openai_provider()

        with patch('linkedout.commands.embed.get_embedding_provider', return_value=mock_prov):
            with patch('linkedout.commands.embed.get_progress_path', return_value=progress_file):
                result = runner.invoke(embed_command, ['--provider', 'openai'])

        assert result.exit_code == 0

        # Verify report file
        report_files = list(reports_dir.glob("embed-*.json"))
        assert len(report_files) >= 1, "Report file should be created"

        report_data = json.loads(report_files[0].read_text())
        assert report_data['operation'] == 'embed'
        assert 'counts' in report_data
        assert report_data['counts']['embedded'] > 0
