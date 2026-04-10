# Sub-Phase 5: `/linkedout-setup-report` Skill Implementation

**Phase:** 11 — Query History & Reporting
**Plan tasks:** 11E (/linkedout-setup-report Skill)
**Dependencies:** sp2 (Formatters)
**Blocks:** sp6
**Can run in parallel with:** sp3, sp4

## Objective
Implement the `/linkedout-setup-report` skill that wraps `linkedout diagnostics` with health scoring, prioritized recommendations, historical comparison, and interactive repair.

## Context
- Read shared context: `docs/execution/phase-11/_shared_context.md`
- Read plan (11E section): `docs/plan/phase-11-query-history.md`
- Read skill distribution pattern: `docs/decision/2026-04-07-skill-distribution-pattern.md`
- Read existing skill templates for pattern reference
- Read config design decision: `docs/decision/env-config-design.md`

## Deliverables

### 1. Skill Template: `skills/linkedout-setup-report/SKILL.md.tmpl` (NEW or UPDATE)

If Phase 8 created a stub, replace it. If not, create the full skill template.

**Skill frontmatter:**
```yaml
---
name: linkedout-setup-report
description: System health assessment with diagnostics, scoring, and repair suggestions
version: 1.0.0
---
```

**Skill instructions for the AI host:**

The skill wraps `linkedout diagnostics --json` and adds intelligence on top.

**Step 1: Run diagnostics**
- Execute `linkedout diagnostics --json` and parse the JSON output
- Also execute `linkedout status --json` for quick stats

**Step 2: Compute health score**
- Start at 100, subtract points per issue:
  - CRITICAL issue: -20 points each
  - WARNING issue: -5 points each
  - INFO issue: -1 point each
- Floor at 0. Round to integer.
- Display with `format_health_badge(score, issue_count)`

**Step 3: Generate recommendations**
- For each issue from diagnostics, generate a prioritized recommendation:
  - Priority: CRITICAL / WARNING / INFO
  - What: describe the issue in plain language
  - Action: specific command to run (e.g., `linkedout embed`, `linkedout enrich --stale`)
  - Impact: what happens if ignored
- Sort recommendations by priority (CRITICAL first)

**Step 4: Historical comparison**
- Read the most recent `setup-report-*.json` from `{data_dir}/reports/`
- If a previous report exists, diff key metrics:
  - "Since last check (Apr 5): +47 profiles, embedding coverage up 3%"
  - "2 new issues since last check" or "1 issue resolved since last check"
- If no previous report, skip comparison section

**Step 5: Persist report**
- Write the full report as JSON to `{data_dir}/reports/setup-report-YYYYMMDD-HHMMSS.json`
- Schema: `{ "generated_at": "...", "health_score": 92, "issue_count": 1, "issues": [...], "recommendations": [...], "stats": {...} }`

**Two output modes:**

**Summary (default):**
- One-screen overview:
  ```
  System Health: [HEALTHY] 92/100 — 1 issue found

  Network: 4,012 profiles | 2,847 with embeddings (70.9%)
  Companies: 1,203 | Connections: 4,012

  Recommendations:
  1. [WARNING] 1,165 profiles missing embeddings
     Run: linkedout embed --batch 100
  ```

**Detailed (user asks for "detailed" or "full"):**
- Everything from summary PLUS full diagnostics output
- All issues listed with details
- Complete stats breakdown

**Interactive repair:**
- If CRITICAL issues found, prompt: "Found {n} critical issues. Want me to fix them?"
- If user says yes, run `linkedout diagnostics --repair` under the hood
- Report results of repair

**Output designed for GitHub issue paste:**
- Plain text, no ANSI
- Include a "Copy to GitHub issue" section header that makes it clear this can be pasted as-is

### 2. Generated Skill: `skills/claude-code/linkedout-setup-report/SKILL.md` (NEW or UPDATE)

Claude Code-specific skill that:
- Uses `Bash` tool to run `linkedout diagnostics --json` and `linkedout status --json`
- Parses JSON output
- Reads `{data_dir}/reports/setup-report-*.json` for historical comparison via `Read` tool
- Writes new report via `Write` tool or `Bash` with Python
- Uses `Bash` to run `linkedout diagnostics --repair` if user approves

### 3. CLAUDE.md Routing Update

Register `/linkedout-setup-report` in the routing system (if Phase 8 routing exists).

## Verification
After completing all deliverables:
1. Verify skill template has correct frontmatter
2. Verify health scoring algorithm is documented clearly
3. Verify recommendation generation covers all issue types
4. Verify historical comparison logic handles "no previous report" case
5. Test manually:
   - Run `linkedout diagnostics --json` and verify skill can parse it
   - Verify health score computation matches expected output
   - Verify report persists to correct path
   - Verify summary vs detailed output modes
