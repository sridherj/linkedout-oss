# SPDX-License-Identifier: Apache-2.0
"""Local embedding provider using nomic-embed-text-v1.5.

Implements the ``EmbeddingProvider`` ABC for local CPU-based embedding via
sentence-transformers with an ONNX backend.  The model loads lazily on first
``embed()`` call so that importing this module never fails — even when
``sentence-transformers`` is not installed.
"""

from __future__ import annotations

import os

from shared.config import get_config
from shared.utilities.logger import get_logger
from utilities.llm_manager.embedding_provider import EmbeddingProvider

logger = get_logger(__name__, component="cli", operation="embed")

_DEFAULT_MODEL = "nomic-ai/nomic-embed-text-v1.5"
_DIMENSION = 768
_BATCH_SIZE = 32
# Rough throughput on a modern CPU with ONNX quantized model.
_PROFILES_PER_SECOND = 7


class LocalEmbeddingProvider(EmbeddingProvider):
    """EmbeddingProvider backed by nomic-embed-text-v1.5 running locally.

    Uses ``sentence-transformers`` with the ONNX quantized backend for
    CPU inference.  The model is **not** loaded at init time — it is
    downloaded (if needed) and loaded on the first ``embed()`` call.

    Args:
        model: HuggingFace model identifier.  Defaults to
            ``'nomic-ai/nomic-embed-text-v1.5'``.
    """

    def __init__(self, model: str | None = None) -> None:
        self._model_name = model or _DEFAULT_MODEL
        self._model = None  # loaded lazily via _ensure_model_loaded()

    # ── ABC implementations ───────────────────────────────────

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts via local model.

        Processes in batches of 32 (sentence-transformers default).

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors, one per input text, each of length 768.
        """
        if not texts:
            return []
        self._ensure_model_loaded()
        logger.info("Embedding batch", count=len(texts))
        vectors = self._model.encode(  # type: ignore[union-attr]
            texts,
            batch_size=_BATCH_SIZE,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [v.tolist() for v in vectors]

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text string.

        Args:
            text: The text to embed.

        Returns:
            A single embedding vector of length 768.
        """
        return self.embed([text])[0]

    def dimension(self) -> int:
        """Return the vector dimension (768 for nomic-embed-text-v1.5)."""
        return _DIMENSION

    def model_name(self) -> str:
        """Return ``'nomic-embed-text-v1.5'``."""
        return "nomic-embed-text-v1.5"

    def estimate_time(self, count: int) -> str:
        """Return a human-readable time estimate for CPU embedding.

        Heuristic: ~7 profiles/second on a modern CPU with ONNX.

        Args:
            count: Number of texts to embed.

        Returns:
            A string like ``'~10 minutes for 4,000 profiles'``.
        """
        if count <= 0:
            return "< 1 second"
        seconds = count / _PROFILES_PER_SECOND
        minutes = max(1, round(seconds / 60))
        if minutes == 1:
            return f"~1 minute for {count:,} profiles"
        return f"~{minutes} minutes for {count:,} profiles"

    def estimate_cost(self, count: int) -> str | None:
        """Return ``None`` — local inference is free."""
        return None

    # ── Lazy model loading ────────────────────────────────────

    def _ensure_model_loaded(self) -> None:
        """Download (if needed) and load the model on first use."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "Local embedding provider requires 'sentence-transformers' and 'onnxruntime'. "
                "Install with: pip install sentence-transformers onnxruntime"
            )
        settings = get_config()
        cache_dir = os.path.join(settings.data_dir, "models")
        logger.info(
            "Loading local embedding model",
            model=self._model_name,
            cache_dir=cache_dir,
        )
        try:
            self._model = SentenceTransformer(
                self._model_name,
                backend="onnx",
                model_kwargs={"file_name": "onnx/model_quantized.onnx"},
                cache_folder=cache_dir,
                trust_remote_code=True,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load embedding model '{self._model_name}'. "
                f"If this is the first run, ensure you have internet access for the "
                f"~275MB model download.\n\n"
                f"Model cache directory: {cache_dir}\n"
                f"Original error: {exc}"
            ) from exc
        logger.info("Local embedding model loaded", model=self._model_name)
