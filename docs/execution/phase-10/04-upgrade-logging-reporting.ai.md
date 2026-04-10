# Sub-Phase 04: Upgrade Logging & Reporting

**Source task:** 10G
**Complexity:** M
**Dependencies:** Sub-phase 02 (VERSION file & version utilities)
**Can run in parallel with:** Sub-phase 03

## Objective

Set up comprehensive upgrade logging with structured report output. This infrastructure is used by all subsequent upgrade sub-phases. Every step of the upgrade process will produce structured logs and a final upgrade report.

## Context

Read `_shared_context.md` for project-level context. Key points:
- Loguru with human-readable format (no JSON logs)
- Operation result pattern: Progress → Summary → Failures → Report path
- Reports saved to `~/linkedout-data/reports/`
- JSONL metrics to `~/linkedout-data/metrics/daily/`
- Phase 3K defines `OperationReport` format — use compatible structure

## Deliverables

### Files to Create/Modify

1. **Upgrade report structure** (in `backend/src/linkedout/upgrade/upgrader.py` or a dedicated `report.py`)

   Define the upgrade report data structures:

   - `UpgradeStepResult` dataclass:
     - `step`: str (e.g., "pre_flight", "pull_code")
     - `status`: "success" | "skipped" | "failed"
     - `duration_ms`: int
     - `detail`: str | None
     - Additional step-specific fields (e.g., `migrations_applied`)

   - `UpgradeReport` dataclass:
     - `operation`: "upgrade"
     - `timestamp`: ISO 8601 string
     - `duration_ms`: int
     - `from_version`: str
     - `to_version`: str
     - `counts`: dict (`total_steps`, `succeeded`, `skipped`, `failed`)
     - `steps`: list of `UpgradeStepResult`
     - `whats_new`: str | None
     - `next_steps`: list of str
     - `failures`: list of str
     - `rollback`: str
   
   - `write_upgrade_report(report: UpgradeReport)`:
     - Writes to `~/linkedout-data/reports/upgrade-YYYYMMDD-HHMMSS.json`
     - Also appends metrics event to `~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl`
     - Metrics format: `{"metric": "upgrade", "from": "0.1.0", "to": "0.2.0", "status": "success", "duration_ms": 15000, "timestamp": "..."}`

2. **Logging helpers** for upgrade operations:
   - Component binding: `component="cli"`, `operation="upgrade"`
   - Correlation ID per upgrade invocation: `cli_upgrade_YYYYMMDD_HHMM`
   - Step-level logging: log start/success/failure with timing for each step
   - Follow loguru patterns from Phase 3 / `docs/decision/logging-observability-strategy.md`

### Tests to Create

3. **`backend/tests/unit/upgrade/test_upgrader.py`** (report-specific tests)
   - Report structure serialization/deserialization
   - Report file written to correct path
   - Metrics event format is valid JSONL
   - Counts computed correctly from step results
   - Rollback string included in report

## Acceptance Criteria

- [ ] `UpgradeReport` dataclass defined with all required fields
- [ ] `write_upgrade_report()` writes JSON to `~/linkedout-data/reports/upgrade-*.json`
- [ ] Metrics event appended to `~/linkedout-data/metrics/daily/*.jsonl`
- [ ] Logging uses `component="cli"`, `operation="upgrade"` bindings
- [ ] Correlation ID generated per upgrade invocation
- [ ] Report JSON matches the example structure from the phase plan
- [ ] Unit tests pass

## Verification

```bash
# Run unit tests
cd backend && python -m pytest tests/unit/upgrade/test_upgrader.py -v -k "report"

# Verify report structure matches expected format
python -c "
from linkedout.upgrade.upgrader import UpgradeReport, UpgradeStepResult
import json
step = UpgradeStepResult(step='pre_flight', status='success', duration_ms=100)
report = UpgradeReport(
    from_version='0.1.0', to_version='0.2.0',
    steps=[step], whats_new=None, next_steps=[], failures=[], rollback='git checkout v0.1.0'
)
print(json.dumps(report.__dict__, indent=2))
"
```

## Notes

- This sub-phase sets up the infrastructure that sub-phase 05 (Core Upgrade) will use heavily
- If Phase 3's `OperationReport` already exists, use/extend it; otherwise define a compatible structure
- The rollback string should be a template that gets filled in with actual version numbers during upgrade
- Keep the report writer generic enough that it could be reused for other operations (setup, import, etc.)
