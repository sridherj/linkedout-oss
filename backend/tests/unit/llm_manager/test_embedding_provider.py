# SPDX-License-Identifier: Apache-2.0
"""Tests for EmbeddingProvider ABC and build_embedding_text()."""

import pytest

from utilities.llm_manager.embedding_provider import EmbeddingProvider, build_embedding_text


class TestEmbeddingProviderABC:
    """Verify the ABC contract."""

    def test_cannot_instantiate_directly(self):
        """EmbeddingProvider is abstract and cannot be instantiated."""
        with pytest.raises(TypeError, match="abstract method"):
            EmbeddingProvider()

    def test_concrete_subclass_instantiates(self):
        """A minimal concrete subclass that implements all 6 methods works."""

        class StubProvider(EmbeddingProvider):
            def embed(self, texts: list[str]) -> list[list[float]]:
                return [[0.0] * 3 for _ in texts]

            def embed_single(self, text: str) -> list[float]:
                return [0.0] * 3

            def dimension(self) -> int:
                return 3

            def model_name(self) -> str:
                return "stub-v1"

            def estimate_time(self, count: int) -> str:
                return "< 1 second"

            def estimate_cost(self, count: int) -> str | None:
                return None

        provider = StubProvider()
        assert provider.dimension() == 3
        assert provider.model_name() == "stub-v1"
        assert provider.embed_single("hello") == [0.0, 0.0, 0.0]
        assert provider.embed(["a", "b"]) == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        assert provider.estimate_time(100) == "< 1 second"
        assert provider.estimate_cost(100) is None

    def test_partial_implementation_raises(self):
        """Subclass missing methods cannot be instantiated."""

        class PartialProvider(EmbeddingProvider):
            def embed(self, texts: list[str]) -> list[list[float]]:
                return []

            def embed_single(self, text: str) -> list[float]:
                return []

        with pytest.raises(TypeError):
            PartialProvider()


class TestBuildEmbeddingText:
    """Verify build_embedding_text() produces expected output."""

    def test_name_and_headline(self):
        profile = {"full_name": "Test User", "headline": "Engineer"}
        assert build_embedding_text(profile) == "Test User | Engineer"

    def test_full_profile(self):
        profile = {
            "full_name": "Jane Doe",
            "headline": "Senior Engineer",
            "about": "Builds things",
            "experiences": [
                {"company_name": "Acme", "title": "SWE"},
                {"company_name": "Globex", "title": "Lead"},
            ],
        }
        result = build_embedding_text(profile)
        assert result == (
            "Jane Doe | Senior Engineer | Builds things | "
            "Experience: Acme - SWE, Globex - Lead"
        )

    def test_empty_profile(self):
        assert build_embedding_text({}) == ""

    def test_name_only(self):
        assert build_embedding_text({"full_name": "Solo"}) == "Solo"

    def test_experience_company_only(self):
        profile = {"experiences": [{"company_name": "Acme"}]}
        assert build_embedding_text(profile) == "Experience: Acme"

    def test_experience_title_only(self):
        profile = {"experiences": [{"title": "Engineer"}]}
        assert build_embedding_text(profile) == "Experience: Engineer"

    def test_empty_experiences_list(self):
        profile = {"full_name": "Test", "experiences": []}
        assert build_embedding_text(profile) == "Test"

    def test_experience_with_empty_strings(self):
        """Experiences with empty company_name and title are skipped."""
        profile = {
            "full_name": "Test",
            "experiences": [{"company_name": "", "title": ""}],
        }
        assert build_embedding_text(profile) == "Test"
