---
status: refined
confidence:
  intent: high
  behavior: high
  constraints: high
  out_of_scope: high
open_unknowns: 0
questions_asked: 3
---

# Demo Seed — Refined Requirements

## Intent

**Job statement:** When a user first installs LinkedOut and faces a cold-start empty database, they want to immediately experience the product's core value (semantic search, affinity scoring, the AI intelligence agent) without importing their own LinkedIn connections, running embeddings, or computing affinity -- so they can decide if LinkedOut is worth the full multi-step setup.

**Expanded context:** The demo is a *temporary playground*, not a permanent mode. It exists to collapse time-to-value from "30-minute setup" to "2-minute restore." The user should feel like they're using a real LinkedOut instance with realistic data -- real companies, real job titles, real skill distributions -- just with anonymized identities. Periodic nudges encourage transition to real data, but the demo never expires or degrades.

---

## Behavior

### Scenario 1: Demo offer during setup (happy path)

**When** the user runs `linkedout setup` and completes Step 3 (Database Setup), the system shall present a prompt offering to load demo data into a separate `linkedout_demo` database, with a clear description of what they'll get (2,000 sample profiles, search, affinity, AI agent) and options to accept or skip to full setup.

### Scenario 2: Demo database download and restore

**When** the user accepts the demo offer, the system shall:
1. Download the demo dump file from the GitHub Release asset (estimated 50-150 MB compressed)
2. Create a separate Postgres database named `linkedout_demo`
3. Restore the dump into `linkedout_demo` using `pg_restore`
4. Configure the application to point at `linkedout_demo`
5. Report success with profile count, company count, and a sample query to try

### Scenario 3: Demo database coexistence with real database

**While** the demo database (`linkedout_demo`) exists, **when** the user later runs the full setup flow (steps 4-14), the system shall create the real `linkedout` database via Alembic migrations as normal. Both databases coexist -- no destructive operations are needed on the demo database during real setup.

### Scenario 4: Transition from demo to real data

**When** the user is ready to switch from demo to real data, the system shall:
1. Update the application configuration to point at the real `linkedout` database
2. Optionally drop the `linkedout_demo` database (user's choice, not automatic)
3. No data migration between demo and real databases -- they are fully independent

### Scenario 5: Periodic transition nudges

**While** the application is configured to use the demo database, **when** the user interacts with LinkedOut at natural touchpoints (CLI startup, after queries, skill invocations), the system shall periodically display a non-blocking nudge suggesting they set up their real data. Nudges are informational, not obstructive -- they never block a query or command from executing.

### Scenario 6: Demo reset

**When** the user wants to reset the demo to its original state, the system shall drop and re-restore `linkedout_demo` from the original dump file, preserving any cached download.

### Scenario 7: Generation pipeline -- anonymization (maintainer-only)

**When** the maintainer runs `scripts/generate-demo-dump.py` (gitignored, not shipped to OSS users) against the production database, the system shall:
1. Connect to the production Postgres database (28K profiles, 22K enriched)
2. Sample ~2,000 profiles using stratified sampling across (seniority_level, function_area, location_country) to preserve the real distribution
3. Anonymize PII fields: names (locale-matched Faker), LinkedIn URLs, headlines (reconstructed from position + company), about text (templated), profile images (nulled), connection/follower counts (jittered +/-20%)
4. Preserve structural data: real companies, positions, locations, skills, education, experience dates, seniority, function area
5. Assign demo IDs (`cp_demo_NNNN`, `exp_demo_NNNNNN`, etc.) and `data_source='demo-seed'`
6. Create connection records linking to system user (`tenant_sys_001`, `bu_sys_001`, `usr_sys_001`)
7. Run `linkedout embed` against the anonymized profiles to generate fresh embeddings (no embedding leakage from original text)
8. Compute affinity scores on the demo connections
9. Produce a `pg_dump --format=custom` output file containing the complete, functional database

### Scenario 8: Dump contents -- full functional instance

The demo dump shall contain a complete LinkedOut instance that works without any additional setup steps:
1. Organization tables (system tenant, BU, user)
2. Company reference data (~48K companies with aliases, funding, etc.)
3. ~2,000 anonymized crawled profiles
4. ~12,000 experience records (~6 per profile)
5. ~4,400 education records (~2.2 per profile)
6. ~10,000 skill records (capped at 5 per profile)
7. ~2,000 connection records (1 per profile, linked to system user)
8. Pre-computed embeddings (pgvector, so semantic search works immediately)
9. Pre-computed affinity scores (so ranking works immediately)
10. Alembic version table (so migrations think the schema is up to date)

### Scenario 9: Demo database detection

**If** the application cannot determine which database to use (e.g., config points to `linkedout_demo` but the user expects real data, or vice versa), **then** the system shall clearly indicate which database is active and how to switch.

### Scenario 10: Sample queries with followups and profile explanation

**When** the demo database is first loaded, the system shall present seed sample queries that demonstrate LinkedOut's core capabilities. These queries shall:

1. **Cover all three pillars:** semantic search, affinity/relationship scoring, and the AI intelligence agent -- so the user sees the full product surface, not just one feature.
2. **Include followup queries:** Each sample query shall suggest 1-2 natural followup queries, demonstrating the conversational flow (e.g., initial search -> drill into a result -> compare candidates). This shows users that LinkedOut is not just a one-shot search tool.
3. **Explain the demo user's own profile:** The system shall describe the system user's demo identity (e.g., "Your demo profile is a Senior ML Engineer at Acme Corp, based in Bengaluru, with 8 years of experience in machine learning and distributed systems"). This is critical because affinity and relationship scores are *relative to the user* -- without understanding the demo profile, users cannot interpret why certain connections score higher than others.
4. **Explain the "why" behind results:** Sample query outputs shall include explanations of how affinity/relationship scores were calculated (e.g., "This connection scored high because you share: same company (Acme Corp), overlapping skills (ML, Python), and similar seniority level"). The educational value of the demo depends on users understanding the scoring mechanism, not just seeing numbers.

**Where** the demo database is active, the system shall make the sample queries accessible both at first load and on demand (e.g., via a `linkedout demo-help` command or equivalent), so users can return to them after exploring on their own.

---

## Constraints

- **Database isolation:** Demo data lives in a separate Postgres database (`linkedout_demo`), never mixed with the real `linkedout` database. This eliminates all marker/cleanup/cascade complexity from the earlier in-DB approach.
- **Dump size:** Target 50-150 MB compressed. The dump includes pgvector embeddings (~6 KB per row for 1536-dim vectors across 2K profiles = ~12 MB for embeddings alone) plus all table data.
- **Hosting:** The dump file is hosted as a GitHub Release asset. Download URL must be stable across releases.
- **Generation script location:** `scripts/generate-demo-dump.py` lives in the main `linkedout-oss` repo but is gitignored -- it exists locally for the maintainer but is never shipped to OSS users. It is maintainer-only tooling (requires production DB access).
- **Embedding generation:** Embeddings are generated by running `linkedout embed` against the anonymized profiles during dump generation. This ensures no information leakage from original profile text encoded in embedding vectors.
- **Anonymization completeness:** No real person's name, LinkedIn URL, or free-text PII may appear in the dump. Structural data (companies, positions, locations, skills, schools) is explicitly kept as-is because it is not PII and is critical for demo quality.
- **Demo IDs:** All demo records use the `cp_demo_`, `exp_demo_`, `edu_demo_`, `psk_demo_`, `conn_demo_` ID prefixes. All crawled_profile records have `data_source='demo-seed'`.
- **System user:** Demo connections are owned by system IDs (`tenant_sys_001`, `bu_sys_001`, `usr_sys_001`).
- **Stratified sampling:** The 2K profile sample must preserve the real distribution across seniority level, function area, and country -- not random sampling that could skew toward the majority bucket.

---

## Out of Scope

- **Generation tooling shipping:** The generation script (`scripts/generate-demo-dump.py`) is gitignored in the main repo. OSS users never see it. Only the CLI code to download and restore the dump is shipped.
- **In-DB demo mode:** The earlier approach of mixing demo data into the real database with markers and cleanup hooks is rejected in favor of database-level isolation.
- **Demo data updates/versioning:** The demo dump is regenerated manually by the maintainer when needed. No automatic update mechanism.
- **Demo expiration or degradation:** The demo never expires, locks features, or degrades over time. Nudges encourage transition but never force it.
- **Data migration from demo to real:** There is no path to "keep" demo data when transitioning. The demo database is disposable.
- **Chrome extension in demo mode:** Whether the extension works against the demo database is not in scope for this feature. It may work incidentally since it just talks to the backend API.
- **Multi-user demo support:** The demo uses a single system user. No multi-tenancy in demo mode.

---

## Resolved Questions

1. **Alembic version in dump:** `pg_dump` of a fully-migrated database automatically captures the `alembic_version` table. No special handling needed — `pg_restore` restores it as-is. If the OSS repo's migrations evolve past the dump's revision, a new dump release is needed anyway.

2. **Nudge approach:** Subtle persistent footer on every CLI output in demo mode: `Demo mode · linkedout setup to use your own data`. No nudge logic, no state tracking, no dismissal mechanism needed. Always visible, never interrupts flow.

3. **Download caching:** Cache the dump at `~/linkedout-data/cache/demo-seed.dump`. On reset, re-use the cached file (instant `pg_restore`, no re-download). To refresh: `linkedout download-demo --force` re-fetches from GitHub Releases.

4. **Demo user profile design:** Founder/CTO composite profile modeled after SJ's real profile. Broad skills spanning engineering, product, and data. This produces moderate affinity with many profiles, showcasing breadth of the scoring system. The sample queries should explain how the founder profile relates to different connection types (engineers, managers, data scientists, etc.).
