# Sub-Phase 3: `/linkedout-history` Skill Implementation

**Phase:** 11 — Query History & Reporting
**Plan tasks:** 11C (/linkedout-history Skill)
**Dependencies:** sp1 (Query Logging), sp2 (Formatters)
**Blocks:** sp6
**Can run in parallel with:** sp4, sp5

## Objective
Implement the `/linkedout-history` skill so users can browse their past network queries in reverse chronological order, with conversation grouping, date range filtering, and text search.

## Context
- Read shared context: `docs/execution/phase-11/_shared_context.md`
- Read plan (11C section): `docs/plan/phase-11-query-history.md`
- Read skill distribution pattern: `docs/decision/2026-04-07-skill-distribution-pattern.md`
- Read existing skill templates for pattern reference: `skills/linkedout-history/SKILL.md.tmpl` (if Phase 8 stub exists) or other skill templates in `skills/`
- Read config design decision: `docs/decision/env-config-design.md`

## Deliverables

### 1. Skill Template: `skills/linkedout-history/SKILL.md.tmpl` (NEW or UPDATE)

If Phase 8 created a stub, replace it. If not, create the full skill template.

**Skill frontmatter:**
```yaml
---
name: linkedout-history
description: Browse past network queries with conversation grouping and search
version: 1.0.0
---
```

**Skill instructions for the AI host:**

The skill should instruct Claude Code to:
1. Read `{{AGENT_CONTEXT_PATH}}` to locate `LINKEDOUT_DATA_DIR` (default: `~/linkedout-data/`)
2. Read JSONL files from `{data_dir}/queries/` directory
3. Parse each line as JSON, collect all query entries
4. Group entries by `session_id` to form conversations
5. Sort sessions by most recent `timestamp` (reverse chronological)

**Default view (no arguments):**
- Show last 7 days of queries
- Group by session, most recent first
- Per session: show initial query text, turn count, timestamp, total results across turns
- Session header format: `--- Session: "who do I know at Stripe?" (3 turns, Apr 7 14:23) ---`
- Under each session header, list individual query turns if turn_count > 1

**Date range filtering:**
- Support natural language: "show me queries from last month", "queries on April 5th", "last 30 days"
- The AI host parses the date range and filters JSONL entries by `timestamp` field

**Text search:**
- "find queries about Stripe", "queries mentioning AI startups"
- Search across `query_text` field (case-insensitive substring match)

**Empty state:**
- If no JSONL files exist or all are empty: `"No query history found. Start querying with /linkedout."`

**Output formatting:**
- Use formatters from `backend/src/linkedout/query_history/formatters.py` (or inline equivalent formatting logic)
- Plain text tables, no ANSI codes
- Output designed for terminal readability AND copy-paste into Slack/GitHub

### 2. Generated Skill: `skills/claude-code/linkedout-history/SKILL.md` (NEW or UPDATE)

If Phase 8's generation script is functional, generate from the template. Otherwise, create a hand-written `SKILL.md` targeting Claude Code directly.

The Claude Code-specific skill should:
- Use the `Read` tool to read JSONL files
- Parse JSON inline (Claude Code can parse JSON in its reasoning)
- Use `Bash` tool to run Python one-liners for complex aggregation if needed
- Reference `~/linkedout-data/config/agent-context.env` for data dir location

### 3. CLAUDE.md Routing Update

If Phase 8's routing system is in place, ensure `/linkedout-history` is registered in the routing file. If not, add a comment in the skill file noting it needs routing registration.

## Verification
After completing all deliverables:
1. Verify skill template exists and has correct frontmatter
2. Verify generated/hand-written SKILL.md is valid and contains complete instructions
3. Test the skill manually:
   - Create sample JSONL data in a temp `~/linkedout-data/queries/` directory
   - Invoke the skill and verify output formatting
   - Test empty state message
   - Test date filtering logic
   - Test text search
