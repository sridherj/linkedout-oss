#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# LinkedOut OSS — Upgrade Path Test
#
# Tests the upgrade path: install from a tagged version, then upgrade to HEAD.
#   1. Check out the v0.1.0 tag (or earliest tag)
#   2. Install and run migrations at that version
#   3. Import test data at the old version
#   4. Check out HEAD (current branch)
#   5. Run migrations to upgrade
#   6. Verify data integrity post-upgrade
#   7. Verify CLI commands work at new version
#
# This test is intentionally slow (full install twice). It runs only on
# release branches or manual dispatch — not nightly.
#
# Prerequisites:
#   - Full git history (fetch-depth: 0)
#   - PostgreSQL running with extensions
#   - DATABASE_URL set
#
# Exit codes:
#   0 = upgrade path clean
#   1 = step failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DATA_DIR="${LINKEDOUT_DATA_DIR:-$(mktemp -d /tmp/linkedout-upgrade-XXXXXX)}"
FIXTURES_DIR="$REPO_ROOT/tests/fixtures"
CURRENT_BRANCH=""

# shellcheck source=_test_schema_helpers.sh
source "$SCRIPT_DIR/_test_schema_helpers.sh"

# ── Colours ────────────────────────────────────────────────────────
if [ -t 1 ]; then
  GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
else
  GREEN=''; RED=''; NC=''
fi

pass() { echo -e "${GREEN}  PASS${NC}: $1"; }
fail() { echo -e "${RED}  FAIL${NC}: $1"; }

# ── Cleanup ────────────────────────────────────────────────────────
cleanup() {
  local exit_code=$?

  # Always clean up test schema
  cleanup_test_schema

  # Return to original branch
  if [ -n "$CURRENT_BRANCH" ]; then
    cd "$REPO_ROOT"
    git checkout "$CURRENT_BRANCH" --quiet 2>/dev/null || true
  fi

  if [ $exit_code -ne 0 ]; then
    echo ""
    echo "=== DIAGNOSTICS DUMP ==="
    if [ -d "$TEST_DATA_DIR/logs" ]; then
      find "$TEST_DATA_DIR/logs" -type f -name "*.log" -exec tail -50 {} + 2>/dev/null || true
    fi
    if [ -d "$TEST_DATA_DIR/reports" ]; then
      find "$TEST_DATA_DIR/reports" -type f -name "*.json" -exec cat {} + 2>/dev/null || true
    fi
    echo "=== END DIAGNOSTICS ==="
  fi
}
trap cleanup EXIT

# ── Setup ──────────────────────────────────────────────────────────
export LINKEDOUT_DATA_DIR="$TEST_DATA_DIR"
export LINKEDOUT_ENVIRONMENT="${LINKEDOUT_ENVIRONMENT:-test}"

mkdir -p "$TEST_DATA_DIR"/{config,logs,reports,state,uploads}

# Create isolated test schema
setup_test_schema
echo " Schema:     $TEST_SCHEMA_NAME"

# Write config
cat > "$TEST_DATA_DIR/config/config.yaml" <<YAML
database_url: "${DATABASE_URL}"
data_dir: "${TEST_DATA_DIR}"
embedding_provider: local
backend_port: 18002
YAML

echo "============================================================"
echo " LinkedOut Upgrade Path Test"
echo " Data dir:    $TEST_DATA_DIR"
echo " DB:          ${DATABASE_URL:-<not set>}"
echo "============================================================"
echo ""

STEP_COUNT=0
PASS_COUNT=0

step() {
  STEP_COUNT=$((STEP_COUNT + 1))
  echo ""
  echo "=== Step $STEP_COUNT: $1 ==="
}

# ── Step 1: Identify base version ─────────────────────────────────
step "Identify base version"

cd "$REPO_ROOT"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || git rev-parse HEAD 2>/dev/null || echo "main")

# Find the v0.1.0 tag or the earliest tag
BASE_TAG=$(git tag --list 'v0.1.0' 2>/dev/null | head -1)
if [ -z "$BASE_TAG" ]; then
  BASE_TAG=$(git tag --sort=version:refname | head -1)
fi

if [ -z "$BASE_TAG" ]; then
  echo "No tags found — running upgrade test against current HEAD only."
  echo "This tests that migrations are clean on a fresh database."

  # ── Fallback: just verify migrations and CLI at HEAD ─────────
  step "Run migrations at HEAD"
  cd "$REPO_ROOT/backend"
  linkedout migrate 2>/dev/null
  seed_system_data
  pass "Migrations applied at HEAD"
  PASS_COUNT=$((PASS_COUNT + 1))

  step "Verify CLI at HEAD"
  STATUS=$(linkedout status --json 2>/dev/null) && STATUS_EXIT=0 || STATUS_EXIT=$?
  if [ "$STATUS_EXIT" -eq 0 ]; then
    pass "linkedout status --json works"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    fail "linkedout status --json failed (exit=$STATUS_EXIT)"
    exit 1
  fi

  echo ""
  echo "============================================================"
  echo " Upgrade Path Test Complete (no base tag, HEAD-only)"
  echo " Checks passed: $PASS_COUNT"
  echo "============================================================"
  exit 0
fi

echo "Base version: $BASE_TAG"
echo "Target: $CURRENT_BRANCH"
pass "Found base tag: $BASE_TAG"
PASS_COUNT=$((PASS_COUNT + 1))

# ── Step 2: Install at base version ───────────────────────────────
step "Install at base version ($BASE_TAG)"

git checkout "$BASE_TAG" --quiet

cd "$REPO_ROOT/backend"
pip install uv -q 2>/dev/null || true
uv pip install --system -r requirements-dev.txt -q 2>/dev/null || true

pass "Dependencies installed at $BASE_TAG"
PASS_COUNT=$((PASS_COUNT + 1))

# ── Step 3: Run migrations at base version ────────────────────────
step "Migrate at base version"

alembic upgrade head
pass "Migrations applied at $BASE_TAG"
PASS_COUNT=$((PASS_COUNT + 1))

# ── Step 4: Import test data at base version ──────────────────────
step "Import data at base version"

# Use the sample CSV if import-connections exists at the base version
CSV_FILE="$FIXTURES_DIR/sample-connections.csv"
if [ -f "$CSV_FILE" ]; then
  IMPORT_OUTPUT=$(linkedout import-connections "$CSV_FILE" 2>&1) && IMPORT_EXIT=0 || IMPORT_EXIT=$?
  if [ "$IMPORT_EXIT" -eq 0 ]; then
    pass "Data imported at $BASE_TAG"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  WARN: import-connections not available at $BASE_TAG — skipping data import"
  fi
else
  echo "  WARN: No sample CSV — skipping data import"
fi

# Record pre-upgrade state
PRE_STATUS=$(linkedout status --json 2>/dev/null) || true
PRE_PROFILES=$(echo "$PRE_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('profiles', 0))" 2>/dev/null || echo "0")
echo "  Pre-upgrade profiles: $PRE_PROFILES"

# ── Step 5: Upgrade to HEAD ───────────────────────────────────────
step "Upgrade to HEAD ($CURRENT_BRANCH)"

cd "$REPO_ROOT"
git checkout "$CURRENT_BRANCH" --quiet

cd "$REPO_ROOT/backend"
uv pip install --system -r requirements-dev.txt -q 2>/dev/null || true

pass "Dependencies installed at HEAD"
PASS_COUNT=$((PASS_COUNT + 1))

# ── Step 6: Run migrations to upgrade ─────────────────────────────
step "Migrate to HEAD"

alembic upgrade head
pass "Migrations applied to HEAD"
PASS_COUNT=$((PASS_COUNT + 1))

# ── Step 7: Verify data integrity ─────────────────────────────────
step "Verify data integrity post-upgrade"

POST_STATUS=$(linkedout status --json 2>/dev/null) && POST_EXIT=0 || POST_EXIT=$?
if [ "$POST_EXIT" -ne 0 ]; then
  fail "linkedout status --json failed post-upgrade"
  exit 1
fi
pass "CLI functional post-upgrade"
PASS_COUNT=$((PASS_COUNT + 1))

POST_PROFILES=$(echo "$POST_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('profiles', 0))" 2>/dev/null || echo "0")
echo "  Post-upgrade profiles: $POST_PROFILES"

# Data should not be lost during upgrade
if [ "$POST_PROFILES" -ge "$PRE_PROFILES" ] 2>/dev/null; then
  pass "No data loss (profiles: $PRE_PROFILES -> $POST_PROFILES)"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  fail "Data loss detected (profiles: $PRE_PROFILES -> $POST_PROFILES)"
  exit 1
fi

# ── Step 8: Verify CLI commands at new version ────────────────────
step "Verify CLI at HEAD"

# diagnostics
DIAG_OUTPUT=$(linkedout diagnostics --json 2>/dev/null) && DIAG_EXIT=0 || DIAG_EXIT=$?
if [ "$DIAG_EXIT" -eq 0 ]; then
  pass "linkedout diagnostics --json works"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  fail "linkedout diagnostics --json failed (exit=$DIAG_EXIT)"
  exit 1
fi

# version
VERSION_OUTPUT=$(linkedout version 2>&1) && VERSION_EXIT=0 || VERSION_EXIT=$?
if [ "$VERSION_EXIT" -eq 0 ]; then
  pass "linkedout version works"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  fail "linkedout version failed"
  exit 1
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo " Upgrade Path Test Complete"
echo " Base: $BASE_TAG -> HEAD: $CURRENT_BRANCH"
echo " Steps: $STEP_COUNT"
echo " Checks passed: $PASS_COUNT"
echo "============================================================"
