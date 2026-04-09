# Decision: Orchestration Dispatch Pattern for Multi-Agent Execution

**Date:** 2026-03-28
**Status:** Accepted
**Context:** linkedin-ai-production goal -- 32 sub-phase dispatches across 6 phases

## Question
How should the parent orchestrator dispatch and monitor child agents at scale (30+ concurrent/sequential agents)?

## Key Findings
1. `parent_run_id` causes child agents to split-pane into parent's tmux session -- breaks on reboot when parent session is gone
2. `status=stuck` persists after `/continue` is sent, making API-only polling unreliable for liveness
3. tmux `capture-pane` is the only reliable way to determine if a child agent is actually working
4. Some agents complete their work but fail to report completion -- output files exist but status shows "failed"
5. Auto-continuing `stuck` agents disrupts them mid-execution when the stuck status is stale

## Decision
1. **Always omit `parent_run_id`** from dispatch -- children create their own tmux sessions
2. **Never auto-continue on `stuck`** -- status is unreliable; notify human instead
3. **Always include autonomous mode instruction** ("CRITICAL AUTONOMOUS MODE: Do NOT ask questions") in child prompts
4. **Verify via artifacts, not API** -- check goal_dir for output files before assuming failure
5. **3-tier polling**: regular (API status), deep (tmux capture-pane), distress (cost/token check)

## Implications
- Children survive parent reboots and can be monitored independently
- Human-in-the-loop required for stuck agents (slightly slower but much more reliable)
- Orchestrator must know each child's goal_dir to verify artifacts
- The 4 issues are documented in ~/workspace/second-brain/orchestration_issue.md for future API fixes

## References
- ~/workspace/second-brain/orchestration_issue.md (detailed issue writeup with evidence)
- /data/workspace/second-brain/taskos/goals/linkedin-ai-production/ (goal directory)
