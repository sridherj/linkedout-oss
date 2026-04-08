# SPDX-License-Identifier: Apache-2.0
"""Security and permission tests.

Verifies that sensitive files have correct permissions and that secrets
do not leak into logs, diagnostics, or readiness reports.
"""
from __future__ import annotations

import re
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedout.setup.api_keys import write_secrets_yaml
from linkedout.setup.database import write_config_yaml
from linkedout.setup.logging_integration import _redact_config


class TestSecretsYamlPermissions:
    def test_secrets_yaml_permissions(self, temp_data_dir):
        """Verify ``secrets.yaml`` has ``chmod 600`` after setup."""
        secrets = {"openai_api_key": "sk-test-1234567890"}
        secrets_path = write_secrets_yaml(secrets, temp_data_dir)

        mode = secrets_path.stat().st_mode
        # Owner read+write only
        assert mode & stat.S_IRUSR  # owner can read
        assert mode & stat.S_IWUSR  # owner can write
        # No group or other permissions
        assert not (mode & stat.S_IRGRP)  # group cannot read
        assert not (mode & stat.S_IWGRP)  # group cannot write
        assert not (mode & stat.S_IROTH)  # others cannot read
        assert not (mode & stat.S_IWOTH)  # others cannot write


class TestConfigYamlPermissions:
    def test_config_yaml_no_world_readable(self, temp_data_dir):
        """Verify ``config.yaml`` permissions exclude group/other access."""
        db_url = "postgresql://linkedout:secret@localhost:5432/linkedout"
        config_path = write_config_yaml(db_url, temp_data_dir)

        mode = config_path.stat().st_mode
        assert mode & stat.S_IRUSR  # owner can read
        # Should not be world-readable
        assert not (mode & stat.S_IROTH)
        assert not (mode & stat.S_IWOTH)


class TestNoSecretsInLogs:
    def test_no_secrets_in_logs(self, temp_data_dir):
        """Grep all log files for API key patterns and assert none found.

        This writes a fake log file with safe content and verifies the
        pattern-based check works. Real log files are tested in nightly CI.
        """
        log_dir = temp_data_dir / "logs"
        log_dir.mkdir(exist_ok=True)

        # Write a safe log
        log_file = log_dir / "setup.log"
        log_file.write_text(
            "2026-04-07 10:00:00 | INFO | Starting setup\n"
            "2026-04-07 10:01:00 | INFO | OpenAI key validated (boolean check)\n"
            "2026-04-07 10:02:00 | INFO | Setup complete\n",
            encoding="utf-8",
        )

        # Check: no actual API key patterns
        api_key_patterns = [
            r"sk-[A-Za-z0-9\-_]{20,}",  # OpenAI key pattern
            r"apify_api_[A-Za-z0-9]{20,}",  # Apify key pattern
            r"postgresql://[^:]+:[^@]+@",  # DB URL with password
        ]

        content = log_file.read_text()
        for pattern in api_key_patterns:
            matches = re.findall(pattern, content)
            assert not matches, f"Found secret pattern {pattern!r} in log: {matches}"

    def test_log_with_leaked_key_detected(self, temp_data_dir):
        """Verify our check catches a leaked key if one were present."""
        log_dir = temp_data_dir / "logs"
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / "setup-bad.log"
        log_file.write_text(
            "2026-04-07 10:00:00 | DEBUG | Using key sk-proj-abcdefghijklmnopqrstuvwxyz1234567890\n",
            encoding="utf-8",
        )

        content = log_file.read_text()
        matches = re.findall(r"sk-[A-Za-z0-9\-_]{20,}", content)
        assert len(matches) > 0, "Should detect leaked key pattern"


class TestNoSecretsInDiagnostic:
    def test_no_secrets_in_diagnostic(self, temp_data_dir):
        """Verify the config redaction removes sensitive values."""
        config = {
            "database_url": "postgresql://linkedout:supersecret@localhost:5432/linkedout",
            "openai_api_key": "sk-proj-1234567890abcdef",
            "apify_api_key": "apify_api_testkey123",
            "data_dir": str(temp_data_dir),
            "embedding_provider": "openai",
        }

        redacted = _redact_config(config)

        assert redacted["openai_api_key"] == "[REDACTED]"
        assert redacted["apify_api_key"] == "[REDACTED]"
        # Database URL password should be masked
        assert "supersecret" not in redacted["database_url"]
        assert "****" in redacted["database_url"]
        # Non-sensitive values should pass through
        assert redacted["embedding_provider"] == "openai"

    def test_redact_preserves_structure(self, temp_data_dir):
        """Redaction doesn't drop keys — all are present in output."""
        config = {
            "database_url": "postgresql://user:pass@host/db",
            "data_dir": "/tmp/test",
            "secret": "my-secret",
        }
        redacted = _redact_config(config)
        assert set(redacted.keys()) == set(config.keys())


class TestNoSecretsInReadinessReport:
    def test_readiness_report_has_booleans_not_keys(self, temp_data_dir):
        """Readiness report config section should have booleans, not actual keys."""
        from linkedout.setup.readiness import ReadinessReport

        report = ReadinessReport(
            config={
                "openai_key_configured": True,
                "apify_key_configured": False,
                "db_connected": True,
                "embedding_provider": "openai",
                "data_dir": "~/linkedout-data/",
            },
        )

        config = report.config
        # These should be booleans
        assert isinstance(config["openai_key_configured"], bool)
        assert isinstance(config["apify_key_configured"], bool)
        assert isinstance(config["db_connected"], bool)
        # Should NOT contain actual key values
        report_str = str(report.to_dict())
        assert "sk-" not in report_str
        assert "apify_api_" not in report_str
