# Sub-Phase 1: UX Design Doc (DESIGN GATE)

**Phase:** 9 — AI-Native Setup Flow
**Plan tasks:** 9A (UX Design Doc)
**Dependencies:** None
**Blocks:** sp2-sp9 (ALL subsequent sub-phases — DESIGN GATE)
**Can run in parallel with:** —

## Objective
Create the complete user-facing flow specification for `/linkedout-setup`. Every screen, question, message, error, and output the user sees during setup must be specified before any implementation begins. This is a DESIGN GATE — SJ must approve this document before implementation sub-phases can proceed.

## Context
- Read shared context: `docs/execution/phase-09/_shared_context.md`
- Read plan (9A section): `docs/plan/phase-09-setup-flow.md`
- Read config design decision: `docs/decision/env-config-design.md`
- Read CLI surface decision: `docs/decision/cli-surface.md`
- Read logging strategy: `docs/decision/logging-observability-strategy.md`
- Read data directory convention: `docs/decision/2026-04-07-data-directory-convention.md`
- Read embedding model decision: `docs/decision/2026-04-07-embedding-model-selection.md`

## Deliverables

### 1. `docs/design/setup-flow-ux.md` (NEW)

This document specifies the complete user experience for the setup flow. It is the blueprint for all implementation tasks (9B through 9Q).

**Required sections:**

#### Section 1: Step Inventory
Numbered list of every setup step with its purpose. Expected ~12-14 steps matching the architecture overview in shared context.

#### Section 2: User Prompts
Exact wording of every question asked to the user, in order:
- OS detection confirmation (if ambiguous)
- Database password confirmation (auto-generated, show to user?)
- Embedding provider choice (OpenAI vs local, with cost/speed tradeoffs)
- OpenAI API key prompt (if OpenAI chosen)
- Apify API key prompt (optional, explain what it enables)
- LinkedIn profile URL
- LinkedIn CSV file path (with auto-detect from ~/Downloads/)
- Contacts import yes/no
- Contacts format (Google CSV or iCloud vCard)
- Seed data tier (core mandatory, full optional with size info)
- Confirmation before starting embedding generation (with time/cost estimate)
- Skill installation confirmation per detected platform

#### Section 3: Progress Format
- Step N of M header format
- Sub-step progress bars (for long operations like embedding)
- Time estimates where applicable
- Cost estimates for API-dependent steps (OpenAI embedding costs)
- Example: how the user sees "Step 7/12: Importing LinkedIn connections... 2,847/4,012 profiles"

#### Section 4: Success Messages
What the user sees after each step completes. Follow the Phase 3 operation result pattern:
- Progress → Summary → Gaps → Next steps → Report path

#### Section 5: Error Messages
For every failure mode, specify:
- (a) What went wrong (user-readable explanation)
- (b) How to fix it (specific instructions)
- (c) How to retry (exact command or "re-run /linkedout-setup")

Failure modes to cover:
- Missing prerequisite (Python too old, no PostgreSQL, no pgvector)
- Wrong Python version
- DB creation failure (permission denied, port in use)
- Network error during seed download
- Invalid API key (OpenAI, Apify)
- CSV parse error (wrong format, corrupted file)
- Embedding failure (model download fails, API rate limit)
- Disk space insufficient

#### Section 6: Readiness Report Format
Mock-up of the final readiness report. Must include:
- Exact console output format (box-drawing characters, alignment)
- Profile count, embedding coverage %, company count, affinity status
- Gap list with actionable remediation
- Next steps (what to try first)
- Report file path

Reference the example in the phase plan (9M section) but finalize exact formatting.

#### Section 7: Diagnostic Report Format
What gets written to `~/linkedout-data/logs/setup-diagnostic-YYYYMMDD-HHMMSS.txt` on failure:
- System info (OS, Python version, PostgreSQL version, disk space)
- Config summary (redacted — no passwords or API keys)
- Step-by-step log (which steps passed, which failed)
- Error details (full traceback for failed step)
- Last 50 lines of relevant log files
- Instructions for filing a GitHub issue

#### Section 8: Idempotency Behavior
What the user sees when re-running setup on a working system:
- Skip messages per step ("✓ Step N: Already complete (skipping)")
- Gap detection on re-run
- Repair offers for detected gaps
- Fresh readiness report always generated

#### Section 9: Skip/Resume Behavior
How partially completed setup resumes:
- Which steps are skippable vs. always-run
- How state is tracked (`~/linkedout-data/state/setup-state.json`)
- What happens if setup is interrupted mid-step
- Version-aware re-runs (new version forces relevant step re-runs)

## Verification
1. Document covers all 12+ setup steps with exact user-facing text
2. Every error mode has a recovery path
3. Readiness report mock-up is included with realistic data
4. Diagnostic report format is specified
5. Idempotency behavior is fully specified
6. No API keys, passwords, or sensitive data appear in example outputs
7. All referenced CLI commands match `docs/decision/cli-surface.md`
8. All config paths match `docs/decision/env-config-design.md`

## IMPORTANT: DESIGN GATE PROCESS
After creating the document:
1. Present a summary to SJ highlighting key UX decisions
2. Call out any areas where you made judgment calls
3. Wait for SJ's approval before marking this sub-phase as complete
4. Implementation sub-phases (sp2-sp9) MUST NOT begin until this document is approved

## Notes
- This is a UX design doc, NOT an implementation plan. Focus on what the USER sees, not how it's built.
- Be opinionated about UX — propose specific wording, don't leave placeholders.
- The setup flow runs inside a Claude Code / Codex / Copilot skill context. The "user" is a developer interacting via natural language. All prompts should be formatted as text output from the skill.
- Cost estimates should use real OpenAI Batch API pricing for text-embedding-3-small / text-embedding-ada-002 equivalent pricing.
- Time estimates should be realistic for consumer hardware (4-8 core CPU, 16GB RAM).
