# SPDX-License-Identifier: Apache-2.0
"""Embedding provider abstraction.

Defines the ``EmbeddingProvider`` ABC that all embedding backends implement,
and the shared ``build_embedding_text()`` utility used to construct embedding
input from profile data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    Every concrete provider (OpenAI, local nomic, etc.) must implement all six
    methods below.  The interface is intentionally minimal — callers need only
    ``embed`` / ``embed_single`` for vectors and the remaining helpers for
    human-readable diagnostics.
    """

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts.

        Args:
            texts: Non-empty list of strings to embed.

        Returns:
            A list of embedding vectors, one per input text, each of length
            ``self.dimension()``.
        """
        ...

    @abstractmethod
    def embed_single(self, text: str) -> list[float]:
        """Embed a single text string.

        Args:
            text: The text to embed.

        Returns:
            A single embedding vector of length ``self.dimension()``.
        """
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimension for this provider/model."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return a human-readable model identifier (e.g. ``'text-embedding-3-small'``)."""
        ...

    @abstractmethod
    def estimate_time(self, count: int) -> str:
        """Return a human-readable time estimate for embedding *count* texts.

        Args:
            count: Number of texts to embed.

        Returns:
            A string like ``'~2 minutes'`` or ``'< 1 second'``.
        """
        ...

    @abstractmethod
    def estimate_cost(self, count: int) -> str | None:
        """Return a human-readable cost estimate, or ``None`` if free.

        Args:
            count: Number of texts to embed.

        Returns:
            A string like ``'~$0.02'``, or ``None`` for free/local providers.
        """
        ...


def build_embedding_text(profile: dict) -> str:
    """Construct embedding input text from a profile dictionary.

    Format::

        {full_name} | {headline} | {about} | Experience: {company} - {title}, ...

    This is a shared utility used by all embedding providers.

    Args:
        profile: Dictionary with optional keys ``full_name``, ``headline``,
            ``about``, and ``experiences`` (list of dicts with ``company_name``
            and ``title``).

    Returns:
        A pipe-separated string suitable for embedding.
    """
    parts: list[str] = []

    if profile.get('full_name'):
        parts.append(profile['full_name'])
    if profile.get('headline'):
        parts.append(profile['headline'])
    if profile.get('about'):
        parts.append(profile['about'])

    experiences = profile.get('experiences', [])
    if experiences:
        exp_strs: list[str] = []
        for exp in experiences:
            company = exp.get('company_name', '')
            title = exp.get('title', '')
            if company and title:
                exp_strs.append(f'{company} - {title}')
            elif company:
                exp_strs.append(company)
            elif title:
                exp_strs.append(title)
        if exp_strs:
            parts.append('Experience: ' + ', '.join(exp_strs))

    return ' | '.join(parts)
