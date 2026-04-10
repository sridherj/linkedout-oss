# Sub-Phase 3: Alembic Migration + Nanoid Utility

**Goal:** linkedin-ai-production
**Phase:** 2b — Startup Pipeline Compatibility
**Depends on:** SP-2 (CRUD Entities — for entity imports in Alembic env)
**Estimated effort:** 2.5-3.5h
**Source plan steps:** Steps 3, 4

---

## Objective

Create a single Alembic migration with 7 pipeline infrastructure tables (raw SQL, no CRUD entities) and add a nanoid generation utility to the pipeline code.

---

## Part A: Alembic Migration (Step 3)

Write a single Alembic migration file with all 7 tables. These are infra tables used by the pipeline — they get nanoid PKs but no Entity/Repo/Service/Controller stack.

### Pre-requisites

Start the migration with extension setup:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

Include a PostgreSQL function for nanoid generation that the pipeline can use as DEFAULT:
```sql
-- nanoid generation function for pipeline use
CREATE OR REPLACE FUNCTION generate_nanoid(prefix TEXT, size INT DEFAULT 12)
RETURNS TEXT AS $$
DECLARE
    alphabet TEXT := 'abcdefghijklmnopqrstuvwxyz0123456789';
    result TEXT := '';
    i INT;
BEGIN
    FOR i IN 1..size LOOP
        result := result || substr(alphabet, floor(random() * length(alphabet) + 1)::int, 1);
    END LOOP;
    RETURN prefix || '_' || result;
END;
$$ LANGUAGE plpgsql;
```

### Tables to Create

**3a. `pipeline_state`** (prefix: `ps`)

```sql
CREATE TABLE pipeline_state (
    id              TEXT PRIMARY KEY DEFAULT generate_nanoid('ps'),
    pipeline_name   TEXT NOT NULL UNIQUE,
    last_run_started_at     TIMESTAMPTZ,
    last_run_completed_at   TIMESTAMPTZ,
    last_successful_run_at  TIMESTAMPTZ,
    status          TEXT DEFAULT 'idle'
        CHECK (status IN ('idle', 'running', 'success', 'failed')),
    error_message   TEXT,
    last_gmail_history_id   TEXT,
    total_emails_processed  INTEGER DEFAULT 0,
    total_items_parsed      INTEGER DEFAULT 0,
    total_items_extracted   INTEGER DEFAULT 0,
    total_companies_found   INTEGER DEFAULT 0,
    total_noise_flagged     INTEGER DEFAULT 0,
    total_promoted          INTEGER DEFAULT 0,
    total_errors            INTEGER DEFAULT 0,
    run_emails_processed    INTEGER DEFAULT 0,
    run_items_parsed        INTEGER DEFAULT 0,
    run_items_extracted     INTEGER DEFAULT 0,
    run_companies_found     INTEGER DEFAULT 0,
    run_noise_flagged       INTEGER DEFAULT 0,
    run_promoted            INTEGER DEFAULT 0,
    run_errors              INTEGER DEFAULT 0,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**3b. `raw_feed_item`** (prefix: `rfi`)

```sql
CREATE TABLE raw_feed_item (
    id                  TEXT PRIMARY KEY DEFAULT generate_nanoid('rfi'),
    gmail_message_id    TEXT NOT NULL,
    email_received_at   TIMESTAMPTZ,
    source_feed         TEXT NOT NULL,
    feed_category       TEXT,
    title               TEXT NOT NULL,
    summary             TEXT,
    source_url          TEXT NOT NULL,
    raw_url             TEXT,
    published_at        TIMESTAMPTZ,
    extracted_at        TIMESTAMPTZ,
    is_noise            BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (gmail_message_id, source_url)
);
```

**3c. `extracted_company`** (prefix: `ec`)

```sql
CREATE TABLE extracted_company (
    id                  TEXT PRIMARY KEY DEFAULT generate_nanoid('ec'),
    raw_item_id         TEXT NOT NULL REFERENCES raw_feed_item(id) ON DELETE CASCADE,
    company_name        TEXT NOT NULL,
    normalized_name     TEXT,
    description_snippet TEXT,
    website_url         TEXT,
    role_in_item        TEXT DEFAULT 'primary',
    has_funding_event   BOOLEAN DEFAULT FALSE,
    amount_usd          BIGINT,
    round_type          TEXT,
    announced_on        DATE,
    lead_investors      TEXT[],
    all_investors       TEXT[],
    confidence          SMALLINT DEFAULT 5,
    is_ai_startup       BOOLEAN,
    dedup_status        TEXT DEFAULT 'pending',
    matched_company_id  TEXT,
    dedup_method        TEXT,
    dedup_score         NUMERIC(4,3),
    dedup_run_at        TIMESTAMPTZ,
    source              TEXT DEFAULT 'rss_pipeline',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (raw_item_id, normalized_name)
);
```

**3d. `discovery_signal`** (prefix: `ds`)

```sql
CREATE TABLE discovery_signal (
    id                  TEXT PRIMARY KEY DEFAULT generate_nanoid('ds'),
    normalized_name     TEXT NOT NULL UNIQUE,
    canonical_name      TEXT,
    signal_count        INTEGER DEFAULT 1,
    source_feeds        TEXT[],
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    best_description    TEXT,
    best_website_url    TEXT,
    best_confidence     SMALLINT DEFAULT 5,
    is_ai_startup       BOOLEAN,
    sample_raw_item_ids TEXT[],
    has_funding_event   BOOLEAN DEFAULT FALSE,
    amount_usd          BIGINT,
    round_type          TEXT,
    lead_investors      TEXT[],
    promotion_status    TEXT DEFAULT 'candidate',
    promoted_company_id TEXT,
    reviewed_by         TEXT,
    reviewed_at         TIMESTAMPTZ,
    rejection_reason    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**3e. `pipeline_failed_item`** (prefix: `pfi`)

```sql
CREATE TABLE pipeline_failed_item (
    id              TEXT PRIMARY KEY DEFAULT generate_nanoid('pfi'),
    raw_item_id     TEXT REFERENCES raw_feed_item(id) ON DELETE SET NULL,
    stage           TEXT NOT NULL,
    error_type      TEXT,
    error_message   TEXT NOT NULL,
    stack_trace     TEXT,
    item_data       JSONB,
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    next_retry_at   TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    pipeline_name   TEXT DEFAULT 'startup_discovery',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**3f. `news_article`** (prefix: `na`)

```sql
CREATE TABLE news_article (
    id              TEXT PRIMARY KEY DEFAULT generate_nanoid('na'),
    raw_item_id     TEXT REFERENCES raw_feed_item(id) ON DELETE SET NULL,
    url             TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    summary         TEXT,
    source_feed     TEXT,
    feed_category   TEXT,
    published_at    TIMESTAMPTZ,
    collected_at    TIMESTAMPTZ DEFAULT NOW(),
    enriched_at     TIMESTAMPTZ,
    event_type      TEXT CHECK (event_type IN ('funding', 'acquisition', 'launch', 'hiring', 'partnership', 'other')),
    sentiment       TEXT CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    key_facts       TEXT[],
    extracted_amount TEXT,
    mentions_json   JSONB,
    search_vector   tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, ''))) STORED,
    embedding       vector(1536),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_news_search_vector ON news_article USING GIN (search_vector);
CREATE INDEX idx_news_embedding ON news_article USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_news_published_at ON news_article (published_at DESC);
CREATE INDEX idx_news_unenriched ON news_article (id) WHERE enriched_at IS NULL;
CREATE INDEX idx_news_event_type ON news_article (event_type) WHERE event_type IS NOT NULL;
```

**3g. `news_company_mention`** (prefix: `ncm`)

```sql
CREATE TABLE news_company_mention (
    id              TEXT PRIMARY KEY DEFAULT generate_nanoid('ncm'),
    article_id      TEXT NOT NULL REFERENCES news_article(id) ON DELETE CASCADE,
    company_id      TEXT NOT NULL REFERENCES company(id),
    relevance       TEXT DEFAULT 'mentioned'
        CHECK (relevance IN ('primary', 'mentioned', 'competitor', 'investor')),
    confidence      SMALLINT DEFAULT 5 CHECK (confidence BETWEEN 1 AND 10),
    mention_context TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (article_id, company_id)
);

CREATE INDEX idx_news_mentions_company ON news_company_mention (company_id);
CREATE INDEX idx_news_mentions_article ON news_company_mention (article_id);
```

### Additional Pipeline Query Indexes

```sql
-- raw_feed_item: Stage 2 extraction watermark query
CREATE INDEX idx_rfi_unextracted ON raw_feed_item (id) WHERE extracted_at IS NULL;

-- extracted_company: Stage 3 dedup pending query
CREATE INDEX idx_ec_dedup_pending ON extracted_company (dedup_status, role_in_item);

-- discovery_signal: Stage 4 promotion candidate query
CREATE INDEX idx_ds_promotion ON discovery_signal (signal_count, best_confidence)
    WHERE promotion_status = 'candidate';
```

---

## Part B: Nanoid Utility (Step 4)

Add to `<prior-project>/agents/pipeline/db.py`:

```python
import string, secrets

NANOID_ALPHABET = string.ascii_lowercase + string.digits
NANOID_SIZE = 12

def generate_nanoid(prefix: str) -> str:
    """Generate a prefixed nanoid matching LinkedOut's BaseEntity format."""
    nid = ''.join(secrets.choice(NANOID_ALPHABET) for _ in range(NANOID_SIZE))
    return f"{prefix}_{nid}"

ENTITY_PREFIXES = {
    'company': 'co',
    'funding_round': 'fr',
    'growth_signal': 'gs',
    'startup_tracking': 'st',
    'pipeline_state': 'ps',
    'raw_feed_item': 'rfi',
    'extracted_company': 'ec',
    'discovery_signal': 'ds',
    'pipeline_failed_item': 'pfi',
    'news_article': 'na',
    'news_company_mention': 'ncm',
}
```

---

## Completion Criteria

- [ ] `alembic upgrade head` succeeds
- [ ] All 7 tables exist: `\dt pipeline_state raw_feed_item extracted_company discovery_signal pipeline_failed_item news_article news_company_mention`
- [ ] Nanoid PKs generated correctly on test inserts
- [ ] FK constraints work (insert into `news_company_mention` with invalid `company_id` fails)
- [ ] `generate_nanoid('co')` returns strings like `co_a1b2c3d4e5f6`
- [ ] Prefix map matches LinkedOut entity prefixes
- [ ] pgvector and pg_trgm extensions confirmed active

## Verification

```bash
alembic upgrade head
psql -d linkedout -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('pipeline_state', 'raw_feed_item', 'extracted_company', 'discovery_signal', 'pipeline_failed_item', 'news_article', 'news_company_mention')"
# Should return 7
```
