# SPDX-License-Identifier: Apache-2.0
"""Tests for the skill detection and installation module."""
from pathlib import Path
from unittest.mock import patch

from linkedout.setup.skill_install import (
    PlatformInfo,
    detect_platforms,
    generate_skills,
    install_skills_for_platform,
)


class TestDetectPlatforms:
    @patch("linkedout.setup.skill_install.Path.home")
    def test_detects_claude_code_when_dir_exists(self, mock_home, tmp_path):
        mock_home.return_value = tmp_path
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        platforms = detect_platforms()

        names = [p.name for p in platforms]
        assert "Claude Code" in names

    @patch("linkedout.setup.skill_install.Path.home")
    def test_returns_empty_when_no_platforms(self, mock_home, tmp_path):
        mock_home.return_value = tmp_path
        # No platform directories created

        platforms = detect_platforms()

        assert platforms == []

    @patch("linkedout.setup.skill_install.Path.home")
    def test_detects_multiple_platforms(self, mock_home, tmp_path):
        mock_home.return_value = tmp_path
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".agents").mkdir()

        platforms = detect_platforms()

        names = {p.name for p in platforms}
        assert "Claude Code" in names
        assert "Codex" in names

    @patch("linkedout.setup.skill_install.Path.home")
    def test_platform_info_has_correct_paths(self, mock_home, tmp_path):
        mock_home.return_value = tmp_path
        (tmp_path / ".claude").mkdir()

        platforms = detect_platforms()
        claude = [p for p in platforms if p.name == "Claude Code"][0]

        assert claude.config_dir == tmp_path / ".claude"
        assert claude.skill_install_dir == tmp_path / ".claude" / "skills" / "linkedout"


class TestGenerateSkills:
    @patch("linkedout.setup.skill_install.subprocess.run")
    def test_calls_generate_skills_script(self, mock_run, tmp_path):
        # Create the script file
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        script = bin_dir / "generate-skills"
        script.write_text("#!/usr/bin/env python3\nprint('ok')")

        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Generated 4 files"
        mock_run.return_value.stderr = ""

        result = generate_skills(tmp_path)

        assert result is True
        mock_run.assert_called_once()

    def test_returns_false_when_script_missing(self, tmp_path):
        result = generate_skills(tmp_path)

        assert result is False

    @patch("linkedout.setup.skill_install.subprocess.run")
    def test_returns_false_on_script_failure(self, mock_run, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "generate-skills").write_text("#!/bin/bash")

        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Template error"

        result = generate_skills(tmp_path)

        assert result is False


class TestInstallSkillsForPlatform:
    def test_copies_files_to_target_directory(self, tmp_path):
        # Set up source (generated) skill files
        repo_root = tmp_path / "repo"
        generated = repo_root / "skills" / "claude-code" / "linkedout"
        generated.mkdir(parents=True)
        (generated / "SKILL.md").write_text("# Test Skill")
        (generated / "README.md").write_text("# Readme")

        # Set up target
        target = tmp_path / "home" / ".claude" / "skills" / "linkedout"

        platform = PlatformInfo(
            name="Claude Code",
            config_dir=tmp_path / "home" / ".claude",
            skill_install_dir=target,
            dispatch_file=tmp_path / "home" / ".claude" / "CLAUDE.md",
            generated_dir=Path("skills/claude-code"),
        )

        result = install_skills_for_platform(platform, repo_root)

        assert result is True
        assert (target / "linkedout" / "SKILL.md").exists()
        assert (target / "linkedout" / "README.md").exists()

    def test_returns_false_when_source_missing(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        platform = PlatformInfo(
            name="Claude Code",
            config_dir=tmp_path / ".claude",
            skill_install_dir=tmp_path / ".claude" / "skills" / "linkedout",
            dispatch_file=tmp_path / ".claude" / "CLAUDE.md",
            generated_dir=Path("skills/claude-code"),
        )

        result = install_skills_for_platform(platform, repo_root)

        assert result is False

    def test_creates_target_directory(self, tmp_path):
        repo_root = tmp_path / "repo"
        generated = repo_root / "skills" / "codex" / "test"
        generated.mkdir(parents=True)
        (generated / "SKILL.md").write_text("# Skill")

        target = tmp_path / "target" / "deep" / "path"

        platform = PlatformInfo(
            name="Codex",
            config_dir=tmp_path / ".agents",
            skill_install_dir=target,
            dispatch_file=tmp_path / ".agents" / "AGENTS.md",
            generated_dir=Path("skills/codex"),
        )

        result = install_skills_for_platform(platform, repo_root)

        assert result is True
        assert target.exists()
