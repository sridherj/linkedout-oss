# SPDX-License-Identifier: Apache-2.0
"""Embedding client wrapping OpenAI embeddings API."""
import json
import time
from pathlib import Path
from typing import Optional

from openai import OpenAI

from shared.config import get_config
from shared.utilities.logger import get_logger
from utilities.llm_manager.embedding_provider import build_embedding_text as _build_embedding_text

logger = get_logger(__name__, component="backend")


class EmbeddingClient:
    """Client for generating text embeddings via OpenAI API.

    Supports real-time single/batch embedding and OpenAI Batch API for large-scale processing.
    """

    def __init__(self, model: Optional[str] = None, dimensions: Optional[int] = None, api_key: Optional[str] = None):
        cfg = get_config()
        self._model = model or cfg.embedding.model
        self._dimensions = dimensions if dimensions is not None else cfg.embedding.dimensions
        resolved_key = api_key or cfg.openai_api_key
        self._client = OpenAI(api_key=resolved_key) if resolved_key else OpenAI()

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string. Returns a vector of floats."""
        if not text or not text.strip():
            raise ValueError('Cannot embed empty text')

        response = self._client.embeddings.create(
            input=text,
            model=self._model,
            dimensions=self._dimensions,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single API call (up to ~2K texts).

        Filters out empty texts and maps results back to original positions.
        Empty texts get zero vectors.
        """
        if not texts:
            return []

        # Track which indices have non-empty texts
        valid_indices = []
        valid_texts = []
        for i, t in enumerate(texts):
            if t and t.strip():
                valid_indices.append(i)
                valid_texts.append(t)

        if not valid_texts:
            return [[0.0] * self._dimensions for _ in texts]

        response = self._client.embeddings.create(
            input=valid_texts,
            model=self._model,
            dimensions=self._dimensions,
        )

        # Map results back, filling empties with zero vectors
        results: list[list[float]] = [[0.0] * self._dimensions for _ in texts]
        for resp_item, orig_idx in zip(response.data, valid_indices):
            results[orig_idx] = resp_item.embedding

        return results

    def create_batch_file(self, items: list[dict], output_path: str) -> str:
        """Generate a JSONL file for OpenAI Batch API.

        Each item should have 'custom_id' and 'text' keys.
        Returns the output file path.
        """
        path = Path(output_path)
        with path.open('w') as f:
            for item in items:
                if not item.get('text', '').strip():
                    continue
                request = {
                    'custom_id': item['custom_id'],
                    'method': 'POST',
                    'url': '/v1/embeddings',
                    'body': {
                        'model': self._model,
                        'input': item['text'],
                        'dimensions': self._dimensions,
                    },
                }
                f.write(json.dumps(request) + '\n')
        return str(path)

    def submit_batch(self, file_path: str) -> str:
        """Upload a JSONL file and create an OpenAI batch job. Returns batch_id."""
        with open(file_path, 'rb') as f:
            uploaded = self._client.files.create(file=f, purpose='batch')

        batch = self._client.batches.create(
            input_file_id=uploaded.id,
            endpoint='/v1/embeddings',
            completion_window='24h',
        )
        logger.info(f'Batch submitted: {batch.id}')
        return batch.id

    def poll_batch(self, batch_id: str, poll_interval: Optional[int] = None, timeout: Optional[int] = None, progress_callback=None) -> dict:
        """Poll a batch job until completion. Returns parsed results keyed by custom_id."""
        cfg = get_config()
        if poll_interval is None:
            poll_interval = cfg.embedding.batch_poll_interval_seconds
        if timeout is None:
            timeout = cfg.embedding.batch_timeout_seconds
        elapsed = 0
        while elapsed < timeout:
            batch = self._client.batches.retrieve(batch_id)
            counts = batch.request_counts
            completed = counts.completed if counts else 0
            total = counts.total if counts else 0
            failed = counts.failed if counts else 0
            msg = f'[{batch.status}] {completed}/{total} completed, {failed} failed'
            logger.info(f'Batch {batch_id}: {msg}')
            if progress_callback:
                progress_callback(msg)
            if batch.status == 'completed':
                if not batch.output_file_id:
                    raise RuntimeError(f'Batch {batch_id} completed but has no output file')
                return self._download_batch_results(batch.output_file_id)
            if batch.status in ('failed', 'cancelled', 'expired'):
                raise RuntimeError(f'Batch {batch_id} ended with status: {batch.status}')
            time.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f'Batch {batch_id} did not complete within {timeout}s')

    def cancel_and_get_results(self, batch_id: str, poll_interval: int = 5) -> dict:
        """Cancel an in-progress batch and download whatever completed results exist."""
        batch = self._client.batches.retrieve(batch_id)
        if batch.status not in ('in_progress', 'validating', 'finalizing'):
            raise RuntimeError(f'Batch {batch_id} is in status {batch.status!r}, cannot cancel')

        logger.info(f'Cancelling batch {batch_id}...')
        self._client.batches.cancel(batch_id)

        # Poll until cancelled (output_file_id becomes available)
        while True:
            batch = self._client.batches.retrieve(batch_id)
            counts = batch.request_counts
            completed = counts.completed if counts else '?'
            total = counts.total if counts else '?'
            logger.info(f'Batch {batch_id}: [{batch.status}] {completed}/{total} completed')
            if batch.status == 'cancelled':
                break
            if batch.status in ('failed', 'expired'):
                raise RuntimeError(f'Batch {batch_id} ended unexpectedly with status: {batch.status}')
            time.sleep(poll_interval)

        if not batch.output_file_id:
            return {}
        return self._download_batch_results(batch.output_file_id)

    def _download_batch_results(self, output_file_id: str) -> dict:
        """Download and parse batch results. Returns dict keyed by custom_id."""
        content = self._client.files.content(output_file_id)
        results = {}
        for line in content.text.strip().split('\n'):
            if not line.strip():
                continue
            record = json.loads(line)
            custom_id = record['custom_id']
            embedding = record['response']['body']['data'][0]['embedding']
            results[custom_id] = embedding
        return results

    @staticmethod
    def build_embedding_text(profile: dict) -> str:
        """Construct embedding input text from a profile dict.

        Delegates to the standalone ``build_embedding_text()`` in
        ``embedding_provider`` module.
        """
        return _build_embedding_text(profile)
