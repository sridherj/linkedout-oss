# SP6: Health Checks + Diagnostics + Auto-Repair

**Sub-Phase:** 6 of 7
**Tasks:** 3M (Setup Report Data Layer) + 3I (Diagnostic Report Generator) + 3J (Auto-Repair Hooks)
**Complexity:** S + L + M = L
**Depends on:** SP3 (OperationReport used by repair hooks)
**Blocks:** None

---

## Objective

Build the health check functions, the `linkedout diagnostics` CLI command, and the extensible auto-repair hook framework. This is the largest sub-phase but the three tasks form a tight dependency chain (health checks → diagnostics → repair) and share the same code surface.

---

## Context

Read `_shared_context.md` for project-level context.

**Key decisions:**
- Register diagnostics as `rcv2 db diagnostics` for now (Phase 6 creates the `linkedout` CLI)
- `--json` flag for structured JSON output
- `--repair` flag to detect and fix common issues interactively
- No secrets in output — API keys show only "configured" / "not configured"
- Output designed to be pasted into a GitHub issue

---

## Tasks

### 1. Create Health Check Functions (3M)

**File:** `backend/src/shared/utilities/health_checks.py` (NEW)

```python
@dataclass
class HealthCheckResult:
    check: str
    status: Literal["pass", "fail", "skip"]
    detail: str = ""

def check_db_connection() -> HealthCheckResult:
    """Test PostgreSQL connectivity. Returns pass/fail."""

def check_embedding_model() -> HealthCheckResult:
    """Check if embedding model is loaded/available. Returns pass/skip."""

def check_api_keys() -> list[HealthCheckResult]:
    """Check configured API keys (openai, apify). Returns configured/not configured."""

def check_disk_space() -> HealthCheckResult:
    """Check disk space for linkedout-data directory. Pass if >1GB free."""

def get_db_stats() -> dict:
    """Return profile count, company count, connection count, embedding coverage %,
    last enrichment date, schema version (Alembic head)."""
```

Requirements:
- Each health check must handle connection errors gracefully (return `fail` status, not exception)
- `check_api_keys()` NEVER returns the actual key value — only "configured" / "not configured"
- `get_db_stats()` needs a database session — accept one as parameter or create one internally
- When DB is not configured, return "not configured" status, not an error
- These functions must be independently callable (not tied to the CLI command)

### 2. Create Diagnostics Command (3I)

**File:** `backend/src/dev_tools/diagnostics.py` (NEW)

Implement `diagnostics` command (registered as `rcv2 db diagnostics` in `cli.py`):

#### System Info
- OS name + version
- Python version
- PostgreSQL version (from DB connection or `psql --version`)
- LinkedOut version (from `__version__` or pyproject.toml)
- Disk free space (GB)
- Data dir path (`~/linkedout-data/`)
- Data dir size (MB)

#### Config Summary
- Embedding provider (local/openai)
- Embedding model name
- Backend URL
- API key status: "configured" / "not configured" for each key
- Langfuse enabled/disabled
- Log level

#### Database Stats (from `get_db_stats()`)
- profiles_total, profiles_with_embeddings, profiles_without_embeddings
- companies_total, connections_total
- last_enrichment date
- schema_version (Alembic head hash)

#### Health Checks
Run all `check_*` functions and collect results.

#### Recent Errors
Parse last 50 lines of each log file in `~/linkedout-data/logs/` for ERROR/CRITICAL entries. Group by component.

#### Output Formats
- **Default:** Human-readable summary to stdout
- **`--json`:** Structured JSON to stdout (matching the schema in `docs/decision/logging-observability-strategy.md` section 10)
- **Always:** Write to `~/linkedout-data/reports/diagnostic-YYYYMMDD-HHMMSS.json`

### 3. Register Diagnostics Command in CLI (3I)

**File:** `backend/src/dev_tools/cli.py`

Add `diagnostics` as a subcommand under the `db` group (or appropriate group):
```python
@db.command()
@click.option('--json', 'output_json', is_flag=True, help='Output structured JSON')
@click.option('--repair', is_flag=True, help='Detect and offer to fix common issues')
def diagnostics(output_json, repair):
    ...
```

### 4. Create Auto-Repair Framework (3J)

**File:** `backend/src/shared/utilities/repair.py` (NEW)

```python
@dataclass
class RepairDetection:
    needs_repair: bool
    count: int = 0
    description: str = ""

@dataclass
class RepairHook:
    name: str
    description: str
    detect: Callable[[], RepairDetection]
    repair: Callable[[], OperationReport]
```

Registry pattern:
```python
_repair_hooks: list[RepairHook] = []

def register_repair_hook(hook: RepairHook) -> None:
    """Register a new repair hook. Other phases call this to add their own hooks."""
    _repair_hooks.append(hook)

def get_repair_hooks() -> list[RepairHook]:
    """Return all registered repair hooks."""
    return list(_repair_hooks)
```

### 5. Register Initial Repair Hooks (3J)

Register these hooks (in `diagnostics.py` or a separate registration module):

| Hook | Detects | Repairs |
|------|---------|---------|
| `missing_embeddings` | Profiles without embeddings | Offer to run embedding generation |
| `missing_affinity` | Connections without affinity scores | Offer to run compute-affinity |
| `stale_enrichment` | Profiles with enrichment older than TTL | Offer re-enrichment |

### 6. Implement `--repair` Flow (3J)

In `diagnostics.py`:
```
1. Run all detection hooks
2. For each detected gap:
   - Print description and count
   - Prompt: "Fix N items? [Y/n]"
   - On confirm: run repair function
   - Print repair result via OperationReport.print_summary()
3. If nothing detected: "No issues found."
```

---

## Files to Create

| File | Description |
|------|-------------|
| `backend/src/shared/utilities/health_checks.py` | Reusable health check functions |
| `backend/src/dev_tools/diagnostics.py` | Diagnostics command implementation |
| `backend/src/shared/utilities/repair.py` | Auto-repair hook framework |
| `tests/unit/shared/test_health_checks.py` | Health check unit tests |
| `tests/unit/shared/test_repair.py` | Repair hook unit tests |

## Files to Modify

| File | Changes |
|------|---------|
| `backend/src/dev_tools/cli.py` | Register `diagnostics` command |

---

## Verification

### Unit Tests

**`tests/unit/shared/test_health_checks.py`:**
- Each health check function returns `HealthCheckResult` with correct fields
- `check_api_keys()` never returns actual key values
- `get_db_stats()` returns expected dict structure (mock DB session)
- Graceful handling when DB/services are unavailable

**`tests/unit/shared/test_repair.py`:**
- `register_repair_hook()` adds to the registry
- `get_repair_hooks()` returns registered hooks
- Detect function returns `RepairDetection` with correct fields
- Repair flow calls detect → prompt → repair in order

### Integration Checks

- `rcv2 db diagnostics` produces a comprehensive report
- `--json` flag outputs valid JSON matching the expected schema
- Report is saved to `~/linkedout-data/reports/diagnostic-*.json`
- No secrets appear in the output
- Running on a healthy system shows all health checks as "pass"
- `--repair` detects issues and prompts for confirmation before fixing

---

## Acceptance Criteria

- [ ] `rcv2 db diagnostics` produces comprehensive report: system, config, database, health
- [ ] `--json` flag outputs valid JSON
- [ ] Report is saved to `~/linkedout-data/reports/`
- [ ] No secrets appear in the output
- [ ] Health checks handle unavailable services gracefully
- [ ] `--repair` detects and offers to fix common issues
- [ ] Each repair is interactive (asks before acting)
- [ ] Repairs produce `OperationReport` artifacts
- [ ] Repair framework is extensible (register one `RepairHook` to add a new check)
- [ ] `get_db_stats()` returns profile/company/embedding coverage stats
