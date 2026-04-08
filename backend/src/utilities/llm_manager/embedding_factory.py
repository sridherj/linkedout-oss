# SPDX-License-Identifier: Apache-2.0
"""Embedding provider factory.

Returns the configured ``EmbeddingProvider`` instance based on application
config or explicit overrides.  Also provides ``get_embedding_column_name()``
to map a provider to the correct ``crawled_profile`` column.
"""

from __future__ import annotations

from utilities.llm_manager.embedding_provider import EmbeddingProvider


def get_embedding_provider(
    provider: str | None = None,
    model: str | None = None,
) -> EmbeddingProvider:
    """Return a configured ``EmbeddingProvider`` instance.

    Args:
        provider: ``'openai'`` or ``'local'``.  Defaults to the value of
            ``LINKEDOUT_EMBEDDING_PROVIDER`` from config.
        model: Override model name.  Defaults to the provider's default.
    """
    if provider is None:
        from shared.config import get_config

        cfg = get_config()
        provider = cfg.embedding.provider
        if model is None:
            model_from_config = cfg.embedding.model
            if model_from_config:
                model = model_from_config

    if provider == "openai":
        from utilities.llm_manager.openai_embedding_provider import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider(model=model)
    elif provider == "local":
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        return LocalEmbeddingProvider(model=model)
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider!r}. "
            f"Use 'openai' or 'local'. "
            f"Set LINKEDOUT_EMBEDDING_PROVIDER in config.yaml or environment."
        )


def get_embedding_column_name(provider: EmbeddingProvider) -> str:
    """Return the ``crawled_profile`` column name for the given provider.

    Maps provider model names to the appropriate dual-column:
    - Models containing ``'nomic'`` -> ``'embedding_nomic'``
    - Everything else             -> ``'embedding_openai'``
    """
    if "nomic" in provider.model_name().lower():
        return "embedding_nomic"
    return "embedding_openai"
