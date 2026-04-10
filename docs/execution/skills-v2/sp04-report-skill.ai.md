# SP04: Rewrite `/linkedout-report` Skill

## Context

Read `_shared_context.md` first for skill template conventions.

Currently non-functional — depends on cost tracking files and profile freshness by `enriched_at`
(wrong column name) that don't exist. After SP01 adds extended diagnostics and SP02a wires up
query logging, this skill can work — but must be honest about what data is available.

## Depends On

- **SP01** (extended diagnostics output)
- **SP02a** (query logging — populates `~/linkedout-data/queries/*.jsonl`)

## Tasks

### 4a. Rewrite the skill template

**File:** `skills/linkedout-report/SKILL.md.tmpl`

Read the existing template first.

**New sections (in order):**

1. **Network Overview** — from `linkedout status --json` + `linkedout diagnostics --json`
   - Profile count, enrichment coverage, embedding coverage
   - Connection count, affinity coverage
   - Company count, funding rounds
   - This section always works after setup

2. **Query Activity** — from `~/linkedout-data/queries/*.jsonl`
   - If no files: "No query history yet. Try: `/linkedout \"who do I know at Google?\"`"
   - If files exist: total queries, queries this week, most common query types, avg results per query
   - Group by session, show recent sessions

3. **Import History** — from `~/linkedout-data/reports/import-csv-*.json`
   - If no files: "No imports recorded."
   - If files exist: date, row count, matched/unenriched/errors breakdown

4. **System Health Snapshot** — from `linkedout diagnostics --json`
   - Health badge from `health_status`
   - Top issues (if any)

**Remove entirely:**
- Cost tracking section (no data source)
- Profile freshness by `enriched_at` (wrong column; use `has_enriched_data` count from diagnostics)
- Elaborate session grouping logic (keep it simple — list recent sessions)

**Active empty-state guidance (Review Decision #7):** Every empty state includes a specific
next-step command the user can run.

## Verification

```bash
bin/generate-skills
# /linkedout-report — Network overview should always work; query activity shows data after queries
```
