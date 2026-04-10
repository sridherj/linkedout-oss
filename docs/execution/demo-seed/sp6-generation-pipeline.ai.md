# Sub-phase 6: Generation Pipeline (scripts/generate-demo-dump.py)

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP6 |
| Dependencies | SP1 (demo constants for IDs and data_source markers) |
| Estimated effort | 3 sessions (~10 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-08-demo-seed-plan.md` — Sub-phase 6 |

## Objective

A maintainer-only script connects to the production Postgres database, samples 2,000 profiles with stratified sampling, anonymizes PII, re-embeds with fresh embeddings, computes affinity, creates connection records for the system user, and produces a `pg_dump --format=custom` file ready for upload as a GitHub Release asset.

## Context

This script is run by maintainers (SJ) to produce the demo dump that end users download. It reads from the production database (read-only), anonymizes all PII, and outputs a self-contained dump file. The script is gitignored — it's not shipped with the repo.

### Key existing files (read these before implementing)

- `backend/src/linkedout/demo/__init__.py` — Demo constants: `DEMO_DB_NAME` (from SP1)
- `backend/src/shared/config/agent_context.py` — System user IDs (`usr_sys_001`)
- `backend/src/linkedout/commands/embed.py` — Embedding command (called as subprocess)
- `backend/src/linkedout/commands/compute_affinity.py` — Affinity command (called as subprocess)
- Alembic migrations in `backend/src/shared/migrations/` — Schema creation

## Tasks

### 1. Create the generation script

Create `scripts/generate-demo-dump.py` (gitignored):

- CLI args: `--db-url` (required), `--output` (default: `demo-seed.dump`), `--sample-size` (default: 2000), `--seed` (random seed for reproducibility)

- High-level flow:
  1. Connect to production database (read-only)
  2. Run stratified sampling query
  3. Create a temporary database (`linkedout_demo_gen`)
  4. Run Alembic migrations against the temp DB (creates clean schema)
  5. Insert anonymized data in FK-safe order
  6. Run `linkedout embed` against the temp DB
  7. Run `linkedout compute-affinity` against the temp DB
  8. Run `pg_dump --format=custom` on the temp DB
  9. Drop the temp DB
  10. Print summary stats

### 2. Implement stratified sampling

- Query production for seniority_level/function_area/location_country distribution
- Calculate per-bucket sample sizes proportional to production distribution
- For each bucket, `SELECT * FROM crawled_profile WHERE seniority_level = X AND function_area = Y AND location_country = Z ORDER BY RANDOM() LIMIT N`
- Handle small buckets: if a bucket has fewer profiles than its proportional share, take all and redistribute remainder to larger buckets

### 3. Implement anonymization functions

- `anonymize_name(profile) -> (first, last, full)`: Uses Faker with locale matching (`en_IN` for India, `en_US` for US, `en_GB` for UK, etc.)
- `anonymize_linkedin_url(index) -> str`: `f"https://www.linkedin.com/in/demo-user-{index:04d}"`
- `anonymize_headline(profile) -> str`: `f"{profile.current_position} at {profile.current_company_name}"`
- `anonymize_about(profile, skills) -> str`: `f"Experienced {profile.current_position} with expertise in {', '.join(skills[:3])}..."`
- `jitter_count(count, pct=0.20) -> int`: `count * random.uniform(1-pct, 1+pct)`
- `generate_demo_id(prefix, index) -> str`: `f"{prefix}{index:04d}"` for profiles, `f"{prefix}{index:06d}"` for experiences/education/skills

### 4. Implement data insertion (FK-safe order)

1. Organization tables (tenant, BU, user) — use system IDs from agent_context.py
2. Company reference data — copy all ~48K companies from production as-is
3. Company aliases, funding rounds — copy as-is
4. Role aliases — copy as-is
5. Anonymized crawled_profiles (2K)
6. Experiences (~12K) — real positions/companies/dates, new IDs
7. Education (~4.4K) — real schools/degrees/fields, new IDs
8. Skills (~10K, capped at 5 per profile) — real skill names, new IDs
9. Connection records (2K) — one per profile, linked to system user

### 5. Create demo user profile

The system user (`usr_sys_001`) needs a crawled_profile record in the demo DB representing the "founder/CTO composite" profile:

- NOT from production — it's a synthetic profile modeled after SJ
- Include: founder/CTO title, Bengaluru location, broad skills (ML, product, data, distributed systems, Python, leadership), 8 years experience
- This profile gets embedded along with the 2K sampled profiles

### 6. Embed and compute affinity

- Set `DATABASE_URL` env var to point at temp DB
- Call `linkedout embed` as subprocess (reuses existing embedding infrastructure)
- Call `linkedout compute-affinity` as subprocess
- Both commands are idempotent and will process all profiles/connections

### 7. Create manifest template

Create `scripts/demo-manifest-template.json`:
```json
{
  "version": "demo-v1",
  "files": [
    {
      "name": "demo-seed.dump",
      "tier": "demo",
      "sha256": "<computed-after-dump>",
      "size_bytes": 0
    }
  ]
}
```

### 8. Add to .gitignore

Add `scripts/generate-demo-dump.py` to `.gitignore`.

## Verification Checklist

- [ ] Script runs: `python scripts/generate-demo-dump.py --db-url=<prod> --output=demo-seed.dump`
- [ ] Output file exists and is 50-150 MB
- [ ] Restore the dump into a test database and verify:
  - [ ] `SELECT count(*) FROM crawled_profile` = ~2,000
  - [ ] `SELECT count(*) FROM experience` = ~12,000
  - [ ] `SELECT count(*) FROM education` = ~4,400
  - [ ] `SELECT count(*) FROM profile_skill` = ~10,000
  - [ ] `SELECT count(*) FROM connection` = ~2,000
  - [ ] Company tables match seed data (~48K)
  - [ ] No real names in `crawled_profile`: Faker names only
  - [ ] All IDs start with `cp_demo_`, `exp_demo_`, etc.
  - [ ] All `data_source = 'demo-seed'`
  - [ ] Embeddings exist: `embedding_local IS NOT NULL`
  - [ ] Affinity scores exist: `affinity_score IS NOT NULL`
  - [ ] Alembic version table exists
  - [ ] Connection records reference `usr_sys_001`
- [ ] Stratified sampling: distribution roughly matches production
- [ ] PII check: no LinkedIn URLs contain real public identifiers

## Design Notes

- **Security:** The script connects to production with provided credentials (read-only). The output dump contains no real PII. The script itself is gitignored.
- **Error paths:** If embedding fails (local model not downloaded), error clearly: "Download the nomic-embed-text-v1.5 model first."
- **Architecture:** Using a temporary database (`linkedout_demo_gen`) for generation means we can run Alembic migrations to get a clean schema, then insert data, then embed/score. This guarantees the dump's schema matches what `pg_restore` expects on the user's end.
- **Data coupling:** The demo user profile (founder/CTO) must be consistent between: (a) the generation script where it's inserted, (b) `sample_queries.py` (SP5) where it's described, and (c) the affinity scores which are relative to it.
- **Dump size estimate:** 2K profiles * ~6KB embedding = 12MB for embeddings. ~75K rows of structured data ~20-30MB. Total raw ~40MB, pg_dump custom format compresses well. Estimate: 50-100MB.
- **Embedding provider:** Local model (`nomic-embed-text-v1.5`, 768-dim). Free, no API key required. Embeddings stored in `embedding_local` column.
