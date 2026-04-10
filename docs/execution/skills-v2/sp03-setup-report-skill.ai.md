# SP03: Rewrite `/linkedout-setup-report` Skill

## Context

Read `_shared_context.md` first for skill template conventions.

This is the most broken skill. Every section references data structures that don't exist in the
CLI output. After SP01 adds `health_status`, `issues`, and extended `database` stats to
`linkedout diagnostics --json`, this skill can be rewritten to simply display that data.

## Depends On

- **SP01** (health_status, issues, extended DB stats in diagnostics output)

## Tasks

### 3a. Rewrite the skill template

**File:** `skills/linkedout-setup-report/SKILL.md.tmpl`

Read the existing template first to understand the structure and variable syntax.

**New flow (replace existing content, keeping preamble pattern):**

1. **Preamble** — same as current (activate venv, source agent-context.env)

2. **Run diagnostics:**
   ```bash
   linkedout diagnostics --json
   ```

3. **Parse the JSON** — extract `health_status`, `issues`, `database`, `system`, `config`

4. **Display health badge** from `health_status.badge`:
   - `HEALTHY`: `[HEALTHY]`
   - `NEEDS_ATTENTION`: `[NEEDS ATTENTION] — N warnings`
   - `ACTION_REQUIRED`: `[ACTION REQUIRED] — N critical, M warnings`

5. **Display summary** from `database` section:
   ```
   Network: X profiles | Y enriched | Z with embeddings (W%)
   Connections: X total | Y with affinity scores (W%)
   Companies: X | Funding rounds: Y
   ```

6. **Display issues** sorted by severity (CRITICAL first):
   ```
   Issues:
     [CRITICAL] System tenant record missing — CSV import will fail
        Fix: linkedout setup --demo

     [WARNING] 1,200 profiles without embeddings
        Fix: linkedout embed
   ```

7. **Historical comparison** — find latest `diagnostic-*.json` in `~/linkedout-data/reports/`
   (note: `diagnostic-*`, NOT `setup-report-*`)

8. **Persist report** — the CLI already saves to `~/linkedout-data/reports/`. Note the path.

9. **Repair offer** — if CRITICAL issues exist:
   > Found N critical issues. Want me to help fix them?
   For each critical issue, run the suggested `action` command.

**Remove:**
- All local health score computation (CLI does it now via `compute_issues()`)
- The `setup-report-*` filename references (CLI writes `diagnostic-*`)
- The fabricated `issues` schema mapping
- Cost tracking section (data source doesn't exist)

### 3b. Optionally add `linkedout status --json` as supplementary data

The skill can optionally run `linkedout status --json` to add backend status (running/stopped,
PID, port) to the report. This is additive, not required.

## Verification

```bash
# Regenerate the skill for local testing
bin/generate-skills

# Run the skill (manual QA)
# /linkedout-setup-report should show health badge, issues with fix commands, repair offer
```
