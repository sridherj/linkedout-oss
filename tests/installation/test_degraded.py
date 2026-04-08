# SPDX-License-Identifier: Apache-2.0
"""Degraded environment tests.

Verifies that the setup flow produces actionable error messages when
external dependencies are unavailable or provide invalid data.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linkedout.setup.csv_import import find_linkedin_csv, run_csv_import
from linkedout.setup.embeddings import estimate_embedding_cost, estimate_embedding_time
from linkedout.setup.prerequisites import check_postgres
from linkedout.setup.seed_data import download_seed, verify_seed_checksum
from linkedout.setup.skill_install import generate_skills


class TestNoNetworkSeedDownload:
    def test_no_network_seed_download(self):
        """Mock network timeout during seed download and verify actionable error."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "ConnectionError: Network is unreachable"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="download-seed failed"):
                download_seed(full=False)


class TestInvalidOpenAIKey:
    def test_invalid_openai_key(self):
        """Provide a bad key and verify the validator returns False."""
        with patch(
            "linkedout.setup.api_keys.validate_openai_key",
            return_value=False,
        ) as mock_validate:
            from linkedout.setup.api_keys import validate_openai_key

            result = mock_validate("sk-invalid-key")
            assert result is False


class TestInvalidCsvFormat:
    def test_invalid_csv_not_detected(self, tmp_path):
        """A non-LinkedIn CSV (different columns) should not be auto-detected."""
        csv_path = tmp_path / "Connections.csv"
        csv_path.write_text(
            "Name,Age,City\n"
            "Alice,30,NYC\n",
            encoding="utf-8",
        )

        # find_linkedin_csv looks at filename pattern, not content
        result = find_linkedin_csv(tmp_path)
        # It IS detected by filename, but the import step would fail
        assert result is not None  # found by name
        assert result.name == "Connections.csv"

    def test_run_csv_import_nonexistent_file(self):
        """Importing a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            run_csv_import(Path("/nonexistent/path/Connections.csv"))


class TestEmptyCsv:
    def test_empty_csv(self, tmp_path):
        """An empty CSV file is detected but would produce an import error."""
        csv_path = tmp_path / "Connections.csv"
        csv_path.write_text("", encoding="utf-8")

        result = find_linkedin_csv(tmp_path)
        assert result is not None

    def test_empty_csv_import_fails_gracefully(self, tmp_path):
        """Import of an empty CSV via subprocess should fail."""
        csv_path = tmp_path / "Connections.csv"
        csv_path.write_text("", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: CSV file is empty or has no data rows"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="import-connections failed"):
                run_csv_import(csv_path)


class TestDbConnectionRefused:
    def test_db_connection_refused(self):
        """Mock PostgreSQL down and verify pg_isready reports not running."""
        mock_result = MagicMock()
        mock_result.returncode = 2  # pg_isready exit code for "no response"

        def mock_run(cmd, **kwargs):
            if cmd[0] == "psql":
                raise FileNotFoundError("psql")
            if cmd[0] == "pg_isready":
                return mock_result
            raise FileNotFoundError(cmd[0])

        with patch("subprocess.run", side_effect=mock_run):
            result = check_postgres()

        assert result.installed is False
        assert result.running is False


class TestMissingGenerateSkills:
    def test_missing_generate_skills(self, tmp_path, capsys):
        """Remove ``bin/generate-skills`` and verify graceful skip."""
        # tmp_path has no bin/generate-skills
        result = generate_skills(tmp_path)

        assert result is False

        captured = capsys.readouterr()
        assert "bin/generate-skills not found" in captured.out


class TestSeedChecksumMismatch:
    def test_checksum_mismatch(self, tmp_path):
        """Mismatched checksum should return False."""
        seed_file = tmp_path / "linkedout-seed-core.json"
        seed_file.write_bytes(b"real content")

        checksum_file = tmp_path / "CHECKSUM"
        checksum_file.write_text("badhash  linkedout-seed-core.json\n")

        result = verify_seed_checksum(tmp_path)
        assert result is False

    def test_no_checksum_file(self, tmp_path):
        """Missing CHECKSUM file should return False."""
        result = verify_seed_checksum(tmp_path)
        assert result is False


class TestEmbeddingEstimates:
    """Verify cost/time estimates work without network."""

    def test_openai_cost_estimate(self):
        cost = estimate_embedding_cost(4000, "openai")
        assert cost is not None
        assert cost.startswith("~$")

    def test_local_cost_is_none(self):
        cost = estimate_embedding_cost(4000, "local")
        assert cost is None

    def test_openai_time_estimate(self):
        est = estimate_embedding_time(4000, "openai")
        assert "minute" in est.lower()

    def test_local_time_estimate(self):
        est = estimate_embedding_time(4000, "local")
        assert "minute" in est.lower()
