# SP05: Rewrite `/linkedout-history` Skill

## Context

Read `_shared_context.md` first for skill template conventions.

Same root cause as `/linkedout-report` — depends on query JSONL files that nothing populates.
After SP02a wires up query logging, this works.

## Depends On

- **SP02a** (query logging — populates `~/linkedout-data/queries/*.jsonl`)

## Tasks

### 5a. Simplify the skill template

**File:** `skills/linkedout-history/SKILL.md.tmpl`

Read the existing template first. The current template is overkill — target under 100 lines.

**New flow:**

1. Check for JSONL files in `~/linkedout-data/queries/`

2. If none exist:
   > No query history yet. Try: `/linkedout "who do I know at Google?"` — your queries are logged automatically.

3. If files exist:
   - Default: show last 7 days of sessions
   - Each session: initial query, turn count, result count, timestamp
   - Support "last month", "search for X", date range filtering

4. Keep it under 100 lines.

**Active empty-state guidance (Review Decision #7):** The empty-state message includes a specific
command the user can run.

## Verification

```bash
bin/generate-skills
# After running a few /linkedout queries, /linkedout-history shows them grouped by session
```
