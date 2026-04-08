# SPDX-License-Identifier: Apache-2.0
"""OpenAI embedding provider wrapping the existing EmbeddingClient.

Implements the ``EmbeddingProvider`` ABC for OpenAI's text-embedding models.
The real logic stays in ``EmbeddingClient`` — this is a thin adapter that
conforms to the provider interface and exposes Batch API methods as
provider-specific extras.
"""

from __future__ import annotations

from shared.config import get_config
from shared.utilities.logger import get_logger
from utilities.llm_manager.embedding_client import EmbeddingClient
from utilities.llm_manager.embedding_provider import EmbeddingProvider

logger = get_logger(__name__, component="cli", operation="embed")

# Pricing: OpenAI text-embedding-3-small ~$0.02 per 1M tokens.
# Average profile ≈ 500 tokens.
_COST_PER_MILLION_TOKENS = 0.02
_AVG_TOKENS_PER_PROFILE = 500


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """EmbeddingProvider backed by OpenAI's embedding API.

    Wraps ``EmbeddingClient`` for real-time embedding (single and batch).
    Batch API methods (``embed_batch_async``, ``cancel_batch``) are
    provider-specific and live only on this concrete class.

    Args:
        model: OpenAI model name. Defaults to config value or
            ``'text-embedding-3-small'``.
        dimensions: Vector dimensions. Defaults to config value or ``1536``.
    """

    def __init__(
        self,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        cfg = get_config()

        resolved_key = cfg.openai_api_key
        if not resolved_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured.\n\n"
                "Set it in one of:\n"
                "  1. ~/linkedout-data/config/secrets.yaml  →  openai_api_key: sk-...\n"
                "  2. Environment variable                  →  export OPENAI_API_KEY=sk-...\n"
                "  3. .env file                             →  OPENAI_API_KEY=sk-..."
            )

        self._model = model or cfg.embedding.model
        self._dimensions = (
            dimensions if dimensions is not None else cfg.embedding.dimensions
        )
        self._client = EmbeddingClient(
            model=self._model,
            dimensions=self._dimensions,
            api_key=resolved_key,
        )
        logger.info(
            "OpenAI embedding provider initialized",
            model=self._model,
            dimensions=self._dimensions,
        )

    # ── ABC implementations ───────────────────────────────────

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts via real-time API.

        Delegates to ``EmbeddingClient.embed_batch()`` which handles
        chunking and empty-text filtering internally.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        return self._client.embed_batch(texts)

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text string via real-time API.

        Args:
            text: The text to embed.

        Returns:
            A single embedding vector of length ``self.dimension()``.
        """
        return self._client.embed_text(text)

    def dimension(self) -> int:
        """Return the configured vector dimension (default 1536)."""
        return self._dimensions

    def model_name(self) -> str:
        """Return the configured model name (default ``'text-embedding-3-small'``)."""
        return self._model

    def estimate_time(self, count: int) -> str:
        """Return a human-readable time estimate for real-time embedding.

        Heuristic: ~100 texts per minute via real-time API.

        Args:
            count: Number of texts to embed.

        Returns:
            A string like ``'~40 minutes'``.
        """
        if count <= 0:
            return "< 1 second"
        minutes = max(1, count // 100)
        if minutes == 1:
            return "~1 minute"
        return f"~{minutes} minutes"

    def estimate_cost(self, count: int) -> str | None:
        """Return a human-readable cost estimate based on OpenAI pricing.

        Assumes ~500 tokens per profile at ~$0.02/1M tokens.

        Args:
            count: Number of texts to embed.

        Returns:
            A string like ``'~$0.04 for 4000 profiles'``.
        """
        if count <= 0:
            return None
        total_tokens = count * _AVG_TOKENS_PER_PROFILE
        cost = (total_tokens / 1_000_000) * _COST_PER_MILLION_TOKENS
        return f"~${cost:.2f} for {count} profiles"

    # ── Provider-specific: Batch API ──────────────────────────

    def embed_batch_async(
        self,
        items: list[dict],
        output_path: str,
        poll_interval: int | None = None,
        timeout: int | None = None,
        progress_callback=None,
    ) -> dict:
        """Run embedding via OpenAI Batch API (async, cheaper).

        Creates a JSONL batch file, submits it, and polls until completion.

        1. Generates a JSONL file at ``output_path`` from ``items``.
        2. Submits the file as an OpenAI batch job.
        3. Polls until completion or timeout.

        Args:
            items: List of dicts with ``'custom_id'`` and ``'text'`` keys.
            output_path: Path for the intermediate JSONL file.
            poll_interval: Seconds between status checks. Defaults to config.
            timeout: Max seconds to wait. Defaults to config.
            progress_callback: Optional callable receiving status strings.

        Returns:
            Dict mapping ``custom_id`` → embedding vector.
        """
        batch_file = self._client.create_batch_file(items, output_path)
        batch_id = self._client.submit_batch(batch_file)
        logger.info("Batch submitted", batch_id=batch_id, item_count=len(items))
        return self._client.poll_batch(
            batch_id,
            poll_interval=poll_interval,
            timeout=timeout,
            progress_callback=progress_callback,
        )

    def cancel_batch(self, batch_id: str, poll_interval: int = 5) -> dict:
        """Cancel an in-progress batch and retrieve partial results.

        Args:
            batch_id: The OpenAI batch job ID to cancel.
            poll_interval: Seconds between cancel-status checks.

        Returns:
            Dict mapping ``custom_id`` → embedding vector for completed items.
        """
        logger.info("Cancelling batch", batch_id=batch_id)
        return self._client.cancel_and_get_results(
            batch_id, poll_interval=poll_interval
        )
