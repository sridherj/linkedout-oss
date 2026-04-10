# Sub-Phase 6: Pipeline News Path + CLI (Stages 5-7)

**Goal:** linkedin-ai-production
**Phase:** 2b — Startup Pipeline Compatibility
**Depends on:** SP-4 (DB Layer Updates — shared DB layer must be migrated first)
**Estimated effort:** 3h
**Source plan steps:** Steps 7 (7a-7c), 8
**Parallel with:** SP-5 (Discovery Path), SP-7 (Agent Updates)

---

## Objective

Update pipeline stages 5-7 (the news processing path) and the enrichment CLI to use LinkedOut schema — singular table names, nanoid PKs, and the updated DB layer from SP-4.

## Context

**Working directory:** `<prior-project>/agents/pipeline/`

These stages form the news path:
5. `news/collect_news.py` — Collect news articles → `news_article`
6. `news/enrich_news.py` — LLM enrichment → updates `news_article`
7. `news/link_companies.py` — Link companies → `news_company_mention`

Plus the CLI wrapper: `enrichment/helpers.py`

---

## Tasks

### 7a: `news/collect_news.py` (Stage 5)
- Update `INSERT INTO news_articles` → `INSERT INTO news_article`
- Generate `na_xxx` nanoid for each article
- Update `raw_feed_items` JOIN → `raw_feed_item`
- Update embedding cosine similarity query (table name change)

### 7b: `news/enrich_news.py` (Stage 6)
- Update `UPDATE news_articles` → `UPDATE news_article`
- Update `INSERT INTO pipeline_failed_items` → `INSERT INTO pipeline_failed_item`
- Generate `pfi_xxx` nanoid for failed items
- Update WHERE clauses on `news_articles.id` → `news_article.id`

### 7c: `news/link_companies.py` (Stage 7)
- Update `INSERT INTO news_company_mentions` → `INSERT INTO news_company_mention`
- Generate `ncm_xxx` nanoid
- Update `companies` → `company` in matcher data loading
- Update `article_id` and `company_id` type handling (TEXT nanoids)
- Update calls to `company_ops.insert_or_match_company()` (returns `str`)

### Step 8: `enrichment/helpers.py` CLI
- Update `--company-id` argparse from `type=int` to `type=str`
- Update any ID formatting/display code
- Verify all commands work: `uv run python -m agents.pipeline.enrichment.helpers --help`

---

## Completion Criteria

- [ ] All `news/*.py` files reference singular table names
- [ ] All new rows use nanoid PKs
- [ ] Failed items written to `pipeline_failed_item` with `pfi_xxx` IDs
- [ ] `--company-id` accepts string nanoid values (e.g., `co_xxx`)
- [ ] All `insert_or_match_company()` calls handle `str` return type

## Verification

```bash
# Run stages 5-7 with test data in raw_feed_item
psql -d linkedout -c "SELECT id FROM news_article LIMIT 3"           # na_xxx format
psql -d linkedout -c "SELECT id FROM news_company_mention LIMIT 3"   # ncm_xxx format

# CLI check
uv run python -m agents.pipeline.enrichment.helpers --help
# --company-id should accept strings
```
