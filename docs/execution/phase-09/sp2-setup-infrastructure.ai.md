# Sub-Phase 2: Setup Infrastructure (Logging + Prerequisites)

**Phase:** 9 — AI-Native Setup Flow
**Plan tasks:** 9P (Setup Logging Integration), 9B (Prerequisites Detection)
**Dependencies:** sp1 (UX Design Doc approved)
**Blocks:** sp3
**Can run in parallel with:** —

## Objective
Build the cross-cutting logging infrastructure for setup and the prerequisites detection module. These two are grouped because: (1) logging is a foundation all other modules depend on, and (2) prerequisites detection is the first step in the setup flow and has no other dependencies. Together they form the infrastructure layer for all subsequent implementation sub-phases.

## Context
- Read shared context: `docs/execution/phase-09/_shared_context.md`
- Read plan (9P + 9B sections): `docs/plan/phase-09-setup-flow.md`
- Read UX design doc: `docs/design/setup-flow-ux.md` (created in sp1 — use exact wording from there)
- Read logging strategy: `docs/decision/logging-observability-strategy.md`
- Read config design: `docs/decision/env-config-design.md`
- Read data directory convention: `docs/decision/2026-04-07-data-directory-convention.md`

## Deliverables

### 1. `backend/src/linkedout/setup/__init__.py` (NEW)
Package init. Export the main public API for the setup package.

### 2. `backend/src/linkedout/setup/logging_integration.py` (NEW)

Setup-specific logging configuration that wraps Phase 3 infrastructure.

**Setup correlation ID:**
- Generate `setup_{timestamp}` correlation ID at setup start
- All steps bind this correlation ID to their loguru context
- Use Phase 3 `get_logger()` with `component="setup"` binding

**Per-step logging pattern:**
- Start: `"Starting step N/M: {step_name}"`
- Key parameters: step-specific context (e.g., `"PostgreSQL 16.2, database: linkedout"`)
- Progress milestones: `"Migration 001: applied (45ms)"`
- Result: `"{step_name} complete ({duration}s)"`
- Or failure: `"{step_name} FAILED: {error_description}"`

**Setup log file routing:**
- Route all setup output to `~/linkedout-data/logs/setup.log` (appended across re-runs)
- Use Phase 3 loguru sink configuration

**Failure diagnostic generation:**
- On any step failure, auto-generate `~/linkedout-data/logs/setup-diagnostic-YYYYMMDD-HHMMSS.txt`
- Contents: system info, redacted config summary, step-by-step log, error details, last 50 lines of relevant logs
- Use exact format from UX design doc (sp1)

**Step result tracking:**
- Each step produces a result following Phase 3 `OperationReport` pattern
- Track: step name, status (success/failed/skipped), duration, item counts, errors

**Key functions:**
- `init_setup_logging() -> str` — initialize logging, return correlation ID
- `get_setup_logger(step_name: str)` — return logger bound to setup context + step name
- `generate_diagnostic(error: Exception, steps_completed: list, config: dict) -> Path` — write diagnostic file
- `log_step_start(step_num: int, total: int, step_name: str)` — standardized step start
- `log_step_complete(step_name: str, duration: float, report: OperationReport)` — standardized step end

**Security:**
- NEVER log API keys, passwords, or LinkedIn URLs
- Redact sensitive fields in diagnostic file
- Use `[REDACTED]` for any config value that might be sensitive

### 3. `backend/src/linkedout/setup/prerequisites.py` (NEW)

OS detection and dependency verification. This is the first step in the setup flow.

**Data classes:**
```python
@dataclass
class PlatformInfo:
    os: str          # "linux", "macos", "windows"
    distro: str      # "ubuntu", "arch", "fedora", "macos", "wsl"
    package_manager: str  # "apt", "pacman", "dnf", "brew", "none"
    arch: str        # "x86_64", "arm64"

@dataclass
class PostgresStatus:
    installed: bool
    running: bool
    version: str | None      # e.g., "16.2"
    major_version: int | None  # e.g., 16
    has_pgvector: bool
    has_pg_trgm: bool

@dataclass
class PythonStatus:
    installed: bool
    version: str | None     # e.g., "3.12.1"
    has_pip: bool
    has_venv: bool

@dataclass
class DiskStatus:
    free_gb: float
    mount_point: str
    sufficient: bool         # >= 2GB
    recommended: bool        # >= 5GB

@dataclass
class PrerequisiteReport:
    platform: PlatformInfo
    postgres: PostgresStatus
    python: PythonStatus
    disk: DiskStatus
    ready: bool              # all checks pass
    blockers: list[str]      # human-readable list of what's missing
```

**OS detection (1):**
- Linux: detect Debian/Ubuntu (apt), Arch (pacman), RPM/Fedora (dnf/yum) via `/etc/os-release`
- macOS: detect via `platform.system()`, verify Homebrew via `brew --version`
- WSL: detect via `/proc/version` containing "microsoft" or "WSL"
- Windows native: detect, recommend WSL2

**PostgreSQL check (2):**
- `psql --version` for client version
- `pg_isready` for running server
- Version >= 14 (pgvector compatibility)
- pgvector: `psql -c "SELECT * FROM pg_available_extensions WHERE name = 'vector'"` (only if server running)
- pg_trgm: same check for `pg_trgm`

**Python check (3):**
- `python3 --version` >= 3.11
- `pip` or `pip3` available
- `python3 -c "import venv"` succeeds

**Disk space check (4):**
- Check free space on `~/linkedout-data/` mount point (or parent if dir doesn't exist yet)
- Minimum: 2GB. Recommended: 5GB.

**Key functions:**
- `detect_platform() -> PlatformInfo`
- `check_postgres() -> PostgresStatus`
- `check_python() -> PythonStatus`
- `check_disk_space(data_dir: Path) -> DiskStatus`
- `run_all_checks(data_dir: Path | None = None) -> PrerequisiteReport`

**All checks must be non-destructive (read-only).** No subprocess calls that modify system state.

### 4. Unit Tests

**`backend/tests/linkedout/setup/__init__.py`** (NEW) — empty test package init

**`backend/tests/linkedout/setup/test_logging_integration.py`** (NEW)
- `init_setup_logging()` returns a correlation ID matching `setup_*` pattern
- `get_setup_logger()` returns a logger with correct component binding
- `generate_diagnostic()` creates a file at the expected path
- Diagnostic file does NOT contain any `[REDACTED]` markers replaced by actual secrets
- Step logging functions produce expected log messages

**`backend/tests/linkedout/setup/test_prerequisites.py`** (NEW)
- `detect_platform()` returns valid `PlatformInfo` on current OS
- `check_python()` correctly detects current Python version
- `check_disk_space()` returns valid `DiskStatus` for a temp directory
- `PrerequisiteReport.blockers` is empty when all checks pass
- Mock tests for each OS variant (Ubuntu, Arch, Fedora, macOS, WSL)
- Mock tests for missing PostgreSQL, wrong version, missing pgvector

## Verification
1. `python -c "from linkedout.setup.logging_integration import init_setup_logging; print(init_setup_logging())"` prints a correlation ID
2. `python -c "from linkedout.setup.prerequisites import run_all_checks; r = run_all_checks(); print(r.platform)"` prints platform info
3. `pytest backend/tests/linkedout/setup/test_logging_integration.py -v` passes
4. `pytest backend/tests/linkedout/setup/test_prerequisites.py -v` passes

## Notes
- Use `subprocess.run(capture_output=True)` for shell command checks. Never use `os.system()`.
- All subprocess calls should have a timeout (10 seconds max for version checks).
- The logging module is a thin wrapper around Phase 3 infrastructure — don't duplicate `get_logger()`, extend it.
- Prerequisites detection is read-only. It answers "what's installed?" — it does NOT install anything.
- Use the exact error messages and progress format from the UX design doc (sp1).
