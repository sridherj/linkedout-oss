# Demo Seed Experience — Requirements & Decisions

> **Status:** Requirements captured. Plan needed. Extends from the OSS first-commit audit session.
> **Date:** 2026-04-08

## Problem

When a user first installs LinkedOut, they have an empty database. They can't
experience the product — search, affinity scoring, the intelligence agent — until
they import their own LinkedIn connections, run embeddings, and compute affinity.
That's a multi-step setup before they see any value.

We need a **zero-effort demo experience** so users can query a realistic network
immediately and decide if LinkedOut is worth the full setup.

## Final Approach: Separate Postgres Demo Dump

Instead of mixing demo data into the real DB (markers, cleanup logic, cascade
deletes), provide a **complete Postgres dump** that can be restored before
the user starts their real setup. If they like what they see, they wipe it
and continue with their own data.

### Why this is better than the in-DB demo approach

| Concern | In-DB demo (rejected) | Separate dump (chosen) |
|---------|----------------------|----------------------|
| Mixed data | Demo + real data coexist, need markers/cleanup | Completely isolated — demo DB or real DB, never both |
| Cleanup complexity | CASCADE deletes, data_source markers, import hooks | `DROP DATABASE` or `pg_restore` — atomic, no stray data |
| Embeddings in demo | Would need to ship pre-computed embeddings somehow | Dump includes embeddings — full search works instantly |
| Affinity in demo | Would need pre-computed scores | Dump includes affinity scores — everything works |
| Onboarding flow | Complicated branching in setup orchestrator | Simple fork: "try demo?" → restore dump, done |
| Separate repo | Not needed | Yes — keeps main repo clean, dump is large (~100-500MB) |

## Decisions Made (from interview)

| # | Question | Decision |
|---|----------|---------|
| 1 | Demo data marker | `data_source='demo-seed'` + `cp_demo_` ID prefix — **still useful** even in the dump approach for identification |
| 2 | Companies | Reference real enriched companies (not fakes) |
| 3 | Data source | SJ's real 22K enriched profiles from production DB, anonymized |
| 4 | Demo user | System IDs: `tenant_sys_001`, `bu_sys_001`, `usr_sys_001` |
| 5 | Scale | ~2K profiles (enough meat for realistic search queries) |

## Production DB Stats (source for demo generation)

```
profiles:     28,096 (22,453 enriched)
experiences: 134,012 (~6.1 per profile)
educations:   47,317 (~2.2 per profile)
skills:      758,733 (~34.7 per profile, cap at 5 for demo)
companies:    47,873

Seniority: mid 33%, unknown 21%, senior 15%, manager 9%, lead 8%, founder 4%, director 3%, c_suite 3%, vp 2%, junior 1%
Function:  engineering 40%, unknown 38%, data 6%, consulting 4%, sales 3%, hr 2%, marketing 2%, product 2%, design 1%, research 1%
Countries: India 83%, US 10%, UK 1.3%, Canada 1.2%, UAE 0.9%, Germany 0.7%, ...
Top cities: Bengaluru, Pune, Hyderabad, Mumbai, Gurgaon, Delhi, Chennai, Noida, SF, New Delhi
```

## Anonymization Rules

**What changes (PII):**
- `first_name` / `last_name` / `full_name` → Faker names (locale-matched: Indian for India, etc.)
- `linkedin_url` / `public_identifier` → `https://www.linkedin.com/in/demo-user-NNNN`
- `headline` → reconstructed from real `current_position` + `current_company_name`
- `about` → templated: "Experienced {position} with expertise in {top_skills}..."
- `profile_image_url` → null
- `connections_count` / `follower_count` → jittered ±20%
- `id` → `cp_demo_NNNN` prefix

**What stays real (structural, not PII):**
- Company references (`current_company_name`, `company_id`) — real seed companies
- Location (`location_city`, `location_state`, `location_country`, `location_country_code`)
- `seniority_level`, `function_area`
- `open_to_work`, `premium` (booleans)
- Experience records: real positions, real companies, real dates, real locations (new IDs only)
- Education records: real schools, degrees, fields (new IDs only)
- Skill records: real skill names (new IDs only)
- Connection records created for system user

## Demo Dump Contents

The Postgres dump should contain a **fully functional** LinkedOut instance:

1. **Organization tables** — system tenant, BU, user (`tenant_sys_001`, etc.)
2. **Company reference data** — same as seed export (companies, aliases, funding, etc.)
3. **2K anonymized profiles** — sampled with stratified diversity from real data
4. **~12K experiences** (~6 per profile)
5. **~4.4K educations** (~2.2 per profile)
6. **~10K skills** (capped at 5 per profile for dump size)
7. **2K connection records** — linking system user to demo profiles
8. **Pre-computed embeddings** — pgvector columns populated so semantic search works
9. **Pre-computed affinity scores** — on connection records so ranking works
10. **Role aliases + company aliases** — for normalization

## User Flow (proposed)

```
$ linkedout setup

Step 1: Prerequisites ✓ (Python, Postgres, pgvector)
Step 2: System setup ✓
Step 3: Database created ✓

  ╭─────────────────────────────────────────────────╮
  │  Want to try LinkedOut with demo data first?     │
  │                                                  │
  │  We'll load 2,000 sample profiles so you can     │
  │  test search, affinity scoring, and the AI       │
  │  agent before importing your own connections.    │
  │                                                  │
  │  [Y] Try the demo   [n] Skip to full setup       │
  ╰─────────────────────────────────────────────────╯

  Downloading demo database... (150 MB)
  Restoring... done.

  ✓ Demo loaded: 2,000 profiles | 47K companies | embeddings ready

  Try it now:
    /linkedout "Who in my network works in ML at a Series B startup?"

  When you're ready for your own data:
    linkedout setup --reset-demo
```

## Architecture

- **Separate repo:** `linkedout-demo-data` (or `linkedout-oss-demo`) — hosts the Postgres dump as a GitHub Release asset
- **Generation script:** `scripts/generate-demo-dump.py` — connects to SJ's real DB, anonymizes 2K profiles, creates a full Postgres dump with embeddings and affinity
- **CLI integration:** `linkedout download-demo` / `linkedout setup --reset-demo`
- **Dump format:** `pg_dump --format=custom` → single `.dump` file, compressed
- **Restore:** `pg_restore --clean --if-exists` into the user's database

## Open Questions for Plan Phase

1. **Embedding generation for demo:** Run `linkedout embed` against the anonymized profiles before dumping, or copy real embeddings (anonymized profiles have same structural content so embeddings are still representative)?
2. **Dump size:** Estimate based on 2K profiles + embeddings (pgvector is ~6KB per row for 1536-dim) → ~12MB for embeddings + ~50MB for all tables. Compressed dump likely ~50-100MB.
3. **Separate repo name:** `linkedout-demo-data`? `linkedout-oss-demo`?
4. **Setup orchestrator changes:** Where exactly in the 14-step flow does the demo fork happen? After step 3 (database created) seems right — before API keys, CSV import, etc.
5. **Reset mechanism:** `linkedout setup --reset-demo` does what exactly? `DROP` + recreate DB + re-run migrations? Or just truncate demo tables?
6. **Alembic migrations:** The dump is a raw Postgres restore. Does it include the Alembic version table so migrations think they're up to date?

## What Needs Changing in Current Commit

### Leave as-is (already correct for OSS)
- `.gitignore` updates (session files, settings.json, backend/docs/, etc.)
- Fake fixtures in `backend/src/dev_tools/db/fixtures/` (for load_fixtures dev tool)
- `scripts/generate-fake-fixtures.py` (generates dev fixtures, unrelated to demo)

### Revert / don't change
- `seed_export.py` — **leave original** (exports all 10 tables including profiles). The demo approach means seed_export is only used by the maintainer to build the demo dump, not by OSS users. Profile PII handling (`PII_NULL_COLUMNS`, `EXCLUDE_COLUMNS`) is still needed for the dump generation.
- `import_seed.py` — **leave original** (imports all 10 tables). May still be used for company-only seed if we ship that separately.

### New work (not in this commit, separate effort)
- `scripts/generate-demo-dump.py` — the core anonymization + dump script
- `linkedout-demo-data` repo setup
- Setup orchestrator changes for demo fork
- `linkedout download-demo` / `linkedout setup --reset-demo` commands

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/src/linkedout/setup/orchestrator.py` | 14-step setup flow, state persistence |
| `backend/src/linkedout/setup/seed_data.py` | Current seed download/import orchestration |
| `backend/src/linkedout/commands/setup.py` | CLI entry point |
| `backend/src/linkedout/commands/import_seed.py` | Seed import (10 tables, FK-safe order) |
| `backend/src/linkedout/commands/import_connections.py` | LinkedIn CSV import |
| `backend/src/dev_tools/seed_export.py` | Postgres → SQLite seed exporter |
| `backend/src/linkedout/commands/embed.py` | Embedding generation |
| `backend/src/linkedout/setup/embeddings.py` | Embedding setup step |
| `backend/src/shared/config/agent_context.py` | System IDs (tenant_sys_001, etc.) |
| `docs/getting-started.md` | User-facing setup docs |
