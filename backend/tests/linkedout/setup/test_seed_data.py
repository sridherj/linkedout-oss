# SPDX-License-Identifier: Apache-2.0
"""Tests for seed data setup module."""
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedout.setup.seed_data import (
    download_seed,
    import_seed,
    verify_seed_checksum,
)


class TestDownloadSeed:
    @patch("linkedout.setup.seed_data.subprocess.run")
    def test_download_calls_download_seed(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Downloaded seed"
        mock_run.return_value.stderr = ""

        report = download_seed()

        assert report.counts.succeeded == 1
        call_args = mock_run.call_args[0][0]
        assert "download-seed" in call_args

    @patch("linkedout.setup.seed_data.subprocess.run")
    def test_raises_on_failure(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Network error"
        mock_run.return_value.stdout = ""

        with pytest.raises(RuntimeError, match="download-seed failed"):
            download_seed()


class TestImportSeed:
    @patch("linkedout.setup.seed_data.subprocess.run")
    def test_calls_import_seed_command(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Imported 10 tables"
        mock_run.return_value.stderr = ""

        report = import_seed()

        assert report.counts.succeeded == 1
        call_args = mock_run.call_args[0][0]
        assert "import-seed" in call_args

    @patch("linkedout.setup.seed_data.subprocess.run")
    def test_raises_on_failure(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "DB connection failed"
        mock_run.return_value.stdout = ""

        with pytest.raises(RuntimeError, match="import-seed failed"):
            import_seed()


class TestVerifySeedChecksum:
    def test_returns_true_for_matching_checksum(self, tmp_path):
        # Write a seed file
        seed_file = tmp_path / "seed.dump"
        seed_file.write_bytes(b"test seed data")

        # Compute its real SHA256
        import hashlib
        expected = hashlib.sha256(b"test seed data").hexdigest()

        # Write CHECKSUM file (GNU coreutils format)
        checksum_file = tmp_path / "CHECKSUM"
        checksum_file.write_text(f"{expected}  seed.dump\n")

        assert verify_seed_checksum(tmp_path) is True

    def test_returns_false_for_mismatched_checksum(self, tmp_path):
        seed_file = tmp_path / "seed.dump"
        seed_file.write_bytes(b"test seed data")

        checksum_file = tmp_path / "CHECKSUM"
        checksum_file.write_text("0000000000000000000000000000000000000000000000000000000000000000  seed.dump\n")

        assert verify_seed_checksum(tmp_path) is False

    def test_returns_false_when_no_checksum_file(self, tmp_path):
        assert verify_seed_checksum(tmp_path) is False

    def test_returns_false_when_seed_file_missing(self, tmp_path):
        checksum_file = tmp_path / "CHECKSUM"
        checksum_file.write_text("abcd1234  missing.dump\n")

        assert verify_seed_checksum(tmp_path) is False
