# Sub-Phase 1: Pipeline Code Audit

**Goal:** linkedin-ai-production
**Phase:** 2b — Startup Pipeline Compatibility
**Depends on:** Nothing (first sub-phase)
**Estimated effort:** 30 min
**Source plan steps:** Step 1

---

## Objective

Identify every SQL query, table reference, and column reference across all pipeline files. This audit produces the migration checklist that all subsequent sub-phases depend on.

## Context

The pipeline code lives at `<prior-project>/agents/pipeline/`. Three agents (`startup-pipeline`, `startup-enrich`, `startup-discover`) share this DB layer. The pipeline currently targets the lost `linkedin_intel` database and needs to be migrated to write to the LinkedOut PostgreSQL database instead.

## Files to Audit

| File | Purpose | Known SQL? |
|------|---------|------------|
| `db.py` | Core DB layer | Yes — 10 queries (analyzed) |
| `company_ops.py` | Company CRUD | Yes — 5 queries (analyzed) |
| `enrichment/helpers.py` | CLI wrapper | No direct SQL (analyzed) |
| `run.py` | Orchestrator | Likely calls REFRESH MATERIALIZED VIEW |
| `collect.py` | Stage 1: RSS collection | Likely INSERT into raw_feed_items |
| `extract.py` | Stage 2: Company extraction | Likely INSERT into extracted_companies |
| `dedup.py` | Stage 3: Deduplication | Likely UPDATE extracted_companies |
| `promote.py` | Stage 4: Promote to companies | Likely INSERT into companies, discovery_signals |
| `company_matcher.py` | 3-layer matching | Likely SELECT from companies, company aliases |
| `converters.py` | Name normalization | Likely no SQL |
| `news/collect_news.py` | Stage 5: Collect news | INSERT into news_articles |
| `news/enrich_news.py` | Stage 6: LLM enrichment | UPDATE news_articles |
| `news/link_companies.py` | Stage 7: Link companies | INSERT into news_company_mentions |
| `news/schemas.py` | Pydantic models | No SQL |

## Tasks

1. **Scan every `.py` file** in `<prior-project>/agents/pipeline/` (including subdirectories)
2. **For each SQL query found**, record:
   - File path and line number
   - SQL operation (SELECT, INSERT, UPDATE, DELETE, CREATE, etc.)
   - Tables referenced
   - Columns referenced
   - Any dynamic table/column references
3. **Check for `REFRESH MATERIALIZED VIEW`** calls (expected in `run.py`)
4. **Check `agents/shared/db.py`** for any functions used by the pipeline (startup-discover may import from here instead of `agents/pipeline/db.py`)
5. **Produce the audit table** as a markdown file

## Deliverable

Write the audit to: `docs/execution/phase2b/audit-results.ai.md`

Format:
```markdown
| File | Line | Operation | Table(s) | Columns | Notes |
|------|------|-----------|----------|---------|-------|
| db.py | 45 | SELECT | companies | id, name, watching | get_unenriched_companies |
```

## Completion Criteria

- [ ] Every pipeline `.py` file has been scanned (not just the 3 known files)
- [ ] No table or column reference is missing from the checklist
- [ ] `agents/shared/db.py` checked for pipeline usage
- [ ] REFRESH MATERIALIZED VIEW calls documented
- [ ] Audit table written to `docs/execution/phase2b/audit-results.ai.md`

## Verification

```bash
# Confirm all pipeline .py files were checked
find <prior-project>/agents/pipeline/ -name "*.py" | wc -l
# Compare against number of files in audit
```
