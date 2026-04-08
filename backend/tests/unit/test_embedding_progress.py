# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the embedding progress tracking module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from utilities.embedding_progress import EmbeddingProgress, get_progress_path


def _make_progress(**overrides) -> EmbeddingProgress:
    """Create an EmbeddingProgress with sensible defaults."""
    defaults = {
        "provider": "local",
        "model": "nomic-embed-text-v1.5",
        "dimension": 768,
        "total_profiles": 100,
        "completed_profiles": 0,
        "started_at": "2026-04-07T14:00:00+00:00",
        "updated_at": "2026-04-07T14:00:00+00:00",
        "status": "in_progress",
    }
    defaults.update(overrides)
    return EmbeddingProgress(**defaults)


class TestSaveAndLoad:
    """Save progress to a file, load it back, verify all fields match."""

    def test_round_trip(self, tmp_path: Path):
        # Arrange
        progress_file = tmp_path / "state" / "embedding_progress.json"
        original = _make_progress(
            completed_profiles=50,
            last_processed_id="cp_abc123",
            failed_ids=["cp_err1", "cp_err2"],
        )

        # Act
        original.save(progress_file)
        loaded = EmbeddingProgress.load(progress_file)

        # Assert
        assert loaded is not None
        assert loaded.provider == original.provider
        assert loaded.model == original.model
        assert loaded.dimension == original.dimension
        assert loaded.total_profiles == original.total_profiles
        assert loaded.completed_profiles == original.completed_profiles
        assert loaded.last_processed_id == original.last_processed_id
        assert loaded.started_at == original.started_at
        assert loaded.updated_at == original.updated_at
        assert loaded.status == original.status
        assert loaded.failed_ids == original.failed_ids


class TestLoadMissingFile:
    """Loading from a non-existent path returns None."""

    def test_returns_none(self, tmp_path: Path):
        # Arrange
        missing_file = tmp_path / "does_not_exist.json"

        # Act
        result = EmbeddingProgress.load(missing_file)

        # Assert
        assert result is None


class TestMarkBatchComplete:
    """mark_batch_complete updates count, cursor, and timestamp."""

    def test_updates_fields(self):
        # Arrange
        progress = _make_progress(completed_profiles=10, last_processed_id="cp_010")
        before = datetime.now(timezone.utc)

        # Act
        progress.mark_batch_complete(last_id="cp_042", count=32)

        # Assert
        assert progress.completed_profiles == 42
        assert progress.last_processed_id == "cp_042"
        updated = datetime.fromisoformat(progress.updated_at)
        assert updated >= before

    def test_accumulates_across_batches(self):
        # Arrange
        progress = _make_progress()

        # Act
        progress.mark_batch_complete(last_id="cp_032", count=32)
        progress.mark_batch_complete(last_id="cp_064", count=32)

        # Assert
        assert progress.completed_profiles == 64
        assert progress.last_processed_id == "cp_064"


class TestMarkCompleted:
    """mark_completed sets status to 'completed' and updates timestamp."""

    def test_sets_completed(self):
        # Arrange
        progress = _make_progress()
        before = datetime.now(timezone.utc)

        # Act
        progress.mark_completed()

        # Assert
        assert progress.status == "completed"
        updated = datetime.fromisoformat(progress.updated_at)
        assert updated >= before


class TestMarkFailed:
    """mark_failed sets status to 'failed' and updates timestamp."""

    def test_sets_failed(self):
        # Arrange
        progress = _make_progress()
        before = datetime.now(timezone.utc)

        # Act
        progress.mark_failed("connection timed out")

        # Assert
        assert progress.status == "failed"
        updated = datetime.fromisoformat(progress.updated_at)
        assert updated >= before


class TestResumeLogic:
    """Verify that in-progress state carries the resume cursor."""

    def test_resume_from_last_processed_id(self, tmp_path: Path):
        # Arrange — simulate a partially-complete run
        progress = _make_progress(
            completed_profiles=500,
            last_processed_id="cp_500",
            total_profiles=1000,
        )
        progress_file = tmp_path / "embedding_progress.json"
        progress.save(progress_file)

        # Act — reload (as the CLI would on restart)
        resumed = EmbeddingProgress.load(progress_file)

        # Assert — the caller would use last_processed_id as resume cursor
        assert resumed is not None
        assert resumed.status == "in_progress"
        assert resumed.last_processed_id == "cp_500"
        assert resumed.completed_profiles == 500

    def test_failed_status_also_resumes(self, tmp_path: Path):
        # Arrange — a run that failed partway through
        progress = _make_progress(
            completed_profiles=300,
            last_processed_id="cp_300",
            status="failed",
        )
        progress_file = tmp_path / "embedding_progress.json"
        progress.save(progress_file)

        # Act
        resumed = EmbeddingProgress.load(progress_file)

        # Assert — failed runs resume from last_processed_id too
        assert resumed is not None
        assert resumed.status == "failed"
        assert resumed.last_processed_id == "cp_300"


class TestForceRestart:
    """Force mode deletes the progress file so the operation starts fresh."""

    def test_delete_completed_file(self, tmp_path: Path):
        # Arrange — a previously completed run
        progress = _make_progress(status="completed", completed_profiles=100)
        progress_file = tmp_path / "embedding_progress.json"
        progress.save(progress_file)
        assert progress_file.exists()

        # Act — simulate --force: delete the file
        progress_file.unlink()

        # Assert — load returns None, so CLI starts fresh
        assert EmbeddingProgress.load(progress_file) is None


class TestIdempotent:
    """Loading, saving, and loading again produces identical state."""

    def test_load_save_load(self, tmp_path: Path):
        # Arrange
        progress_file = tmp_path / "embedding_progress.json"
        original = _make_progress(
            completed_profiles=42,
            last_processed_id="cp_042",
            failed_ids=["cp_bad"],
        )
        original.save(progress_file)

        # Act — load → save → load
        first_load = EmbeddingProgress.load(progress_file)
        assert first_load is not None
        first_load.save(progress_file)
        second_load = EmbeddingProgress.load(progress_file)

        # Assert — both loads produce identical data
        assert second_load is not None
        assert first_load.provider == second_load.provider
        assert first_load.model == second_load.model
        assert first_load.dimension == second_load.dimension
        assert first_load.total_profiles == second_load.total_profiles
        assert first_load.completed_profiles == second_load.completed_profiles
        assert first_load.last_processed_id == second_load.last_processed_id
        assert first_load.started_at == second_load.started_at
        assert first_load.updated_at == second_load.updated_at
        assert first_load.status == second_load.status
        assert first_load.failed_ids == second_load.failed_ids


class TestDirectoryCreation:
    """Saving to a path whose parent doesn't exist creates the parent."""

    def test_creates_parent_dirs(self, tmp_path: Path):
        # Arrange
        deep_path = tmp_path / "a" / "b" / "c" / "progress.json"
        progress = _make_progress()

        # Act
        progress.save(deep_path)

        # Assert
        assert deep_path.exists()
        loaded = EmbeddingProgress.load(deep_path)
        assert loaded is not None
        assert loaded.provider == progress.provider


class TestGetProgressPath:
    """get_progress_path returns the expected path under data_dir."""

    def test_uses_data_dir(self, monkeypatch):
        # Arrange — override data_dir via env
        monkeypatch.setenv("LINKEDOUT_DATA_DIR", "/tmp/test-linkedout")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        # Reset the settings singleton so it picks up the new env
        import shared.config.settings as settings_mod

        monkeypatch.setattr(settings_mod, "_settings_instance", None)
        import shared.config.config as config_mod

        monkeypatch.setattr(config_mod, "backend_config", settings_mod.get_config())

        # Act
        result = get_progress_path()

        # Assert
        assert result == Path("/tmp/test-linkedout/state/embedding_progress.json")
