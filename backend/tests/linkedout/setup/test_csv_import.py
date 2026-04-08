# SPDX-License-Identifier: Apache-2.0
"""Tests for LinkedIn CSV import setup module."""
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedout.setup.csv_import import (
    copy_to_uploads,
    find_linkedin_csv,
    run_csv_import,
)


class TestFindLinkedinCsv:
    def test_finds_connections_csv(self, tmp_path):
        csv_file = tmp_path / "Connections.csv"
        csv_file.write_text("First Name,Last Name\nJohn,Doe\n")

        result = find_linkedin_csv(downloads_dir=tmp_path)

        assert result == csv_file

    def test_returns_none_when_no_match(self, tmp_path):
        (tmp_path / "notes.txt").write_text("not a csv")

        result = find_linkedin_csv(downloads_dir=tmp_path)

        assert result is None

    def test_finds_lowercase_connections_csv(self, tmp_path):
        csv_file = tmp_path / "connections.csv"
        csv_file.write_text("First Name,Last Name\nJane,Smith\n")

        result = find_linkedin_csv(downloads_dir=tmp_path)

        assert result == csv_file

    def test_returns_most_recent_when_multiple(self, tmp_path):
        import time

        old_file = tmp_path / "Connections_old.csv"
        old_file.write_text("old")
        time.sleep(0.05)  # Ensure different mtime
        new_file = tmp_path / "Connections.csv"
        new_file.write_text("new")

        result = find_linkedin_csv(downloads_dir=tmp_path)

        assert result == new_file

    def test_returns_none_for_nonexistent_dir(self):
        result = find_linkedin_csv(downloads_dir=Path("/nonexistent/path"))

        assert result is None

    def test_ignores_non_csv_connections_file(self, tmp_path):
        (tmp_path / "Connections.xlsx").write_text("not csv")

        result = find_linkedin_csv(downloads_dir=tmp_path)

        assert result is None


class TestCopyToUploads:
    def test_copies_file_to_uploads_dir(self, tmp_path):
        csv_file = tmp_path / "source" / "Connections.csv"
        csv_file.parent.mkdir()
        csv_file.write_text("data")
        data_dir = tmp_path / "linkedout-data"

        result = copy_to_uploads(csv_file, data_dir)

        assert result == data_dir / "uploads" / "Connections.csv"
        assert result.read_text() == "data"

    def test_creates_uploads_dir_if_missing(self, tmp_path):
        csv_file = tmp_path / "Connections.csv"
        csv_file.write_text("data")
        data_dir = tmp_path / "linkedout-data"

        result = copy_to_uploads(csv_file, data_dir)

        assert (data_dir / "uploads").is_dir()
        assert result.exists()

    def test_returns_existing_if_same_location(self, tmp_path):
        data_dir = tmp_path / "linkedout-data"
        uploads_dir = data_dir / "uploads"
        uploads_dir.mkdir(parents=True)
        csv_file = uploads_dir / "Connections.csv"
        csv_file.write_text("data")

        result = copy_to_uploads(csv_file, data_dir)

        assert result == csv_file


class TestRunCsvImport:
    @patch("linkedout.setup.csv_import.subprocess.run")
    def test_calls_import_connections_command(self, mock_run, tmp_path):
        csv_file = tmp_path / "Connections.csv"
        csv_file.write_text("data")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Imported 100 profiles"
        mock_run.return_value.stderr = ""

        report = run_csv_import(csv_file)

        assert report.counts.succeeded == 1
        call_args = mock_run.call_args[0][0]
        assert "import-connections" in call_args
        assert str(csv_file) in call_args

    def test_raises_for_missing_csv(self, tmp_path):
        missing = tmp_path / "does-not-exist.csv"

        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            run_csv_import(missing)

    @patch("linkedout.setup.csv_import.subprocess.run")
    def test_raises_on_command_failure(self, mock_run, tmp_path):
        csv_file = tmp_path / "Connections.csv"
        csv_file.write_text("data")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Parse error"
        mock_run.return_value.stdout = ""

        with pytest.raises(RuntimeError, match="import-connections failed"):
            run_csv_import(csv_file)
