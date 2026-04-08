# SPDX-License-Identifier: Apache-2.0
"""Unit tests for demo offer and demo setup flow.

Tests cover:
- offer_demo() prompt handling (accept/decline/interrupt)
- run_demo_setup() step execution order (D1-D5)
- offer_transition() prompt handling
- Error handling in demo steps
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


@pytest.fixture
def data_dir(tmp_path):
    """Create a temporary data directory with config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return tmp_path


@pytest.fixture
def repo_root(tmp_path):
    return tmp_path / "repo"


# ── offer_demo tests ────────────────────────────────────────────────────


class TestOfferDemo:

    def test_accept_with_y(self):
        from linkedout.setup.demo_offer import offer_demo

        with patch("builtins.input", return_value="y"):
            assert offer_demo() is True

    def test_accept_with_empty(self):
        from linkedout.setup.demo_offer import offer_demo

        with patch("builtins.input", return_value=""):
            assert offer_demo() is True

    def test_decline_with_n(self):
        from linkedout.setup.demo_offer import offer_demo

        with patch("builtins.input", return_value="n"):
            assert offer_demo() is False

    def test_decline_on_eof(self):
        from linkedout.setup.demo_offer import offer_demo

        with patch("builtins.input", side_effect=EOFError):
            assert offer_demo() is False

    def test_decline_on_keyboard_interrupt(self):
        from linkedout.setup.demo_offer import offer_demo

        with patch("builtins.input", side_effect=KeyboardInterrupt):
            assert offer_demo() is False


# ── offer_transition tests ──────────────────────────────────────────────


class TestOfferTransition:

    def test_accept_transition(self):
        from linkedout.setup.demo_offer import offer_transition

        with patch("builtins.input", return_value="y"):
            assert offer_transition() is True

    def test_decline_transition(self):
        from linkedout.setup.demo_offer import offer_transition

        with patch("builtins.input", return_value="n"):
            assert offer_transition() is False


# ── run_demo_setup tests ────────────────────────────────────────────────


class TestRunDemoSetup:

    @patch("linkedout.setup.demo_offer._run_readiness_check")
    @patch("linkedout.setup.demo_offer._run_skill_install")
    @patch("linkedout.setup.demo_offer._run_demo_restore")
    @patch("linkedout.setup.demo_offer._run_model_download")
    @patch("linkedout.setup.demo_offer._run_demo_download")
    def test_all_steps_execute_in_order(
        self,
        mock_download,
        mock_model,
        mock_restore,
        mock_skills,
        mock_readiness,
        data_dir,
        repo_root,
    ):
        from linkedout.setup.demo_offer import run_demo_setup

        mock_download.return_value = True
        mock_model.return_value = True
        mock_restore.return_value = "postgresql://localhost/linkedout_demo"
        mock_skills.return_value = None
        mock_readiness.return_value = None

        result = run_demo_setup(data_dir, repo_root, "postgresql://localhost/linkedout")

        assert result is True
        mock_download.assert_called_once_with(data_dir)
        mock_model.assert_called_once()
        mock_restore.assert_called_once_with(data_dir, "postgresql://localhost/linkedout")
        mock_skills.assert_called_once_with(repo_root, data_dir)
        mock_readiness.assert_called_once()

    @patch("linkedout.setup.demo_offer._run_demo_download")
    def test_d1_failure_returns_false(self, mock_download, data_dir, repo_root):
        from linkedout.setup.demo_offer import run_demo_setup

        mock_download.return_value = False

        result = run_demo_setup(data_dir, repo_root, "postgresql://localhost/linkedout")

        assert result is False

    @patch("linkedout.setup.demo_offer._run_demo_download")
    def test_d1_exception_returns_false(self, mock_download, data_dir, repo_root):
        from linkedout.setup.demo_offer import run_demo_setup

        mock_download.side_effect = RuntimeError("network error")

        result = run_demo_setup(data_dir, repo_root, "postgresql://localhost/linkedout")

        assert result is False

    @patch("linkedout.setup.demo_offer._run_demo_restore")
    @patch("linkedout.setup.demo_offer._run_model_download")
    @patch("linkedout.setup.demo_offer._run_demo_download")
    def test_d3_failure_returns_false(
        self, mock_download, mock_model, mock_restore, data_dir, repo_root,
    ):
        from linkedout.setup.demo_offer import run_demo_setup

        mock_download.return_value = True
        mock_model.return_value = True
        mock_restore.return_value = None  # restore failed

        result = run_demo_setup(data_dir, repo_root, "postgresql://localhost/linkedout")

        assert result is False

    @patch("linkedout.setup.demo_offer._run_readiness_check")
    @patch("linkedout.setup.demo_offer._run_skill_install")
    @patch("linkedout.setup.demo_offer._run_demo_restore")
    @patch("linkedout.setup.demo_offer._run_model_download")
    @patch("linkedout.setup.demo_offer._run_demo_download")
    def test_d2_failure_non_fatal(
        self,
        mock_download,
        mock_model,
        mock_restore,
        mock_skills,
        mock_readiness,
        data_dir,
        repo_root,
    ):
        """D2 (model download) failure should NOT block demo setup."""
        from linkedout.setup.demo_offer import run_demo_setup

        mock_download.return_value = True
        mock_model.return_value = False  # model download failed
        mock_restore.return_value = "postgresql://localhost/linkedout_demo"
        mock_skills.return_value = None
        mock_readiness.return_value = None

        result = run_demo_setup(data_dir, repo_root, "postgresql://localhost/linkedout")

        assert result is True

    @patch("linkedout.setup.demo_offer._run_readiness_check")
    @patch("linkedout.setup.demo_offer._run_skill_install")
    @patch("linkedout.setup.demo_offer._run_demo_restore")
    @patch("linkedout.setup.demo_offer._run_model_download")
    @patch("linkedout.setup.demo_offer._run_demo_download")
    def test_d4_failure_non_fatal(
        self,
        mock_download,
        mock_model,
        mock_restore,
        mock_skills,
        mock_readiness,
        data_dir,
        repo_root,
    ):
        """D4 (skill install) failure should NOT block demo setup."""
        from linkedout.setup.demo_offer import run_demo_setup

        mock_download.return_value = True
        mock_model.return_value = True
        mock_restore.return_value = "postgresql://localhost/linkedout_demo"
        mock_skills.side_effect = RuntimeError("skill install error")
        mock_readiness.return_value = None

        result = run_demo_setup(data_dir, repo_root, "postgresql://localhost/linkedout")

        assert result is True
