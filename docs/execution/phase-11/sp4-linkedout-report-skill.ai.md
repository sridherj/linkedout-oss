# Sub-Phase 4: `/linkedout-report` Skill Implementation

**Phase:** 11 — Query History & Reporting
**Plan tasks:** 11D (/linkedout-report Skill)
**Dependencies:** sp1 (Query Logging), sp2 (Formatters)
**Blocks:** sp6
**Can run in parallel with:** sp3, sp5

## Objective
Implement the `/linkedout-report` skill so users get a usage summary showing query patterns, network activity, enrichment costs, and profile health.

## Context
- Read shared context: `docs/execution/phase-11/_shared_context.md`
- Read plan (11D section): `docs/plan/phase-11-query-history.md`
- Read skill distribution pattern: `docs/decision/2026-04-07-skill-distribution-pattern.md`
- Read existing skill templates for pattern reference
- Read config design decision: `docs/decision/env-config-design.md`
- Read logging/observability strategy: `docs/decision/logging-observability-strategy.md`

## Deliverables

### 1. Skill Template: `skills/linkedout-report/SKILL.md.tmpl` (NEW or UPDATE)

If Phase 8 created a stub, replace it. If not, create the full skill template.

**Skill frontmatter:**
```yaml
---
name: linkedout-report
description: Usage summary with query patterns, network stats, and cost tracking
version: 1.0.0
---
```

**Skill instructions for the AI host:**

The skill aggregates data from multiple sources and produces a sectioned report.

**Data sources:**
1. **Query history:** `{data_dir}/queries/*.jsonl` — query activity stats
2. **Metrics:** `{data_dir}/metrics/daily/*.jsonl` — enrichment costs, embedding stats
3. **Operation reports:** `{data_dir}/reports/import-csv-*.json` — import history, network growth
4. **Database:** Direct queries via `agent-context.env` credentials — network stats, profile freshness
5. **CLI:** `linkedout status --json` — quick DB stats

**Report sections (in order):**

**1. Query Activity**
- Total queries (all time)
- Queries this week / this month
- Average queries per day (over last 30 days)
- Most active days (top 3 by query count)
- Source: `{data_dir}/queries/*.jsonl`

**2. Top Searches**
- Most frequently searched companies (top 5, extracted from `query_text`)
- Most frequently searched topics/keywords (top 5)
- Most common `query_type` values
- Source: `{data_dir}/queries/*.jsonl`

**3. Network Stats**
- Total connections in DB
- Connections by Dunbar tier (if tiers are assigned)
- Profiles with embeddings / total profiles (embedding coverage %)
- Companies in DB
- Source: DB queries via `agent-context.env`, or `linkedout status --json`

**4. Network Growth**
- New connections added over time (from import reports)
- Most recent import date and count
- Source: `{data_dir}/reports/import-csv-*.json`

**5. Cost Tracker**
- Cumulative enrichment cost (from metrics)
- Embedding generation cost
- Total API spend
- Source: `{data_dir}/metrics/daily/*.jsonl`
- **If no cost metrics exist, skip section** with note: "Cost tracking data not yet available."

**6. Profile Freshness**
- % of profiles enriched in last 30 / 90 / 180 days
- Count of stale profiles (not enriched in 180+ days)
- Source: DB query on `crawled_profile.enriched_at` timestamp

**Graceful degradation:**
- If a data source is empty or missing, skip that section with a brief note (e.g., "No query history yet — start with /linkedout")
- Never error out on missing data; always produce whatever sections are possible

**Output formatting:**
- Use formatters for tables, stat lines, percentages
- Plain text, no ANSI
- Support `--json` equivalent: if user asks for JSON output, produce structured JSON instead of tables

### 2. Generated Skill: `skills/claude-code/linkedout-report/SKILL.md` (NEW or UPDATE)

Claude Code-specific skill that:
- Reads `~/linkedout-data/config/agent-context.env` for DB URL and data dir
- Uses `Read` tool for JSONL file parsing
- Uses `Bash` tool for `psql` queries (via DB URL from agent-context.env) for network stats and profile freshness
- Uses `Bash` tool to run `linkedout status --json` for quick stats
- Formats output using the formatting conventions from `formatters.py`

### 3. CLAUDE.md Routing Update

Register `/linkedout-report` in the routing system (if Phase 8 routing exists).

## Verification
After completing all deliverables:
1. Verify skill template has correct frontmatter and all 6 report sections documented
2. Verify graceful degradation instructions for each section
3. Test manually:
   - Create sample JSONL query and metrics data
   - Verify each section renders correctly with sample data
   - Verify sections are skipped gracefully when data is missing
   - Verify JSON output mode works
