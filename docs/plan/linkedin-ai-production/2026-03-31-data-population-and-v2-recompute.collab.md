# Data Population & V2 Affinity Recompute

## Overview

Code for all 3 phases (Classify Roles, Company Enrichment, Affinity V2) is deployed. But only Phase 1 data is populated — companies have 0% enrichment coverage, contact_source has 0 rows, and affinity scores are still V1. This plan runs the data population commands and recomputes V2 scores.

## Pre-Conditions

- Phase 1 complete: role_alias (62,717), experience seniority (105,287), V1 affinity (28,004)
- Phase 2 code complete: `enrich_companies.py` with PDL+Wikidata waterfall, CLI wired
- Phase 3 code complete: V2 scorer with 5 signals, `load_gmail_contacts.py` updated to write `contact_source` rows
- Bug fix applied: `load_gmail_contacts.py` now writes `contact_source` rows with correct `source_type` mapping to `EXTERNAL_SOURCE_TYPES`

## Steps

### Step 1: Enrich Companies via PDL

Populate company metadata (industry, website, domain, founded_year, hq, employee_count, size_tier) from the PDL CSV.

```bash
cd .
uv run rcv2 db enrich-companies --pdl-file <prior-project>/data/pdl/companies.csv
```

**Expected outcome:** Companies gain industry/website/employee_count/size_tier coverage. `pdl_id` populated for matched companies. This directly feeds `size_factor()` in career overlap — without employee_count, all companies default to 500.

**Verification:**
```sql
SELECT COUNT(*) FILTER (WHERE pdl_id IS NOT NULL) as with_pdl,
       COUNT(*) FILTER (WHERE industry IS NOT NULL) as with_industry,
       COUNT(*) FILTER (WHERE estimated_employee_count IS NOT NULL) as with_emp_count,
       COUNT(*) FILTER (WHERE size_tier IS NOT NULL) as with_size_tier,
       COUNT(*) as total
FROM company;
```

**Risk:** PDL CSV is 33M rows — scan may take several minutes. The script uses `csv.DictReader` with streaming, so memory should be OK.

### Step 2: Load Gmail Contacts

Import all 3 contact sources into `contact_source` table, matching against existing connections.

```bash
cd .
uv run rcv2 db load-gmail-contacts --gmail-dir <prior-project>/agents/taskos-linkedin-ai/gmail_contacts/
```

**Files loaded:**
| File | source_type | source_label | Records |
|------|------------|-------------|---------|
| contacts_from_google_job.csv | google_contacts_job | google_work | ~177 |
| contacts_with_phone.csv | contacts_phone | google_personal | ~1,465 |
| gmail_contacts_email_id_only.csv | gmail_email_only | google_personal | ~2,186 |

**Expected outcome:** ~3,808 deduped contacts parsed. Matched contacts get `contact_source` rows with `dedup_status='matched'` and `connection_id` set. New contacts create stub profiles + connections + `contact_source` rows. ImportJob created for tracking.

**Verification:**
```sql
SELECT source_type, dedup_status, COUNT(*)
FROM contact_source
GROUP BY 1, 2 ORDER BY 1, 2;
```

**Idempotent:** Script deletes prior gmail contact_source rows before inserting.

### Step 3: Recompute Affinity with V2 Formula

Recompute all connection scores using the 5-signal V2 formula.

```bash
cd .
uv run rcv2 db compute-affinity
```

**Expected outcome:** All 28K+ connections rescored with V2 weights (career_overlap=0.40, external_contact=0.25, embedding_similarity=0.15, source_count=0.10, recency=0.10). `affinity_version` set to 2. Dunbar tiers reassigned by rank.

**V2 signal availability:**
| Signal | Weight | Data Available? | Notes |
|--------|--------|----------------|-------|
| career_overlap | 0.40 | Yes — after Step 1 enriches employee_count | size_factor uses real counts instead of 500 default |
| external_contact | 0.25 | Yes — after Step 2 loads contacts | phone=1.0, email=0.7 for matched contacts |
| embedding_similarity | 0.15 | Partial — only enriched profiles have embeddings | ~20K enriched profiles have 1536-dim vectors |
| source_count | 0.10 | Yes | Already populated from import |
| recency | 0.10 | Yes | Already populated from connected_at |

**Verification:**
```sql
-- Version distribution
SELECT affinity_version, COUNT(*) FROM connection WHERE affinity_score > 0 GROUP BY 1;

-- Signal coverage
SELECT
  COUNT(*) FILTER (WHERE affinity_career_overlap > 0) as career,
  COUNT(*) FILTER (WHERE affinity_external_contact > 0) as ext_contact,
  COUNT(*) FILTER (WHERE affinity_embedding_similarity > 0) as emb_sim,
  COUNT(*) FILTER (WHERE affinity_source_count > 0) as src_count,
  COUNT(*) FILTER (WHERE affinity_recency > 0) as recency
FROM connection WHERE affinity_score > 0;

-- Dunbar tier distribution
SELECT dunbar_tier, COUNT(*) FROM connection WHERE affinity_score > 0 GROUP BY 1 ORDER BY 1;

-- Top 10 by affinity
SELECT c.affinity_score, cp.full_name, c.dunbar_tier,
       c.affinity_career_overlap, c.affinity_external_contact, c.affinity_embedding_similarity
FROM connection c
JOIN crawled_profile cp ON c.crawled_profile_id = cp.id
WHERE c.affinity_score > 0
ORDER BY c.affinity_score DESC LIMIT 10;
```

### Step 4: Verify End-to-End

Quick sanity checks that everything hangs together.

```sql
-- Company enrichment fed into career overlap
SELECT COUNT(*) FROM company WHERE estimated_employee_count IS NOT NULL AND estimated_employee_count != 500;

-- External contacts fed into affinity
SELECT COUNT(DISTINCT cs.connection_id)
FROM contact_source cs
WHERE cs.dedup_status = 'matched'
  AND cs.source_type IN ('google_contacts_job', 'contacts_phone', 'gmail_email_only');

-- Connections with non-zero external_contact signal
SELECT COUNT(*) FROM connection WHERE affinity_external_contact > 0;

-- The above two counts should match (or be close)
```

## Key Decisions (already made)

- PDL CSV as lookup only (not bulk load) — match by LinkedIn slug/domain/name
- Two PDL transactions (PDL commits first, Wikidata separate) — not relevant here since we skip Wikidata for now
- Gmail contact_source cleanup before insert (idempotent re-runs)
- V2 weights ship as constants, tuned via eyeball session after first run
- External contact: cap at highest tier (phone=1.0, email=0.7, no stacking)

## Execution Order

```
Step 1 (enrich-companies) ──> Step 2 (load-gmail-contacts) ──> Step 3 (compute-affinity) ──> Step 4 (verify)
```

Steps 1 and 2 are independent but both must complete before Step 3. Running sequentially for simplicity.
