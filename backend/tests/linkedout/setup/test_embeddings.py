# SPDX-License-Identifier: Apache-2.0
"""Tests for embedding generation setup module."""
from unittest.mock import patch

import pytest

from linkedout.setup.embeddings import (
    count_profiles_needing_embeddings,
    estimate_embedding_cost,
    estimate_embedding_time,
    run_embeddings,
)


class TestCountProfilesNeedingEmbeddings:
    @patch("linkedout.setup.embeddings.subprocess.run")
    def test_parses_count_from_dry_run(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            "--- DRY RUN ---\n"
            "  Profiles needing embedding: 4,012\n"
            "  Provider: text-embedding-3-small (1536d, openai)\n"
        )
        mock_run.return_value.stderr = ""

        result = count_profiles_needing_embeddings("postgresql://localhost/test")

        assert result == 4012

    @patch("linkedout.setup.embeddings.subprocess.run")
    def test_returns_zero_on_failure(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "DB error"

        result = count_profiles_needing_embeddings("postgresql://localhost/test")

        assert result == 0

    @patch("linkedout.setup.embeddings.subprocess.run")
    def test_returns_zero_when_no_parseable_count(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "No profiles need embedding."
        mock_run.return_value.stderr = ""

        result = count_profiles_needing_embeddings("postgresql://localhost/test")

        assert result == 0


class TestEstimateEmbeddingTime:
    def test_openai_returns_human_readable_string(self):
        result = estimate_embedding_time(1000, "openai")

        assert isinstance(result, str)
        assert "minute" in result.lower()

    def test_local_returns_longer_estimate_than_openai(self):
        local = estimate_embedding_time(1000, "local")
        openai = estimate_embedding_time(1000, "openai")

        # Local estimates should contain larger numbers
        assert isinstance(local, str)
        assert isinstance(openai, str)
        # Both should be non-empty human-readable strings
        assert len(local) > 0
        assert len(openai) > 0

    def test_openai_small_count(self):
        result = estimate_embedding_time(100, "openai")
        assert "minute" in result.lower()

    def test_local_large_count(self):
        result = estimate_embedding_time(10000, "local")
        assert "minute" in result.lower()


class TestEstimateEmbeddingCost:
    def test_openai_returns_cost_string(self):
        result = estimate_embedding_cost(1000, "openai")

        assert result is not None
        assert "$" in result

    def test_local_returns_none(self):
        result = estimate_embedding_cost(1000, "local")

        assert result is None

    def test_openai_small_count_minimum_cost(self):
        result = estimate_embedding_cost(10, "openai")

        assert result is not None
        assert "$" in result
        assert "0.01" in result

    def test_openai_large_count(self):
        result = estimate_embedding_cost(10000, "openai")

        assert result is not None
        assert "$" in result


class TestRunEmbeddings:
    @patch("linkedout.setup.embeddings.subprocess.run")
    def test_calls_embed_with_provider(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            "Results:\n"
            "  Embedded:   500 profiles\n"
            "  Skipped:    0 (empty text)\n"
        )
        mock_run.return_value.stderr = ""

        run_embeddings("openai")

        call_args = mock_run.call_args[0][0]
        assert "embed" in call_args
        assert "--provider" in call_args
        assert "openai" in call_args

    @patch("linkedout.setup.embeddings.subprocess.run")
    def test_report_includes_embedded_count(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            "Results:\n"
            "  Embedded:   500 profiles\n"
        )
        mock_run.return_value.stderr = ""

        report = run_embeddings("openai")

        assert report.counts.succeeded == 500
        assert report.operation == "setup-embeddings"

    @patch("linkedout.setup.embeddings.subprocess.run")
    def test_raises_on_failure(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "API key invalid"
        mock_run.return_value.stdout = ""

        with pytest.raises(RuntimeError, match="linkedout embed failed"):
            run_embeddings("openai")

    @patch("linkedout.setup.embeddings.subprocess.run")
    def test_local_provider_flag(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        run_embeddings("local")

        call_args = mock_run.call_args[0][0]
        assert "local" in call_args
