# SPDX-License-Identifier: Apache-2.0
"""Embedding progress tracking and resumability.

Persists embedding operation state to a JSON file so that
``linkedout embed`` can be interrupted and resumed without
re-processing completed profiles.

The progress file lives at ``~/linkedout-data/state/embedding_progress.json``
(or ``$LINKEDOUT_DATA_DIR/state/embedding_progress.json`` if overridden).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class EmbeddingProgress:
    """Tracks the state of an embedding operation.

    Serialised to / deserialised from a JSON file so the CLI can
    resume after interruption.  All timestamp fields use ISO-8601
    UTC strings.

    Attributes:
        provider: Embedding provider key (``"openai"`` or ``"local"``).
        model: Model identifier, e.g. ``"text-embedding-3-small"``.
        dimension: Vector dimension produced by the model.
        total_profiles: Total number of profiles to embed.
        completed_profiles: How many profiles have been embedded so far.
        last_processed_id: ID of the last successfully processed profile
            (used as a cursor for resumption).
        started_at: ISO-8601 timestamp of when the operation started.
        updated_at: ISO-8601 timestamp of the last progress update.
        status: One of ``"in_progress"``, ``"completed"``, ``"failed"``.
        failed_ids: Profile IDs that failed to embed.
    """

    provider: str
    model: str
    dimension: int
    total_profiles: int
    completed_profiles: int = 0
    last_processed_id: str | None = None
    started_at: str = ""
    updated_at: str = ""
    status: str = "in_progress"
    failed_ids: list[str] = field(default_factory=list)

    def save(self, path: Path) -> None:
        """Write progress state to a JSON file.

        Creates parent directories if they do not exist.

        Args:
            path: Destination file path.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> EmbeddingProgress | None:
        """Load progress from a JSON file.

        Args:
            path: Source file path.

        Returns:
            An ``EmbeddingProgress`` instance, or ``None`` if the file
            does not exist.
        """
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return cls(**data)

    def mark_batch_complete(self, last_id: str, count: int) -> None:
        """Update state after a batch of profiles is embedded.

        Args:
            last_id: ID of the last profile in the completed batch.
            count: Number of profiles in the completed batch.
        """
        self.completed_profiles += count
        self.last_processed_id = last_id
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_completed(self) -> None:
        """Mark the entire embedding operation as completed."""
        self.status = "completed"
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, error: str) -> None:  # noqa: ARG002
        """Mark the embedding operation as failed.

        Args:
            error: Human-readable description of the failure.  Not stored
                in the progress file — the caller is expected to log it
                separately.  Kept in the signature so callers document
                *why* the operation failed at the call site.
        """
        self.status = "failed"
        self.updated_at = datetime.now(timezone.utc).isoformat()


def get_progress_path() -> Path:
    """Return the path to the embedding progress file.

    Uses ``data_dir`` from ``LinkedOutSettings`` (which respects
    ``LINKEDOUT_DATA_DIR`` and defaults to ``~/linkedout-data``).

    Returns:
        Absolute ``Path`` to ``<data_dir>/state/embedding_progress.json``.
    """
    from shared.config.config import backend_config

    data_dir = os.path.expanduser(backend_config.data_dir)
    return Path(data_dir) / "state" / "embedding_progress.json"
