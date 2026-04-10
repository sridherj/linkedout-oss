# Sub-Phase 2d: Embedding Progress Tracking & Resumability

**Phase:** 5 — Embedding Provider Abstraction
**Plan task:** 5G (Progress Tracking)
**Dependencies:** None (independent utility module)
**Blocks:** sp4
**Can run in parallel with:** sp2a, sp2b, sp2c

## Objective
Create a progress tracking module that persists embedding state to `~/linkedout-data/state/embedding_progress.json`. This enables the `linkedout embed` command to be interrupted and resumed without re-processing completed profiles.

## Context
- Read shared context: `docs/execution/phase-05/_shared_context.md`
- Read plan (5G section): `docs/plan/phase-05-embedding-abstraction.md`
- Read data directory decision: `docs/decision/2026-04-07-data-directory-convention.md`
- Read config: `backend/src/shared/config/config.py` (for `data_dir` path)

## Deliverables

### 1. `backend/src/utilities/embedding_progress.py` (NEW)

Progress tracking module with these responsibilities:

```python
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
import json

@dataclass
class EmbeddingProgress:
    provider: str                          # "openai" or "local"
    model: str                             # "text-embedding-3-small" or "nomic-embed-text-v1.5"
    dimension: int                         # 1536 or 768
    total_profiles: int                    # total profiles to embed
    completed_profiles: int = 0            # how many done so far
    last_processed_id: str | None = None   # ID of last processed profile (for resume)
    started_at: str = ""                   # ISO timestamp
    updated_at: str = ""                   # ISO timestamp
    status: str = "in_progress"            # "in_progress", "completed", "failed"
    failed_ids: list[str] = field(default_factory=list)  # IDs that failed embedding

    def save(self, path: Path) -> None:
        """Write progress state to JSON file. Creates parent dirs if needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "EmbeddingProgress | None":
        """Load progress from file. Returns None if file doesn't exist."""
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return cls(**data)

    def mark_batch_complete(self, last_id: str, count: int) -> None:
        """Update after a batch of profiles is embedded."""
        self.completed_profiles += count
        self.last_processed_id = last_id
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_completed(self) -> None:
        """Mark the entire operation as completed."""
        self.status = "completed"
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, error: str) -> None:
        """Mark the operation as failed."""
        self.status = "failed"
        self.updated_at = datetime.now(timezone.utc).isoformat()


def get_progress_path() -> Path:
    """Return the path to the embedding progress file."""
    from shared.config.config import backend_config
    data_dir = os.path.expanduser(
        getattr(backend_config, 'LINKEDOUT_DATA_DIR', '~/linkedout-data')
    )
    return Path(data_dir) / "state" / "embedding_progress.json"
```

**Behavior rules:**
- Progress file written after each batch (every 32 profiles for local, every 500 for OpenAI)
- On startup, `linkedout embed` checks for existing progress file:
  - `status=in_progress` → resume from `last_processed_id`
  - `status=completed` → skip (already done, unless `--force`)
  - `status=failed` → resume from `last_processed_id` (retry from where it failed)
  - File not found → start fresh
- `--force` flag deletes the progress file and starts fresh
- The file is a simple JSON — no locking needed (single-user, single-process)
- On completion, set `status=completed`

### 2. Unit Tests: `backend/tests/unit/test_embedding_progress.py` (NEW)

Test cases:
- **Save and load:** Create progress, save to temp file, load it back — all fields match
- **Load missing file:** Returns `None`
- **mark_batch_complete:** Updates `completed_profiles`, `last_processed_id`, `updated_at`
- **mark_completed:** Sets `status` to `"completed"`
- **mark_failed:** Sets `status` to `"failed"`
- **Resume logic:** Given progress with `status=in_progress` and `last_processed_id="cp_500"`, verify a resume query would use `WHERE id > 'cp_500'` (test the logic, not the SQL)
- **Force restart:** Given progress with `status=completed`, verify that force mode would delete the file
- **Idempotent:** Loading → saving → loading produces identical state
- **Directory creation:** Saving to a path whose parent doesn't exist creates the parent

## Verification
1. `cd backend && uv run python -c "from utilities.embedding_progress import EmbeddingProgress, get_progress_path; print(get_progress_path())"` prints a valid path
2. `cd backend && uv run pytest tests/unit/test_embedding_progress.py -v` passes
3. `cd backend && uv run pytest tests/unit/ -x --timeout=60` — all unit tests pass

## Notes
- This module is a pure utility — no database dependencies, no external API calls. It only reads/writes a JSON file.
- The `last_processed_id` field assumes profiles are processed in ID order (`ORDER BY id`). This matches the current `generate_embeddings.py` behavior.
- The progress file lives at `~/linkedout-data/state/embedding_progress.json`, consistent with the data directory convention.
- The `failed_ids` list is a simple record of which profile IDs failed. The CLI command (sp4) will decide whether to retry or report them.
