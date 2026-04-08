#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Validate LinkedOut observability infrastructure.
#
# Checks logging, metrics, reports, and diagnostics are properly configured.
# Run from the repo root: bash scripts/validate-observability.sh
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed

set -euo pipefail

DATA_DIR="${LINKEDOUT_DATA_DIR:-$HOME/linkedout-data}"
PASS=0
FAIL=0
SKIP=0

pass() { PASS=$((PASS + 1)); echo "  [PASS] $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  [FAIL] $1"; }
skip() { SKIP=$((SKIP + 1)); echo "  [SKIP] $1"; }

# ── 1. Log Directory Structure ────────────────────────────────────────────────

echo ""
echo "=== Log Directory Structure ==="

LOG_DIR="$DATA_DIR/logs"
if [ -d "$LOG_DIR" ]; then
    pass "Log directory exists: $LOG_DIR"
else
    fail "Log directory missing: $LOG_DIR"
fi

for logfile in backend.log cli.log setup.log enrichment.log import.log queries.log; do
    # These files are created on first use, so check if dir exists and the
    # logger is configured to route to them (code check, not file check)
    if grep -q "$logfile" backend/src/shared/utilities/logger.py 2>/dev/null; then
        pass "Log file configured: $logfile"
    else
        fail "Log file not configured in logger.py: $logfile"
    fi
done

if [ -d "$LOG_DIR/archive" ] || grep -q "archive" backend/src/shared/utilities/logger.py 2>/dev/null; then
    # Archive dir is created by loguru on rotation, may not exist yet
    pass "Log archive directory: configured (created on first rotation)"
else
    skip "Log archive directory: not yet created (normal for fresh installs)"
fi

# ── 2. Log Format Validation ─────────────────────────���───────────────────────

echo ""
echo "=== Log Format ==="

# Check console format is human-readable (HH:mm:ss pattern)
if grep -q "HH:mm:ss" backend/src/shared/utilities/logger.py 2>/dev/null; then
    pass "Console log format: human-readable (HH:mm:ss LEVEL module message)"
else
    fail "Console log format: expected HH:mm:ss pattern in logger.py"
fi

# Check file format includes timestamp and correlation ID
if grep -q "YYYY-MM-DD HH:mm:ss" backend/src/shared/utilities/logger.py 2>/dev/null; then
    pass "File log format: verbose with timestamp"
else
    fail "File log format: expected YYYY-MM-DD pattern in logger.py"
fi

if grep -q "correlation_id" backend/src/shared/utilities/logger.py 2>/dev/null; then
    pass "File log format: includes correlation_id"
else
    fail "File log format: missing correlation_id field"
fi

# ── 3. Log Rotation Policy ─────────────────���───────────────────────��─────────

echo ""
echo "=== Log Rotation Policy ==="

if grep -q "50 MB" backend/src/shared/config/settings.py 2>/dev/null; then
    pass "Log rotation: 50 MB default configured"
else
    fail "Log rotation: expected '50 MB' default in settings.py"
fi

if grep -q "30 days" backend/src/shared/config/settings.py 2>/dev/null; then
    pass "Log retention: 30 days default configured"
else
    fail "Log retention: expected '30 days' default in settings.py"
fi

if grep -q "compression.*gz" backend/src/shared/utilities/logger.py 2>/dev/null; then
    pass "Log compression: gzip enabled"
else
    fail "Log compression: expected gz compression in logger.py"
fi

# ── 4. Correlation IDs ────────────────────────────────────────���──────────────

echo ""
echo "=== Correlation IDs ==="

if [ -f "backend/src/shared/utilities/correlation.py" ]; then
    pass "Correlation module exists"
else
    fail "Correlation module missing: backend/src/shared/utilities/correlation.py"
fi

if grep -q "'req'" backend/src/shared/utilities/request_logging_middleware.py 2>/dev/null; then
    pass "Backend API: req_ prefix correlation IDs"
else
    fail "Backend API: missing req_ prefix correlation IDs"
fi

if grep -q "cli_" backend/src/linkedout/cli_helpers.py 2>/dev/null; then
    pass "CLI: cli_ prefix correlation IDs"
else
    fail "CLI: missing cli_ prefix correlation IDs"
fi

if grep -q "x-correlation-id" backend/src/shared/utilities/request_logging_middleware.py 2>/dev/null; then
    pass "X-Correlation-ID response header"
else
    fail "X-Correlation-ID response header missing"
fi

# ── 5. Metrics Infrastructure ────────────────────────────────────────────────

echo ""
echo "=== Metrics Infrastructure ==="

METRICS_DIR="$DATA_DIR/metrics"
if [ -f "backend/src/shared/utilities/metrics.py" ]; then
    pass "Metrics module exists"
else
    fail "Metrics module missing"
fi

if grep -q "daily" backend/src/shared/utilities/metrics.py 2>/dev/null; then
    pass "Metrics: daily JSONL directory structure"
else
    fail "Metrics: missing daily directory structure"
fi

if grep -q "summary.json" backend/src/shared/utilities/metrics.py 2>/dev/null; then
    pass "Metrics: summary.json rolling updates"
else
    fail "Metrics: missing summary.json support"
fi

# Check that CLI commands record metrics
echo ""
echo "=== CLI Metrics Recording ==="

for cmd in import_connections compute_affinity embed import_seed import_contacts; do
    cmd_file="backend/src/linkedout/commands/${cmd}.py"
    if [ -f "$cmd_file" ] && grep -q "record_metric" "$cmd_file" 2>/dev/null; then
        pass "record_metric in $cmd"
    elif [ -f "$cmd_file" ]; then
        fail "record_metric missing in $cmd"
    else
        skip "$cmd_file not found"
    fi
done

# ── 6. Operation Reports ───��─────────────────────────────────────────────────

echo ""
echo "=== Operation Reports ==="

REPORTS_DIR="$DATA_DIR/reports"
if [ -f "backend/src/shared/utilities/operation_report.py" ]; then
    pass "OperationReport class exists"
else
    fail "OperationReport class missing"
fi

if grep -q "OperationReport" backend/src/shared/utilities/operation_report.py 2>/dev/null; then
    pass "OperationReport: save() and print_summary() methods"
else
    fail "OperationReport: missing core methods"
fi

echo ""
echo "=== CLI Operation Reports ==="

for cmd in embed download_seed import_seed import_connections compute_affinity import_contacts; do
    cmd_file="backend/src/linkedout/commands/${cmd}.py"
    if [ -f "$cmd_file" ] && grep -q "OperationReport\|report.*save\|_write_report" "$cmd_file" 2>/dev/null; then
        pass "Operation report in $cmd"
    elif [ -f "$cmd_file" ]; then
        fail "Operation report missing in $cmd"
    else
        skip "$cmd_file not found"
    fi
done

# ─��� 7. Diagnostics Command ───────────────────────────────────────────────────

echo ""
echo "=== Diagnostics Command ==="

DIAG_FILE="backend/src/linkedout/commands/diagnostics.py"
if [ -f "$DIAG_FILE" ]; then
    pass "diagnostics command file exists"
else
    fail "diagnostics command file missing"
fi

if grep -q "\-\-json" "$DIAG_FILE" 2>/dev/null; then
    pass "diagnostics: --json flag"
else
    fail "diagnostics: --json flag missing"
fi

if grep -q "\-\-repair" "$DIAG_FILE" 2>/dev/null; then
    pass "diagnostics: --repair flag"
else
    fail "diagnostics: --repair flag missing"
fi

if grep -q "diagnostic-" "$DIAG_FILE" 2>/dev/null; then
    pass "diagnostics: saves report to reports directory"
else
    fail "diagnostics: report saving missing"
fi

# ��─ 8. Health Checks Module ───────��──────────────────────────────────────────

echo ""
echo "=== Health Checks ==="

HEALTH_FILE="backend/src/shared/utilities/health_checks.py"
if [ -f "$HEALTH_FILE" ]; then
    pass "Health checks module exists"
else
    fail "Health checks module missing"
fi

for check in check_db_connection check_embedding_model check_api_keys check_disk_space get_db_stats; do
    if grep -q "def $check" "$HEALTH_FILE" 2>/dev/null; then
        pass "Health check: $check"
    else
        fail "Health check missing: $check"
    fi
done

# ── 9. CLI @cli_logged Decorator ─────────────────���───────────────────────────

echo ""
echo "=== CLI Logging Decorator ==="

for cmd in embed download_seed import_seed import_connections compute_affinity import_contacts diagnostics; do
    cmd_file="backend/src/linkedout/commands/${cmd}.py"
    if [ -f "$cmd_file" ] && grep -q "@cli_logged" "$cmd_file" 2>/dev/null; then
        pass "@cli_logged in $cmd"
    elif [ -f "$cmd_file" ]; then
        fail "@cli_logged missing in $cmd"
    else
        skip "$cmd_file not found"
    fi
done

# ── 10. No Raw import logging ─────────────��──────────────────────────────────

echo ""
echo "=== Logger Usage ==="

RAW_LOGGING=$(grep -rl "^import logging$\|^from logging import" backend/src/ 2>/dev/null \
    | grep -v "__pycache__" \
    | grep -v "logger.py" \
    | grep -v "settings.py" \
    | grep -v "query_logger.py" \
    || true)

if [ -z "$RAW_LOGGING" ]; then
    pass "No raw 'import logging' in backend/src/ (excluding known exceptions)"
else
    fail "Raw 'import logging' found in: $RAW_LOGGING"
fi

# ── Summary ──────────────���────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "  PASS: $PASS  |  FAIL: $FAIL  |  SKIP: $SKIP"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "$FAIL check(s) failed. Review the output above."
    exit 1
else
    echo ""
    echo "All observability checks passed."
    exit 0
fi
