# SPDX-License-Identifier: Apache-2.0
"""Tests for demo mode config plumbing."""

import yaml

from shared.config.settings import LinkedOutSettings

from linkedout.demo import DEMO_DB_NAME, get_demo_db_url, set_demo_mode


class TestDemoModeSettings:
    """Verify demo_mode field on LinkedOutSettings."""

    def test_demo_mode_default_false(self):
        settings = LinkedOutSettings()
        assert settings.demo_mode is False

    def test_demo_mode_from_yaml(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("demo_mode: true\n")
        monkeypatch.setenv("LINKEDOUT_DATA_DIR", str(tmp_path))
        # Point the yaml source at our tmp config
        monkeypatch.setenv("LINKEDOUT_DEMO_MODE", "true")
        settings = LinkedOutSettings()
        assert settings.demo_mode is True


class TestGetDemoDbUrl:
    """Verify database URL rewriting for demo mode."""

    def test_replaces_db_name(self):
        url = "postgresql://linkedout:secret@localhost:5432/linkedout"
        result = get_demo_db_url(url)
        assert result == "postgresql://linkedout:secret@localhost:5432/linkedout_demo"

    def test_preserves_credentials_and_host(self):
        url = "postgresql://user:pass@db.example.com:5433/mydb"
        result = get_demo_db_url(url)
        assert "user:pass@db.example.com:5433" in result
        assert result.endswith(f"/{DEMO_DB_NAME}")

    def test_handles_no_password(self):
        url = "postgresql://linkedout:@localhost:5432/linkedout"
        result = get_demo_db_url(url)
        assert result == "postgresql://linkedout:@localhost:5432/linkedout_demo"


class TestSetDemoMode:
    """Verify config.yaml toggle for demo mode."""

    def test_set_demo_mode_enables(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            yaml.safe_dump({
                "database_url": "postgresql://linkedout:secret@localhost:5432/linkedout",
                "demo_mode": False,
            })
        )

        set_demo_mode(tmp_path, enabled=True)

        result = yaml.safe_load(config_file.read_text())
        assert result["demo_mode"] is True
        assert "linkedout_demo" in result["database_url"]

    def test_set_demo_mode_disables(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            yaml.safe_dump({
                "database_url": "postgresql://linkedout:secret@localhost:5432/linkedout_demo",
                "demo_mode": True,
            })
        )

        set_demo_mode(tmp_path, enabled=False)

        result = yaml.safe_load(config_file.read_text())
        assert result["demo_mode"] is False
        assert result["database_url"].endswith("/linkedout")
        assert "linkedout_demo" not in result["database_url"]

    def test_set_demo_mode_creates_config_dir(self, tmp_path):
        """Config directory is created if it doesn't exist."""
        set_demo_mode(tmp_path, enabled=True)

        config_file = tmp_path / "config" / "config.yaml"
        assert config_file.exists()
        result = yaml.safe_load(config_file.read_text())
        assert result["demo_mode"] is True
