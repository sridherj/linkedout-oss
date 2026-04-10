#!/bin/bash
# LinkedOut OSS — Full Execution Pipeline
# Dispatches all sub-phases sequentially across all 13 phases
# Run as: bash docs/execution/_pipeline.sh

set -euo pipefail

GOAL_SLUG="linkedout-opensource"
PARENT_RUN_ID="run_20260407_172449_281b54"
OUTPUT_DIR="."
GOAL_DIR="./.taskos"
DECISIONS_FILE="./docs/important_decisions_made_by_agent.md"
PROGRESS_FILE="./docs/execution/_progress.log"
SP_TIMEOUT=2700  # 45 min per sub-phase

# Initialize progress log
echo "=== LinkedOut OSS Execution Pipeline ===" > "$PROGRESS_FILE"
echo "Started: $(date -Iseconds)" >> "$PROGRESS_FILE"
echo "" >> "$PROGRESS_FILE"

log() {
    echo "[$(date '+%H:%M:%S')] $*" >&2
    echo "[$(date '+%H:%M:%S')] $*" >> "$PROGRESS_FILE"
}

# Dispatch a single sub-phase and return run_id
dispatch() {
    local phase_num="$1"
    local sp_file="$2"
    local extra_context="${3:-}"

    local run_id
    run_id=$(curl -s -X POST http://localhost:8000/api/agents/taskos-subphase-runner/trigger \
      -H "Content-Type: application/json" \
      -d '{
        "goal_slug": "'"$GOAL_SLUG"'",
        "parent_run_id": "'"$PARENT_RUN_ID"'",
        "delegation_context": {
          "agent_name": "taskos-subphase-runner",
          "instructions": "Execute sub-phase '"$sp_file"' for Phase '"$phase_num"' of LinkedOut OSS. Read the sub-phase file at docs/execution/phase-'"$phase_num"'/'"$sp_file"' and the shared context at docs/execution/phase-'"$phase_num"'/_shared_context.md. Implement everything specified in the sub-phase file. Write any important decisions to docs/important_decisions_made_by_agent.md under the appropriate phase section. '"$extra_context"'",
          "context": {
            "goal_title": "LinkedOut OpenSource",
            "goal_phase": "Phase '"$phase_num"' execution",
            "relevant_artifacts": [
              "docs/execution/phase-'"$phase_num"'/'"$sp_file"'",
              "docs/execution/phase-'"$phase_num"'/_shared_context.md",
              "docs/plan/phase-'"$phase_num"'*.md"
            ],
            "constraints": [
              "Read the sub-phase file carefully before starting",
              "Follow all acceptance criteria in the sub-phase file",
              "Reference decision docs when specified",
              "Log important decisions to docs/important_decisions_made_by_agent.md"
            ]
          },
          "output": {
            "output_dir": "'"$OUTPUT_DIR"'"
          }
        }
      }' | jq -r '.run_id // empty')

    echo "$run_id"
}

# Wait for a run_id to complete, return status
wait_for() {
    local run_id="$1"
    local label="$2"
    local timeout="$SP_TIMEOUT"
    local elapsed=0

    while [ $elapsed -lt $timeout ]; do
        if [ -f "$GOAL_DIR/.agent-$run_id.output.json" ]; then
            local status
            status=$(cat "$GOAL_DIR/.agent-$run_id.output.json" | jq -r '.status')
            local summary
            summary=$(cat "$GOAL_DIR/.agent-$run_id.output.json" | jq -r '.summary' | head -c 200)
            log "$label: $status — $summary"

            # Log errors if any
            local errors
            errors=$(cat "$GOAL_DIR/.agent-$run_id.output.json" | jq -r '.errors[]? // empty')
            if [ -n "$errors" ]; then
                log "  ERRORS: $errors"
            fi

            echo "$status"
            return 0
        fi

        # Deep poll every 120s
        if [ $((elapsed % 120)) -eq 0 ] && [ $elapsed -gt 0 ]; then
            local http_status
            http_status=$(curl -s "http://localhost:8000/api/agents/jobs/$run_id" | jq -r '.status // "unknown"')
            log "  $label: still $http_status (${elapsed}s elapsed)"
        fi

        sleep 15
        elapsed=$((elapsed + 15))
    done

    log "$label: TIMEOUT after ${timeout}s"
    echo "timeout"
    return 1
}

# Execute a list of sub-phases sequentially for a given phase
run_phase() {
    local phase_num="$1"
    shift
    local sp_files=("$@")

    log "===== PHASE $phase_num: ${#sp_files[@]} sub-phases ====="

    local completed=0
    local failed=0

    for sp_file in "${sp_files[@]}"; do
        log "Dispatching P${phase_num}/$sp_file..."
        local run_id
        run_id=$(dispatch "$phase_num" "$sp_file")

        if [ -z "$run_id" ]; then
            log "  DISPATCH FAILED for $sp_file — skipping"
            failed=$((failed + 1))
            continue
        fi

        log "  Run ID: $run_id"
        sleep 3

        local status
        status=$(wait_for "$run_id" "P${phase_num}/$sp_file")

        if [ "$status" = "completed" ]; then
            completed=$((completed + 1))
        elif [ "$status" = "partial" ]; then
            completed=$((completed + 1))  # Count partial as progress
            log "  WARNING: Partial completion — continuing"
        else
            failed=$((failed + 1))
            log "  FAILED — continuing with next sub-phase"
        fi
    done

    log "===== PHASE $phase_num DONE: $completed completed, $failed failed ====="
    echo ""
}

# ============================================================
# MAIN PIPELINE
# ============================================================

log "Starting full pipeline execution"
log "Phases 1-13, ~81 sub-phases remaining"
log ""

# --- PHASE 01: Remaining SP5 only ---
run_phase "01" "sp5-spdx-headers.md"

# --- PHASE 02: Environment & Config ---
run_phase "02" \
    "sp1-env-example.md" \
    "sp2-config-module.md" \
    "sp3-agent-context-validation.md" \
    "sp4-backend-startup.md" \
    "sp5-update-consumers.md" \
    "sp6-extension-config.md" \
    "sp7-test-infrastructure.md"

# --- PHASE 03: Logging & Observability ---
run_phase "03" \
    "sp1-core-logging-correlation.md" \
    "sp2-metrics-collection.md" \
    "sp3-operation-report-framework.md" \
    "sp4-standardize-logger-usage.md" \
    "sp5-cli-enrichment-logging.md" \
    "sp6-diagnostics-repair.md" \
    "sp7-setup-extension-logging.md"

# --- PHASE 04: Constants Externalization ---
run_phase "04" \
    "sp1-constants-audits.md" \
    "sp2-scoring-constants.md" \
    "sp3-enrichment-constants.md" \
    "sp4-llm-embedding-constants.md" \
    "sp5-infrastructure-constants.md" \
    "sp6-extension-constants.md" \
    "sp7-constants-documentation.md"

# --- PHASE 05: Embedding Abstraction ---
run_phase "05" \
    "sp1-foundation.md" \
    "sp2a-openai-provider.md" \
    "sp2b-local-provider.md" \
    "sp2c-pgvector-schema.md" \
    "sp2d-progress-tracking.md" \
    "sp3-factory-and-callers.md" \
    "sp4-cli-and-tests.md"

# --- PHASE 06: Code Cleanup ---
run_phase "06" \
    "sp1-auth-verification.md" \
    "sp2-project-mgmt-removal.md" \
    "sp3-procrastinate-removal.md" \
    "sp4-langfuse-guard.md" \
    "sp5-small-cleanups.md" \
    "sp6-cli-refactor.md" \
    "sp7-baseline-migration.md" \
    "sp8-dependency-cleanup.md" \
    "sp9-test-suite-green.md"

# --- PHASE 07: Seed Data ---
run_phase "07" \
    "sp1-seed-directory-and-manifest-schema.md" \
    "sp2-seed-export-curation-script.md" \
    "sp3-download-seed-command.md" \
    "sp4-import-seed-command.md" \
    "sp5-github-release-publishing.md" \
    "sp6-integration-testing.md"

# --- PHASE 08: Skill System ---
run_phase "08" \
    "sp1-template-engine-and-host-configs.md" \
    "sp2-core-query-skill.md" \
    "sp3-stub-skills.md" \
    "sp4-generation-script.md" \
    "sp5-routing-and-dev-workflow.md"

# --- PHASE 09: Setup Flow (SP1 UX doc already done) ---
run_phase "09" \
    "sp2-setup-infrastructure.md" \
    "sp3-system-env-setup.md" \
    "sp4-configuration-collection.md" \
    "sp5-data-import.md" \
    "sp6-computation-steps.md" \
    "sp7-readiness-repair-skills.md" \
    "sp8-orchestrator.md" \
    "sp9-installation-tests.md"

# --- PHASE 10: Upgrade (01 UX doc already done) ---
run_phase "10" \
    "02-version-file-utilities.md" \
    "03-update-check-mechanism.md" \
    "04-upgrade-logging-reporting.md" \
    "05-core-upgrade-implementation.md" \
    "06-snooze-support.md" \
    "07-extension-upgrade.md"

# --- PHASE 11: Query History ---
run_phase "11" \
    "sp1-query-logging-and-session-management.md" \
    "sp2-report-formatting-utilities.md" \
    "sp3-linkedout-history-skill.md" \
    "sp4-linkedout-report-skill.md" \
    "sp5-linkedout-setup-report-skill.md" \
    "sp6-integration-tests-and-verification.md"

# --- PHASE 12: Extension (SP1 UX doc already done) ---
run_phase "12" \
    "sp2-build-pipeline.md" \
    "sp3-options-page.md" \
    "sp4-backend-server-management.md" \
    "sp5-extension-logging.md" \
    "sp6-extension-setup-skill.md" \
    "sp7-extension-documentation.md"

# --- PHASE 13: Polish & Launch ---
run_phase "13" \
    "sp1-public-roadmap.md" \
    "sp2-documentation-polish.md" \
    "sp3-test-observability-validation.md" \
    "sp4-ci-e2e-testing.md" \
    "sp5-good-first-issues.md" \
    "sp6-release.md"

# ============================================================
# FINAL SUMMARY
# ============================================================

log ""
log "===== PIPELINE COMPLETE ====="
log "Finished: $(date -Iseconds)"
log ""
log "Review progress: cat $PROGRESS_FILE"
log "Review decisions: cat $DECISIONS_FILE"
