# SP-F: Burnish Mode (Self-Healing Loop)

**Phase:** Integration Test for Installation
**Plan tasks:** F1 (error detection), F2 (self-healing loop), F3 (decision log)
**Dependencies:** SP-D (parent harness triggers burnish loop on error)
**Blocks:** —
**Can run in parallel with:** SP-E (evaluation)

## Objective

Implement the self-healing loop for burnish mode. When the parent harness detects an error during any test phase, it enters the burnish loop: analyze root cause, apply a fix in the local codebase (visible instantly via volume mount), log the decision, and re-run from the failed point. Bounded by strict limits to prevent infinite loops.

## Context

- Read shared context: `docs/execution/integration-test/_shared_context.md`
- Read plan (Sub-phase F section): `docs/plan/integration-test-installation.md`
- Read requirements (Scenario 7 — self-healing): `.taskos/integration_test_refined_requirements.collab.md`
- Read log reader: `backend/src/dev_tools/log_reader.py` (created in SP-B — provides error detection)
- Read parent harness: `backend/src/dev_tools/integration_test.py` (created in SP-D — calls burnish loop)

## Deliverables

### F1. Error detection integration

The error detection patterns are implemented in the log reader (SP-B's `SessionLogReader.detect_errors()`). SP-F adds the decision layer: what to do when an error is detected.

**Error classification and action table:**

| Pattern | Type | Action |
|---------|------|--------|
| `Traceback (most recent call last):` | `python_traceback` | Enter burnish loop |
| `[sudo] password for` | `unexpected_sudo` | Enter burnish loop |
| `Error:` / `error:` in CLI output | `cli_error` | Enter burnish loop |
| No output change for >120 seconds (setup) or >60s (queries) | `stall` | Enter burnish loop |
| `FAILED` in readiness report | `setup_failure` | Enter burnish loop |
| Docker daemon/build/network errors | `infrastructure` | **STOP and flag to SJ** |

The error classification is integrated into the parent harness (SP-D). After every `send_to_claude()` call, the harness checks `log_reader.detect_errors()` and `tmux_harness.capture_pane()` for error patterns.

### F2. Self-healing loop (bounded)

Add burnish loop logic to `backend/src/dev_tools/integration_test.py` (or as a separate module imported by it):

```python
@dataclass
class BurnishLimits:
    max_per_error: int = 5
    max_total: int = 15
    allowed_paths: tuple[str, ...] = ("backend/src/", "skills/", "scripts/", "tests/")
    prohibited_paths: tuple[str, ...] = ("migrations/", ".github/", "docs/specs/")

@dataclass
class BurnishState:
    total_attempts: int = 0
    error_attempts: dict[str, int] = field(default_factory=dict)  # error_hash -> count
    decisions: list[dict] = field(default_factory=list)


def burnish_loop(error_context: dict, harness: TmuxHarness, state: BurnishState) -> bool:
    """Attempt to fix an error and re-run. Returns True if fixed.

    Steps:
    1. Check limits (per-error and total). If exceeded, escalate to SJ.
    2. Create git commit checkpoint for rollback.
    3. Capture error context: session log snippet, pane output, failed step.
    4. Analyze root cause in LinkedOut OSS codebase.
    5. Check file scope — if root cause is in prohibited path, escalate to SJ.
    6. If multiple valid fix approaches exist (ambiguous), stop and ask SJ.
    7. Apply fix in local repo (appears instantly via volume mount).
    8. Record decision in JSONL log.
    9. Re-run from failed point (or from scratch if state is contaminated).
    """
```

**Limit enforcement:**
- **5 attempts per error:** Hash the error signature (type + key details). If `error_attempts[hash] >= 5`, escalate.
- **15 total attempts:** If `total_attempts >= 15`, hard stop — no exceptions.
- **File scope check:** Before applying any fix, verify that all files to be modified are under `allowed_paths` and not under `prohibited_paths`. If a file is out of scope, escalate to SJ.

**Git checkpoint:**
```python
def create_checkpoint(description: str) -> str:
    """Create a git commit checkpoint before applying a fix.
    Returns the commit hash for potential rollback."""
    # git add -A && git commit -m "checkpoint: {description}"
```

**Error hashing:**
```python
def hash_error(error_context: dict) -> str:
    """Create a stable hash for an error to track per-error attempt counts.
    Uses error type + first line of traceback (or error message)."""
```

**Ambiguity gate:**
- If the parent Claude identifies multiple valid fix approaches, it MUST stop and ask SJ for direction. This is a design constraint, not something that can be automated — the parent Claude uses judgment.

### F3. Decision log

**File:** `/tmp/linkedout-oss/burnish-decisions-YYYYMMDD-HHMMSS.jsonl`

One JSONL entry per fix decision. Each entry is a complete record:

```json
{
  "timestamp": "2026-04-10T12:34:56Z",
  "phase": "I",
  "step": "setup step 3 -- database creation",
  "error_description": "pg_trgm extension not found",
  "root_cause": "system-setup.sh doesn't install postgresql-XX-contrib",
  "fix_applied": "Added postgresql-17-contrib to apt install list",
  "files_modified": ["scripts/system-setup.sh"],
  "rationale": "pg_trgm is required for fuzzy search; contrib package provides it",
  "attempt_number": 1,
  "git_checkpoint": "abc1234"
}
```

```python
class DecisionLog:
    """Append-only JSONL decision log for burnish mode fixes."""

    def __init__(self):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = Path(f"/tmp/linkedout-oss/burnish-decisions-{timestamp}.jsonl")

    def record(self, decision: dict) -> None:
        """Append one decision entry to the JSONL file."""
        with open(self.path, "a") as f:
            f.write(json.dumps(decision) + "\n")

    def read_all(self) -> list[dict]:
        """Read all decision entries."""
```

**Required fields per entry:**
- `timestamp` (ISO 8601)
- `phase` ("I", "II", "III")
- `step` (human-readable step description)
- `error_description` (what went wrong)
- `root_cause` (why it went wrong)
- `fix_applied` (what was changed)
- `files_modified` (list of file paths)
- `rationale` (why this fix was chosen)
- `attempt_number` (1-indexed within this error)
- `git_checkpoint` (commit hash before fix)

## Verification

1. **Limit enforcement:**
   - After 5 attempts on the same error, `burnish_loop()` returns False (escalation)
   - After 15 total attempts, `burnish_loop()` returns False regardless of per-error count
2. **File scope:**
   - Attempting to fix a file under `migrations/` triggers escalation
   - Fixing a file under `backend/src/` is allowed
3. **Git checkpoint:**
   - Before each fix, a git commit is created
   - The commit message contains "checkpoint:" prefix
4. **Decision log:**
   - Each fix creates exactly one JSONL entry
   - The entry contains all required fields
   - Multiple entries append correctly (valid JSONL)
5. **Docker infrastructure errors:**
   - Errors containing "docker daemon", "docker build", or network-related messages trigger escalation to SJ, not burnish loop

## Notes

- The burnish loop is the parent Claude's decision-making process. The code structures here provide the framework (limits, logging, checkpoints), but the actual root cause analysis and fix application is done by the parent Claude using its judgment and codebase access.
- The `burnish_loop()` function is called by the parent harness (SP-D) — it's not a standalone entry point.
- Re-run strategy: if the error is in an early step (setup), re-run from scratch (state may be contaminated). If in a later step (queries), re-run from the failed step.
- The decision log is JSONL (one JSON object per line), not a JSON array. This is intentional — it supports append-only writes without reading the entire file.
- Keep the burnish module thin. The complex part is the parent Claude's analysis, not the scaffolding.
