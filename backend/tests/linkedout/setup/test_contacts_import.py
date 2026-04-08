# SPDX-License-Identifier: Apache-2.0
"""Tests for contacts import setup module."""
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedout.setup.contacts_import import (
    find_contacts_file,
    prompt_contacts_import,
    run_contacts_import,
    setup_contacts_import,
)


class TestFindContactsFile:
    def test_finds_google_contacts_csv(self, tmp_path):
        csv_file = tmp_path / "contacts.csv"
        csv_file.write_text("Name,Email\nJohn,john@example.com\n")

        result = find_contacts_file("google", downloads_dir=tmp_path)

        assert result == csv_file

    def test_finds_google_csv_with_google_prefix(self, tmp_path):
        csv_file = tmp_path / "google-contacts.csv"
        csv_file.write_text("Name,Email\n")

        result = find_contacts_file("google", downloads_dir=tmp_path)

        assert result == csv_file

    def test_finds_icloud_vcf(self, tmp_path):
        vcf_file = tmp_path / "contacts.vcf"
        vcf_file.write_text("BEGIN:VCARD\nFN:John Doe\nEND:VCARD\n")

        result = find_contacts_file("icloud", downloads_dir=tmp_path)

        assert result == vcf_file

    def test_returns_none_for_google_when_no_csv(self, tmp_path):
        (tmp_path / "notes.txt").write_text("not contacts")

        result = find_contacts_file("google", downloads_dir=tmp_path)

        assert result is None

    def test_returns_none_for_icloud_when_no_vcf(self, tmp_path):
        (tmp_path / "contacts.csv").write_text("csv not vcf")

        result = find_contacts_file("icloud", downloads_dir=tmp_path)

        assert result is None

    def test_returns_none_for_nonexistent_dir(self):
        result = find_contacts_file("google", downloads_dir=Path("/nonexistent"))

        assert result is None


class TestPromptContactsImport:
    @patch("builtins.input", return_value="y")
    def test_returns_true_when_yes(self, _):
        assert prompt_contacts_import() is True

    @patch("builtins.input", return_value="yes")
    def test_returns_true_when_yes_full(self, _):
        assert prompt_contacts_import() is True

    @patch("builtins.input", return_value="")
    def test_returns_false_on_empty_default_no(self, _):
        assert prompt_contacts_import() is False

    @patch("builtins.input", return_value="n")
    def test_returns_false_when_no(self, _):
        assert prompt_contacts_import() is False


class TestRunContactsImport:
    @patch("linkedout.setup.contacts_import.subprocess.run")
    def test_calls_import_contacts_with_format(self, mock_run, tmp_path):
        contacts_file = tmp_path / "contacts.csv"
        contacts_file.write_text("data")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Imported 50 contacts"
        mock_run.return_value.stderr = ""

        report = run_contacts_import(contacts_file, "google")

        assert report.counts.succeeded == 1
        call_args = mock_run.call_args[0][0]
        assert "import-contacts" in call_args
        assert "--format" in call_args
        assert "google" in call_args

    @patch("linkedout.setup.contacts_import.subprocess.run")
    def test_calls_with_icloud_format(self, mock_run, tmp_path):
        vcf_file = tmp_path / "contacts.vcf"
        vcf_file.write_text("data")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        run_contacts_import(vcf_file, "icloud")

        call_args = mock_run.call_args[0][0]
        assert "icloud" in call_args

    def test_raises_for_missing_file(self, tmp_path):
        missing = tmp_path / "does-not-exist.csv"

        with pytest.raises(FileNotFoundError, match="Contacts file not found"):
            run_contacts_import(missing, "google")


class TestSetupContactsImport:
    @patch("builtins.input", return_value="n")
    def test_declining_returns_skip_status(self, _, tmp_path):
        report = setup_contacts_import(tmp_path)

        assert report.counts.skipped == 1
        assert report.counts.succeeded == 0
