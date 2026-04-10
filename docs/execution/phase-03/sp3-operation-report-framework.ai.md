# SP3: Operation Report Framework

**Sub-Phase:** 3 of 7
**Tasks:** 3F (Operation Report Framework)
**Complexity:** M
**Depends on:** SP1 (core logging framework)
**Blocks:** SP5 (CLI + enrichment logging), SP6 (diagnostics + repair)

---

## Objective

Create the `OperationReport` dataclass and supporting types that every CLI command uses to produce structured, persistent operation results. This is the standardized output artifact for all data-modifying operations.

---

## Context

Read `_shared_context.md` for project-level context and the operation result pattern.

**Key decisions:**
- Reports saved to `~/linkedout-data/reports/{operation}-YYYYMMDD-HHMMSS.json`
- `LINKEDOUT_REPORTS_DIR` env var overrides the path
- `print_summary()` follows the exact output pattern from `docs/decision/cli-surface.md`

---

## Tasks

### 1. Create OperationReport Dataclass

**File:** `backend/src/shared/utilities/operation_report.py` (NEW)

```python
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
from typing import Literal
import json

@dataclass
class OperationCounts:
    total: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0

@dataclass
class CoverageGap:
    type: str          # e.g., "missing_company", "missing_embedding"
    count: int
    detail: str        # human-readable description

@dataclass
class OperationFailure:
    item: str          # identifier of the failed item
    reason: str        # why it failed

@dataclass
class OperationReport:
    operation: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    duration_ms: float = 0.0
    counts: OperationCounts = field(default_factory=OperationCounts)
    coverage_gaps: list[CoverageGap] = field(default_factory=list)
    failures: list[OperationFailure] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    
    def save(self, reports_dir: Path | None = None) -> Path:
        """Save to ~/linkedout-data/reports/{operation}-YYYYMMDD-HHMMSS.json
        
        Returns the path where the report was saved.
        """
        ...
    
    def print_summary(self) -> None:
        """Print human-readable summary to stdout following the operation result pattern."""
        ...
    
    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        ...
```

### 2. Implement `save()` Method

- Read `LINKEDOUT_REPORTS_DIR` from environment, default `~/linkedout-data/reports/`
- Ensure directory exists on first write
- Filename: `{operation}-YYYYMMDD-HHMMSS.json` derived from `self.timestamp`
- Write formatted JSON (indent=2)
- Return the `Path` of the saved file

### 3. Implement `print_summary()` Method

Must follow the exact operation result pattern:

```
Results:
  Imported:  3,847 new connections
  Skipped:   23 (already in database)
  Failed:    0

Coverage:
  Companies matched:  3,691 / 3,847 (95.9%)
  Missing companies:  156

Next steps:
  → Run `linkedout compute-affinity` to calculate affinity scores

Report saved: ~/linkedout-data/reports/import-csv-20260407-142305.json
```

Notes:
- Use `click.echo()` or `print()` for output (stdout, not stderr)
- Format numbers with comma separators for readability
- Coverage section only appears if `coverage_gaps` is non-empty
- Next steps section only appears if `next_steps` is non-empty
- Report path line always appears after `save()` is called

### 4. Implement `to_dict()` Method

Recursively convert all dataclass fields to dicts/lists. Use `dataclasses.asdict()` as the base.

### 5. Helper: Get Reports Directory

```python
def _get_reports_dir() -> Path:
    """Get reports directory from env or default."""
    reports_dir = os.environ.get("LINKEDOUT_REPORTS_DIR",
                                  str(Path.home() / "linkedout-data" / "reports"))
    return Path(reports_dir)
```

---

## Files to Create

| File | Description |
|------|-------------|
| `backend/src/shared/utilities/operation_report.py` | OperationReport + supporting dataclasses |
| `tests/unit/shared/test_operation_report.py` | Operation report unit tests |

---

## Verification

### Unit Tests (`tests/unit/shared/test_operation_report.py`)

- Create an `OperationReport` with all fields populated
- `to_dict()` returns a valid dict with all expected keys
- `save()` writes a valid JSON file to the expected path with correct filename format
- `save()` creates the reports directory if it doesn't exist
- `print_summary()` outputs the correct format (capture stdout)
- `print_summary()` omits Coverage section when no gaps
- `print_summary()` omits Next steps when none provided
- Numbers are formatted with commas in `print_summary()`
- Empty report (all zeros) produces sensible output
- Use `tmp_path` and `LINKEDOUT_REPORTS_DIR` env var override for isolation

---

## Acceptance Criteria

- [ ] `OperationReport` can be instantiated, saved as JSON, and printed as human-readable summary
- [ ] JSON output includes all fields: operation, timestamp, duration_ms, counts, coverage_gaps, failures, next_steps
- [ ] `print_summary()` follows the exact output pattern from `docs/decision/cli-surface.md`
- [ ] Reports are saved to `~/linkedout-data/reports/` with timestamp-based filenames
- [ ] Directory auto-created on first write
