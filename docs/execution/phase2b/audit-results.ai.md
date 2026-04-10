# Phase 2b — Pipeline SQL Audit Results

**Generated:** 2026-03-27
**Scope:** All `.py` files in `<prior-project>/agents/pipeline/` + `agents/shared/db.py`
**Total files scanned:** 45 (14 source files with SQL, 17 source files without SQL, 14 test files)

---

## Summary

- **14 files** contain direct SQL queries
- **39 unique SQL statements** identified
- **10 tables** referenced (+ 1 materialized view + 1 system catalog)
- **2 `get_connection()` implementations** (pipeline/db.py and shared/db.py) — both default to `linkedin_intel` database

---

## SQL Audit Table

### `agents/pipeline/db.py` — Core DB layer

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 47-54 | INSERT | `raw_feed_items` | gmail_message_id, email_received_at, source_feed, feed_category, title, summary, source_url, raw_url, published_at, id | `upsert_raw_items()` — ON CONFLICT (gmail_message_id, source_url) DO NOTHING, RETURNING id |
| 87-97 | UPDATE | `pipeline_state` | run_emails_processed, run_items_parsed, run_items_extracted, run_companies_found, run_noise_flagged, run_promoted, run_errors, pipeline_name | `reset_run_counters()` — zeros run_* counters |
| 107-118 | UPDATE | `pipeline_state` | total_emails_processed, total_items_parsed, total_items_extracted, total_companies_found, total_noise_flagged, total_promoted, total_errors, run_* (all), pipeline_name | `finalize_run_counters()` — adds run_* to total_* |
| 156 | UPDATE | `pipeline_state` | Dynamic columns from `_PIPELINE_STATE_COLUMNS` set: last_run_started_at, last_run_completed_at, last_successful_run_at, status, error_message, last_gmail_history_id, metadata, run_* counters | `update_pipeline_state()` — dynamic SET clause |
| 169-177 | SELECT | `companies`, `funding_rounds` | c.id, c.canonical_name, c.normalized_name, c.website, c.description, c.vertical, fr.id (LEFT JOIN) | `get_unenriched_companies()` — WHERE c.watching=true AND fr.id IS NULL |
| 186-190 | SELECT | `companies` | id, canonical_name, normalized_name, website, description, vertical | `get_companies_by_names()` — WHERE normalized_name = ANY(%s) |
| 197-201 | SELECT | `funding_rounds` | id, round_type, amount_usd, announced_on, lead_investors, source, confidence | `get_existing_rounds()` — WHERE company_id = %s |
| 209-223 | SELECT | `growth_signals` | id, signal_type, signal_date, value_numeric, value_text, source, source_url, confidence | `get_existing_signals()` — WHERE company_id = %s, optional signal_type filter |
| 245-248 | UPDATE | `companies` | Dynamic columns from `_ALLOWED_COMPANY_METADATA_COLUMNS`: vertical, hq_city, hq_country, founded_year, estimated_employee_count, website, description, estimated_arr_usd, arr_signal_date, arr_confidence | `update_company_metadata()` — WHERE id = %s |
| 255 | REFRESH MATERIALIZED VIEW | `company_growth_metrics` | (all) | `refresh_growth_metrics()` — CONCURRENTLY |
| 262-268 | SELECT | `funding_rounds`, `companies` | fr.company_id (COUNT DISTINCT), companies.watching (subquery COUNT) | `enrichment_report()` — coverage stats |
| 272-275 | SELECT | `funding_rounds` | confidence (GROUP BY, COUNT) | `enrichment_report()` — confidence distribution |
| 279-284 | SELECT | `companies` | estimated_arr_usd, watching (COUNT FILTER) | `enrichment_report()` — revenue coverage |
| 287-290 | SELECT | `growth_signals` | signal_type (GROUP BY, COUNT) | `enrichment_report()` — signal distribution |

### `agents/pipeline/company_ops.py` — Company & funding CRUD

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 33-35 | SELECT | `companies` | id | `insert_or_match_company()` — WHERE normalized_name = %s LIMIT 1 |
| 39 | UPDATE | `companies` | watching | `insert_or_match_company()` — SET watching = true WHERE id = %s |
| 43-49 | INSERT | `companies` | canonical_name, normalized_name, website, description, watching, vertical, id | `insert_or_match_company()` — ON CONFLICT (canonical_name) DO UPDATE SET watching=true, RETURNING id |
| 70-75 | SELECT | `funding_rounds` | id, confidence | `insert_funding_round()` — dedup check: WHERE company_id, round_type, amount_usd IS NOT DISTINCT FROM |
| 81-92 | UPDATE | `funding_rounds` | lead_investors, announced_on, all_investors, source_url, notes, source, confidence | `insert_funding_round()` — conditional update when new confidence > existing |
| 96-107 | INSERT | `funding_rounds` | company_id, round_type, amount_usd, lead_investors, source, confidence, announced_on, all_investors, source_url, notes | `insert_funding_round()` — ON CONFLICT DO NOTHING, RETURNING id |
| 125-138 | INSERT | `growth_signals` | company_id, signal_type, signal_date, value_numeric, value_text, source, source_url, confidence | `insert_growth_signal()` — ON CONFLICT (company_id, signal_type, signal_date, source) DO UPDATE with confidence check |

### `agents/pipeline/run.py` — Orchestrator

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 198-201 | SELECT | `raw_feed_items` | id, title, summary, source_url, source_feed, feed_category | Stage 2 inline query — WHERE extracted_at IS NULL |

### `agents/pipeline/extract.py` — Stage 2: LLM extraction

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 183-185 | UPDATE | `raw_feed_items` | extracted_at, is_noise | `_store_extraction()` — SET extracted_at=NOW(), is_noise=%s WHERE id=%s |
| 195-218 | INSERT | `extracted_companies` | raw_item_id, company_name, normalized_name, description_snippet, website_url, role_in_item, has_funding_event, amount_usd, round_type, announced_on, lead_investors, all_investors, confidence, is_ai_startup, source | `_store_extraction()` — ON CONFLICT (raw_item_id, normalized_name) DO NOTHING |
| 247-264 | INSERT | `pipeline_failed_items` | raw_item_id, stage, error_type, error_message, stack_trace, item_data | `_store_failure()` — cast item_data as jsonb |

### `agents/pipeline/dedup.py` — Stage 3: Deduplication

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 34-42 | SELECT | `extracted_companies` | id, company_name, normalized_name, confidence, description_snippet, website_url, is_ai_startup, has_funding_event, amount_usd, round_type, lead_investors, raw_item_id | `deduplicate_extractions()` — WHERE dedup_status='pending' AND role_in_item='primary' |
| 85-90 | UPDATE | `extracted_companies` | dedup_status, matched_company_id, dedup_method, dedup_score, dedup_run_at | `_update_dedup_status()` — WHERE id=%s |
| 106 | SELECT | `raw_feed_items` | source_feed | `_upsert_discovery_signal()` — WHERE id=%s (get source_feed) |
| 126-163 | INSERT | `discovery_signals` | normalized_name, canonical_name, signal_count, source_feeds, best_description, best_website_url, best_confidence, is_ai_startup, has_funding_event, amount_usd, round_type, lead_investors, sample_raw_item_ids, last_seen_at | `_upsert_discovery_signal()` — ON CONFLICT (normalized_name) DO UPDATE with complex merge logic |

### `agents/pipeline/promote.py` — Stage 4: Promote

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 35-44 | SELECT | `discovery_signals` | id, normalized_name, canonical_name, best_description, best_website_url, is_ai_startup, has_funding_event, amount_usd, round_type, lead_investors | `promote_candidates()` — WHERE promotion_status='candidate' AND signal_count>=3 AND best_confidence>=8 |
| 83-88 | UPDATE | `discovery_signals` | promotion_status | `promote_candidates()` — SET promotion_status='review' WHERE candidate AND signal_count>=2 |
| 93-103 | UPDATE | `companies` | watching | `promote_candidates()` — SET watching=true for matched companies |
| 108-116 | SELECT | `extracted_companies` | matched_company_id, amount_usd, round_type, lead_investors | `promote_candidates()` — WHERE dedup_status='matched' AND has_funding_event=true |
| 143-149 | UPDATE | `discovery_signals` | promotion_status, promoted_company_id, reviewed_by, reviewed_at | `_update_signal_promoted()` — SET promoted, company_id, reviewed_by, NOW() |

### `agents/pipeline/company_matcher.py` — 3-layer matching

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 58 | SELECT | `companies` | id, normalized_name | `_load_company_names()` — WHERE normalized_name IS NOT NULL |
| 71-73 | SELECT | `information_schema.tables` | table_name | `_load_aliases()` — checks company_aliases table existence |
| 78 | SELECT | `company_aliases` | alias_name, company_id | `_load_aliases()` — loads all aliases |
| 89 | SELECT | `pg_extension` | extname | `_check_pg_trgm()` — checks pg_trgm extension |
| 96-102 | SELECT | `companies` | id, normalized_name (via similarity()) | `_fuzzy_match_db()` — pg_trgm similarity match, score > 0.7 |

### `agents/pipeline/news/collect_news.py` — Stage 5: News collect

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 40-48 | SELECT | `raw_feed_items`, `news_articles` | r.id, r.title, r.summary, r.source_url, r.raw_url, r.source_feed, r.feed_category, r.published_at, na.id (LEFT JOIN) | `_fetch_unprocessed_items()` — WHERE na.id IS NULL AND r.is_noise=false |
| 90-95 | SELECT | `news_articles` | id, embedding | Semantic dedup — WHERE embedding <=> vector < threshold AND published_at > NOW()-7days |
| 102-117 | INSERT | `news_articles` | raw_item_id, url, title, summary, source_feed, feed_category, published_at, embedding | `collect_news()` — ON CONFLICT (url) DO NOTHING, RETURNING id |

### `agents/pipeline/news/enrich_news.py` — Stage 6: News enrich

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 42-44 | SELECT | `news_articles` | id, title, summary, url | `_fetch_unenriched()` — WHERE enriched_at IS NULL |
| 97-105 | UPDATE | `news_articles` | event_type, sentiment, key_facts, extracted_amount, mentions_json, enriched_at | `_update_article()` — SET enriched_at=NOW() WHERE id=%s |
| 120-136 | INSERT | `pipeline_failed_items` | raw_item_id, stage, error_type, error_message, stack_trace, item_data | `_store_failure()` — cast item_data as jsonb |

### `agents/pipeline/news/link_companies.py` — Stage 7: Link companies

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 53-58 | INSERT | `news_company_mentions` | article_id, company_id, relevance, confidence, mention_context | `_insert_mention()` — ON CONFLICT (article_id, company_id) DO UPDATE SET relevance |
| 66-73 | SELECT | `news_articles`, `news_company_mentions` | na.id, na.mentions_json, na.event_type, na.extracted_amount, ncm.id (LEFT JOIN) | `_load_enrichment_from_db()` — WHERE enriched_at IS NOT NULL AND mentions_json IS NOT NULL AND ncm.id IS NULL |

### `agents/pipeline/ats_cache.py` — ATS slug cache

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 23-24 | SELECT | `companies` | ats_platform, ats_slug, ats_last_checked | `get_ats_cache()` — WHERE id=%s |
| 46-48 | UPDATE | `companies` | ats_platform, ats_slug, ats_last_checked | `update_ats_cache()` — WHERE id=%s |
| 67-69 | UPDATE | `companies` | ats_platform, ats_slug, ats_last_checked | `bulk_update_ats_cache()` — WHERE id=%s (loop) |

### `agents/shared/db.py` — Shared DB layer (used by non-pipeline agents)

| Line | Operation | Table(s) | Columns | Function / Notes |
|------|-----------|----------|---------|------------------|
| 41-44 | INSERT | `companies` | canonical_name, normalized_name, website, watching, id | `add_company()` — RETURNING id |
| 55-57 | SELECT | `companies` | canonical_name (WHERE) | `company_exists()` — WHERE canonical_name=%s LIMIT 1 |
| 68-69 | SELECT | `companies` | * (all columns), normalized_name (WHERE) | `find_by_normalized_name()` — WHERE normalized_name=%s |

---

## Files With No Direct SQL

| File | Reason |
|------|--------|
| `collect.py` | Gmail API only, no DB access (returns dicts for `run.py` to INSERT via `db.upsert_raw_items`) |
| `converters.py` | Pure functions (name normalization, date parsing, amount parsing) |
| `schemas.py` | Pydantic models only |
| `news/schemas.py` | Pydantic models only |
| `enrichment/helpers.py` | CLI wrapper — calls `db.py` and `company_ops.py` functions, no direct SQL |
| `opportunity_finder.py` | HTTP API calls to ATS platforms — DB access via `ats_cache.py` and `db.get_connection()` |
| `gmail_auth.py` | Gmail OAuth only |
| `__init__.py` | Empty |
| `__main__.py` | CLI entry point |
| All `tests/*.py` files (14) | Test files — may contain SQL in fixtures but not production code |

---

## Table Reference Summary

| Table | Operations | Referenced In |
|-------|-----------|---------------|
| `companies` | SELECT, INSERT, UPDATE | db.py, company_ops.py, company_matcher.py, promote.py, ats_cache.py, shared/db.py |
| `funding_rounds` | SELECT, INSERT, UPDATE | db.py, company_ops.py |
| `growth_signals` | SELECT, INSERT | db.py, company_ops.py |
| `raw_feed_items` | SELECT, INSERT, UPDATE | db.py, run.py, extract.py, dedup.py, collect_news.py |
| `extracted_companies` | SELECT, INSERT, UPDATE | extract.py, dedup.py, promote.py |
| `discovery_signals` | SELECT, INSERT, UPDATE | dedup.py, promote.py |
| `pipeline_state` | UPDATE | db.py (reset/finalize/update) |
| `pipeline_failed_items` | INSERT | extract.py, enrich_news.py |
| `news_articles` | SELECT, INSERT, UPDATE | collect_news.py, enrich_news.py, link_companies.py |
| `news_company_mentions` | SELECT (LEFT JOIN), INSERT | link_companies.py |
| `company_aliases` | SELECT | company_matcher.py |
| `company_growth_metrics` | REFRESH MATERIALIZED VIEW | db.py |

### System Catalog / Extension References

| Table/Object | Operation | File |
|--------------|-----------|------|
| `information_schema.tables` | SELECT | company_matcher.py (check company_aliases existence) |
| `pg_extension` | SELECT | company_matcher.py (check pg_trgm) |
| `pg_trgm` similarity() | Function call | company_matcher.py (fuzzy matching) |
| `pgvector` <=> operator | Operator | collect_news.py (semantic dedup via vector cosine distance) |

---

## Column Inventory by Table

### `companies`
id, canonical_name, normalized_name, website, description, vertical, watching, hq_city, hq_country, founded_year, estimated_employee_count, estimated_arr_usd, arr_signal_date, arr_confidence, ats_platform, ats_slug, ats_last_checked

### `funding_rounds`
id, company_id, round_type, amount_usd, announced_on, lead_investors, all_investors, source, confidence, source_url, notes

### `growth_signals`
id, company_id, signal_type, signal_date, value_numeric, value_text, source, source_url, confidence

### `raw_feed_items`
id, gmail_message_id, email_received_at, source_feed, feed_category, title, summary, source_url, raw_url, published_at, extracted_at, is_noise

### `extracted_companies`
id, raw_item_id, company_name, normalized_name, description_snippet, website_url, role_in_item, has_funding_event, amount_usd, round_type, announced_on, lead_investors, all_investors, confidence, is_ai_startup, source, dedup_status, matched_company_id, dedup_method, dedup_score, dedup_run_at

### `discovery_signals`
id, normalized_name, canonical_name, signal_count, source_feeds, best_description, best_website_url, best_confidence, is_ai_startup, has_funding_event, amount_usd, round_type, lead_investors, sample_raw_item_ids, last_seen_at, promotion_status, promoted_company_id, reviewed_by, reviewed_at

### `pipeline_state`
pipeline_name, run_emails_processed, run_items_parsed, run_items_extracted, run_companies_found, run_noise_flagged, run_promoted, run_errors, total_emails_processed, total_items_parsed, total_items_extracted, total_companies_found, total_noise_flagged, total_promoted, total_errors, last_run_started_at, last_run_completed_at, last_successful_run_at, status, error_message, last_gmail_history_id, metadata

### `pipeline_failed_items`
id (implied), raw_item_id, stage, error_type, error_message, stack_trace, item_data

### `news_articles`
id, raw_item_id, url, title, summary, source_feed, feed_category, published_at, embedding, enriched_at, event_type, sentiment, key_facts, extracted_amount, mentions_json

### `news_company_mentions`
id, article_id, company_id, relevance, confidence, mention_context

### `company_aliases`
alias_name, company_id

### `company_growth_metrics` (materialized view)
(columns not directly referenced — only REFRESH MATERIALIZED VIEW CONCURRENTLY)

---

## Connection Configuration

Both `agents/pipeline/db.py:get_connection()` (line 17) and `agents/shared/db.py:get_connection()` (line 17) use the same pattern:
1. `LINKEDIN_INTEL_DSN` env var (preferred)
2. `DATABASE_URL` env var (fallback)
3. Individual `PG*` env vars with defaults: host=localhost, port=5432, **dbname=linkedin_intel**, user=sj

**Migration action:** These must be updated to connect to the LinkedOut PostgreSQL database instead.

---

## Key Observations for Migration

1. **Two `get_connection()` functions** need updating (pipeline/db.py + shared/db.py)
2. **`companies` table is the most heavily referenced** — 6 files, all CRUD operations
3. **`pgvector` extension required** for news_articles.embedding column (cosine distance operator `<=>`)
4. **`pg_trgm` extension required** for fuzzy company matching
5. **ON CONFLICT clauses define unique constraints** that must be preserved in Alembic migration
6. **`pipeline_state` uses dynamic column updates** — column whitelist in `_PIPELINE_STATE_COLUMNS`
7. **`company_growth_metrics` is a materialized view** that needs to be created/migrated
8. **No `CREATE TABLE` or `ALTER TABLE` statements** in pipeline code — schema is managed externally
9. **`enrichment/helpers.py`** has no direct SQL — it delegates to `db.py` and `company_ops.py`
10. **`ats_cache.py`** reads/writes ATS columns directly on the `companies` table (not a separate table)
