# Sub-Phase 2: DB Operations — role_alias Population and Experience/Profile Updates

**Goal:** linkedin-ai-production
**Source plan:** 2026-03-28-classify-roles-port-and-wiring.md
**Type:** DB operations — bulk SQL with sqlalchemy.text()
**Estimated effort:** ~3-4 hours
**Dependencies:** Sub-Phase 1 (pure functions must exist)
**Can parallelize with:** Nothing (sequential)

---

## Overview

Implement the `main(dry_run=False)` function in `classify_roles.py`. When called, it: (1) fetches distinct titles from `experience.position` UNION `crawled_profile.current_position`, (2) classifies them in-memory, (3) upserts into `role_alias` with `ON CONFLICT`, (4) bulk updates `experience.seniority_level/function_area`, (5) updates `crawled_profile` from current experience + direct role_alias fallback. Dry-run mode executes steps 1-2 only and prints stats.

---

## Step 1: Title Extraction Query

**What:** UNION DISTINCT titles from two tables.

**Actions:**
1. Add `main(dry_run: bool = False) -> int` function to `src/dev_tools/classify_roles.py`
2. Use `sqlalchemy.text()` with `db_session_manager.get_session(DbSessionType.WRITE)`:
   ```sql
   SELECT DISTINCT title FROM (
       SELECT position AS title FROM experience WHERE position IS NOT NULL
       UNION
       SELECT current_position AS title FROM crawled_profile WHERE current_position IS NOT NULL
   ) t
   ```
3. Handle edge case: if 0 titles found, print "No titles found" and return 0

**Verification:**
- [ ] Query returns expected title count when run against dev DB

---

## Step 2: In-Memory Classification Loop

**What:** Iterate titles, classify with pure functions, collect results.

**Actions:**
1. Loop over fetched titles, call `classify_seniority(title.strip().lower())` and `classify_function(title.strip().lower())` for each
2. Store classifications as list of dicts: `{title, seniority_level, function_area}`
3. For dry-run mode: print total titles, classified count, percentage, seniority distribution, function distribution, then `return 0`

**Key constraint:** Store `alias_title` as lowercase (`.strip().lower()`) — prevents casing variants from inflating role_alias table and ensures reliable JOINs.

**Verification:**
- [ ] `--dry-run` prints classification stats without writing to DB
- [ ] Classification rate ~80% matches expectations

---

## Step 3: INSERT role_alias with ON CONFLICT

**What:** Upsert classified titles into `role_alias` table.

**Actions:**
1. Generate `ra_` prefixed nanoid IDs via `Nanoid.make_nanoid_with_prefix('ra')`
2. Use batched raw SQL with `sqlalchemy.text()`, batch size 500-1000:
   ```sql
   INSERT INTO role_alias (id, alias_title, canonical_title, seniority_level, function_area, is_active, version, created_at, updated_at)
   VALUES (:id, :alias_title, :canonical_title, :seniority_level, :function_area, true, 1, NOW(), NOW())
   ON CONFLICT (alias_title) DO UPDATE SET
       seniority_level = EXCLUDED.seniority_level,
       function_area = EXCLUDED.function_area,
       updated_at = NOW()
   ```
3. **CRITICAL:** Must include all BaseEntity required fields (`id`, `is_active`, `version`, `created_at`, `updated_at`) since bypassing ORM

**Verification:**
- [ ] `SELECT COUNT(*) FROM role_alias;` shows expected row count after insert
- [ ] Re-running is idempotent (ON CONFLICT handles duplicates)

---

## Step 4: UPDATE experience via Temp Table JOIN

**What:** Bulk update experience rows with classifications.

**Actions:**
1. Create temp table:
   ```sql
   CREATE TEMP TABLE _role_map (title TEXT, seniority TEXT, function_area TEXT)
   ```
2. Batch INSERT classifications into temp table
3. UPDATE experience:
   ```sql
   UPDATE experience e
   SET seniority_level = rm.seniority,
       function_area = rm.function_area
   FROM _role_map rm
   WHERE e.position = rm.title
     AND (e.seniority_level IS NULL OR e.function_area IS NULL)
   ```

**Design note:** Old script used psycopg COPY protocol — adapted to sqlalchemy.text() batch INSERT. 40K rows is small enough that this is fast (<5s).

**Verification:**
- [ ] Experience rows have seniority_level and function_area populated

---

## Step 5: UPDATE crawled_profile

**What:** Two UPDATE statements to propagate classifications to profiles.

**Actions:**
1. From current experience (matching old script's `is_current = TRUE` + `start_date DESC` logic):
   ```sql
   UPDATE crawled_profile p
   SET seniority_level = sub.seniority_level,
       function_area = sub.function_area
   FROM (
       SELECT DISTINCT ON (crawled_profile_id)
           crawled_profile_id, seniority_level, function_area
       FROM experience
       WHERE is_current = TRUE
         AND (seniority_level IS NOT NULL OR function_area IS NOT NULL)
       ORDER BY crawled_profile_id, start_date DESC NULLS LAST, id DESC
   ) sub
   WHERE sub.crawled_profile_id = p.id
     AND p.has_enriched_data = TRUE
   ```
2. Direct role_alias fallback for profiles without current experience match:
   ```sql
   UPDATE crawled_profile p
   SET seniority_level = ra.seniority_level,
       function_area = ra.function_area
   FROM role_alias ra
   WHERE ra.alias_title = p.current_position
     AND p.seniority_level IS NULL
     AND p.current_position IS NOT NULL
   ```

**Verification:**
- [ ] Profiles with current experience have seniority_level populated
- [ ] Profiles without experience but with role_alias match also populated

---

## Step 6: Distribution Report and Error Handling

**What:** Print summary and handle errors.

**Actions:**
1. Print distribution report at end (matching old script style): seniority counts, function counts, total rows affected per step
2. Wrap entire operation in single transaction (db_session_manager context manager handles this)
3. If any step fails, transaction rolls back. Print error and return exit code 1

**Verification:**
- [ ] Distribution report prints after successful run
- [ ] Failed run rolls back cleanly

---

## Completion Criteria

- [ ] `main(dry_run=True)` prints stats without writing
- [ ] `main(dry_run=False)` populates `role_alias`, updates `experience` + `crawled_profile`
- [ ] `SELECT COUNT(*) FROM role_alias;` shows ~36K rows
- [ ] Seniority/function distribution matches expectations (~80% coverage)
- [ ] `rcv2 db backfill-seniority --dry-run` shows matches (confirms role_alias data is usable)
- [ ] Idempotent: re-running produces same results
