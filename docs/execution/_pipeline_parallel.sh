#!/bin/bash
# LinkedOut OSS — Parallel Pipeline for P10+P11+P12 → P13
# With within-phase sub-phase parallelism based on DAG analysis
# Usage: bash docs/execution/_pipeline_parallel.sh

set -euo pipefail

GOAL_SLUG="linkedout-opensource"
PARENT_RUN_ID="run_20260407_172449_281b54"
OUTPUT_DIR="."
GOAL_DIR="./.taskos"
PROGRESS_FILE="./docs/execution/_progress.log"
SP_TIMEOUT=2700

log() {
    echo "[$(date '+%H:%M:%S')] $*" >&2
    echo "[$(date '+%H:%M:%S')] $*" >> "$PROGRESS_FILE"
}

dispatch() {
    local phase_num="$1"
    local sp_file="$2"
    curl -s -X POST http://localhost:8000/api/agents/taskos-subphase-runner/trigger \
      -H "Content-Type: application/json" \
      -d '{
        "goal_slug": "'"$GOAL_SLUG"'",
        "parent_run_id": "'"$PARENT_RUN_ID"'",
        "delegation_context": {
          "agent_name": "taskos-subphase-runner",
          "instructions": "Execute sub-phase '"$sp_file"' for Phase '"$phase_num"' of LinkedOut OSS. Read the sub-phase file at docs/execution/phase-'"$phase_num"'/'"$sp_file"' and the shared context at docs/execution/phase-'"$phase_num"'/_shared_context.md. Implement everything specified. Log important decisions to docs/important_decisions_made_by_agent.md.",
          "context": {
            "goal_title": "LinkedOut OpenSource",
            "goal_phase": "Phase '"$phase_num"' execution",
            "relevant_artifacts": [
              "docs/execution/phase-'"$phase_num"'/'"$sp_file"'",
              "docs/execution/phase-'"$phase_num"'/_shared_context.md"
            ],
            "constraints": ["Log important decisions to docs/important_decisions_made_by_agent.md"]
          },
          "output": { "output_dir": "'"$OUTPUT_DIR"'" }
        }
      }' | jq -r '.run_id // empty'
}

# Wait for a single run_id, return status
wait_one() {
    local run_id="$1"
    local label="$2"
    local elapsed=0
    while [ $elapsed -lt $SP_TIMEOUT ]; do
        if [ -f "$GOAL_DIR/.agent-$run_id.output.json" ]; then
            local status
            status=$(jq -r '.status' "$GOAL_DIR/.agent-$run_id.output.json")
            local summary
            summary=$(jq -r '.summary' "$GOAL_DIR/.agent-$run_id.output.json" | head -c 200)
            log "$label: $status — $summary"
            echo "$status"
            return 0
        fi
        if [ $((elapsed % 120)) -eq 0 ] && [ $elapsed -gt 0 ]; then
            log "  $label: still running (${elapsed}s)"
        fi
        sleep 15
        elapsed=$((elapsed + 15))
    done
    log "$label: TIMEOUT"
    echo "timeout"
}

# Dispatch one sub-phase and wait for it (sequential helper)
run_sp() {
    local phase_num="$1"
    local sp_file="$2"
    log "Dispatching P${phase_num}/$sp_file..."
    local run_id
    run_id=$(dispatch "$phase_num" "$sp_file")
    if [ -z "$run_id" ]; then
        log "  DISPATCH FAILED for $sp_file — skipping"
        return 1
    fi
    log "  Run ID: $run_id"
    sleep 3
    wait_one "$run_id" "P${phase_num}/$sp_file"
}

# Dispatch multiple sub-phases in parallel, wait for all
run_sp_parallel() {
    local phase_num="$1"
    shift
    local sp_files=("$@")
    local run_ids=()
    local labels=()

    for sp_file in "${sp_files[@]}"; do
        log "Dispatching P${phase_num}/$sp_file (parallel)..."
        local run_id
        run_id=$(dispatch "$phase_num" "$sp_file")
        if [ -z "$run_id" ]; then
            log "  DISPATCH FAILED for $sp_file — skipping"
            continue
        fi
        log "  Run ID: $run_id"
        run_ids+=("$run_id")
        labels+=("P${phase_num}/$sp_file")
    done

    # Wait for all dispatched agents
    local elapsed=0
    local remaining=${#run_ids[@]}
    declare -A done_map
    while [ $remaining -gt 0 ] && [ $elapsed -lt $SP_TIMEOUT ]; do
        for i in "${!run_ids[@]}"; do
            local rid="${run_ids[$i]}"
            if [ -n "${done_map[$rid]:-}" ]; then continue; fi
            if [ -f "$GOAL_DIR/.agent-$rid.output.json" ]; then
                local status
                status=$(jq -r '.status' "$GOAL_DIR/.agent-$rid.output.json")
                local summary
                summary=$(jq -r '.summary' "$GOAL_DIR/.agent-$rid.output.json" | head -c 200)
                log "${labels[$i]}: $status — $summary"
                done_map[$rid]="$status"
                remaining=$((remaining - 1))
            fi
        done
        if [ $remaining -eq 0 ]; then break; fi
        if [ $((elapsed % 120)) -eq 0 ] && [ $elapsed -gt 0 ]; then
            log "  Parallel group: $remaining still running (${elapsed}s)"
        fi
        sleep 15
        elapsed=$((elapsed + 15))
    done

    if [ $remaining -gt 0 ]; then
        log "  Parallel group: $remaining TIMED OUT"
    fi
}

# ============================================================
# PARALLEL PIPELINE: P10+P11 concurrent, then P12, then P13
# With within-phase sub-phase parallelism
# ============================================================

log ""
log "===== PARALLEL PIPELINE: P10+P11 concurrent → P12 → P13 ====="
log "===== With within-phase sub-phase parallelism ====="
log ""

# ---- PHASE 10: Upgrade (SP01 UX already done) ----
# DAG: SP02 → (SP03+SP04) → SP05 → (SP06+SP07)
run_phase_10() {
    log "===== PHASE 10: Upgrade (6 sub-phases, 4 serial steps) ====="
    run_sp "10" "02-version-file-utilities.md"
    run_sp_parallel "10" "03-update-check-mechanism.md" "04-upgrade-logging-reporting.md"
    run_sp "10" "05-core-upgrade-implementation.md"
    run_sp_parallel "10" "06-snooze-support.md" "07-extension-upgrade.md"
    log "===== PHASE 10 COMPLETE ====="
}

# ---- PHASE 11: Query History ----
# DAG: (SP1+SP2) → (SP3+SP4+SP5) → SP6
run_phase_11() {
    log "===== PHASE 11: Query History (6 sub-phases, 3 serial steps) ====="
    run_sp_parallel "11" "sp1-query-logging-and-session-management.md" "sp2-report-formatting-utilities.md"
    run_sp_parallel "11" "sp3-linkedout-history-skill.md" "sp4-linkedout-report-skill.md" "sp5-linkedout-setup-report-skill.md"
    run_sp "11" "sp6-integration-tests-and-verification.md"
    log "===== PHASE 11 COMPLETE ====="
}

# ---- PHASE 12: Extension (SP1 UX already done) ----
# DAG: (SP2+SP4) → SP3 → SP5 → SP6 → SP7
run_phase_12() {
    log "===== PHASE 12: Extension (6 sub-phases, 5 serial steps) ====="
    run_sp_parallel "12" "sp2-build-pipeline.md" "sp4-backend-server-management.md"
    run_sp "12" "sp3-options-page.md"
    run_sp "12" "sp5-extension-logging.md"
    run_sp "12" "sp6-extension-setup-skill.md"
    run_sp "12" "sp7-extension-documentation.md"
    log "===== PHASE 12 COMPLETE ====="
}

# ---- PHASE 13: Polish & Launch ----
# DAG: (SP1+SP2+SP3) → SP4 → SP5 → SP6
run_phase_13() {
    log "===== PHASE 13: Polish & Launch (6 sub-phases, 4 serial steps) ====="
    run_sp_parallel "13" "sp1-public-roadmap.md" "sp2-documentation-polish.md" "sp3-test-observability-validation.md"
    run_sp "13" "sp4-ci-e2e-testing.md"
    run_sp "13" "sp5-good-first-issues.md"
    run_sp "13" "sp6-release.md"
    log "===== PHASE 13 COMPLETE ====="
}

# ============================================================
# EXECUTION: P10+P11 parallel, then P12 (cli.py conflict with P10), then P13
# ============================================================

# Launch P10 in background subshell
(
    run_phase_10
    touch /tmp/linkedout_p10_done
) &
P10_PID=$!

# Launch P11 in background subshell
(
    run_phase_11
    touch /tmp/linkedout_p11_done
) &
P11_PID=$!

log "P10 (PID $P10_PID) and P11 (PID $P11_PID) running in parallel"

# Wait for P10 to finish (P12 needs cli.py clear)
wait $P10_PID
log "P10 finished. Starting P12 (cli.py safe now)."

# Launch P12 (can start now that P10's cli.py changes are done)
run_phase_12

# Wait for P11 if still running
wait $P11_PID 2>/dev/null || true
log "P11 finished."

# --- PHASE 13: Polish & Launch (after all three done) ---
run_phase_13

log ""
log "===== PARALLEL PIPELINE COMPLETE ====="
log "Finished: $(date -Iseconds)"

# Cleanup
rm -f /tmp/linkedout_p10_done /tmp/linkedout_p11_done
