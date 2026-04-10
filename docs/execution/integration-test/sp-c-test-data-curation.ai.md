# SP-C: Test Data Curation

**Phase:** Integration Test for Installation
**Plan tasks:** C1 (LinkedIn subset), C2 (Gmail subset), C3 (API key sourcing)
**Dependencies:** SP-A (sandbox must support `--dev` for volume-mounting fixtures)
**Blocks:** SP-D (parent harness needs test data fixtures)
**Can run in parallel with:** SP-B

## Objective

Select and prepare curated subsets of LinkedIn connections and Gmail contacts as version-controlled fixtures for Phase II (full setup with own data). Define the API key sourcing mechanism. The fixtures must be reproducible and provide diverse coverage for meaningful test assertions.

## Context

- Read shared context: `docs/execution/integration-test/_shared_context.md`
- Read plan (Sub-phase C section): `docs/plan/integration-test-installation.md`
- Read requirements (Scenario 4 — Phase II): `.taskos/integration_test_refined_requirements.collab.md`
- Read LinkedIn CSV converter for expected column format: `backend/src/linkedout/import_pipeline/converters/linkedin_csv.py`

## Deliverables

### C1. LinkedIn connections subset

**Source:** `<prior-project>/data/linkedin_connections.csv` (~24,800 rows)
**Output:** `tests/e2e/fixtures/linkedin-connections-subset.csv` (10-20 rows)

**Selection criteria for coverage:**
1. **Company diversity:** 8-10 different companies (mix of FAANG, startups, mid-size)
2. **Role diversity:** Engineering, product, leadership, other
3. **Location diversity:** Different geographies (US coasts, international)
4. **Temporal diversity:** Recent and older connections
5. **Name diversity:** Varied first/last names to exercise parsing

The subset must match the column format expected by `backend/src/linkedout/import_pipeline/converters/linkedin_csv.py`. Read that file first to understand the expected CSV schema.

### C2. Gmail contacts subset

**Source files:**
- `<prior-project>/agents/taskos-linkedin-ai/gmail_contacts/contacts_from_google_job.csv`
- `<prior-project>/agents/taskos-linkedin-ai/gmail_contacts/contacts_with_phone.csv`
- `<prior-project>/agents/taskos-linkedin-ai/gmail_contacts/gmail_contacts_email_id_only.csv`

**Output:** `tests/e2e/fixtures/gmail-contacts-subset.csv` (10-15 rows)

**Selection criteria:**
1. **Some match** LinkedIn connections subset (same name/company) — tests affinity overlap
2. **Some don't match** — tests no-match handling
3. **Mix of data completeness:** Some with phone, some email-only
4. Import all three source files — the import pipeline handles deduplication

### C3. API key sourcing

**Source:** `./.env.local`
**Mechanism:** The parent harness reads this file at runtime, never copies or commits keys.

No file to create — this is a design constraint documented here so SP-D knows where to source keys.

### C4. Curation script

**File to create:** `backend/src/dev_tools/curate_test_data.py`

One-time curation script. Run interactively to select rows from the source CSVs, applying the selection criteria above. Output goes to `tests/e2e/fixtures/`.

The script should:
1. Read the source LinkedIn CSV
2. Apply diversity filters (company, role, location, temporal)
3. Print a summary of selected rows for review
4. Write to `tests/e2e/fixtures/linkedin-connections-subset.csv`
5. Repeat for Gmail contacts (merge all three source files, select subset)
6. Write to `tests/e2e/fixtures/gmail-contacts-subset.csv`

This script is run once to generate the fixtures, then the fixtures are version-controlled. The script itself is kept for reproducibility but is not part of the test flow.

## Verification

1. **C1:** `tests/e2e/fixtures/linkedin-connections-subset.csv` exists with 10-20 rows
   - Has the same columns as the source CSV
   - Rows span at least 8 different companies
   - Rows span at least 3 different role types
2. **C2:** `tests/e2e/fixtures/gmail-contacts-subset.csv` exists with 10-15 rows
   - At least 3 contacts match a name/company in the LinkedIn subset
   - At least 3 contacts have no LinkedIn match
   - Mix of phone + email-only records
3. **C3:** `./.env.local` exists and contains `APIFY_API_KEY` and `OPENAI_API_KEY`
4. **C4:** Running `python backend/src/dev_tools/curate_test_data.py` regenerates the fixtures with the same output (idempotent with the same source data)

## Notes

- The fixtures contain real names/companies from SJ's network. This is acceptable because the repo is private during development. Before making the repo public, replace with synthetic data or add to `.gitignore`.
- Read the LinkedIn CSV converter (`backend/src/linkedout/import_pipeline/converters/linkedin_csv.py`) before writing fixtures — the column names and format must match exactly.
- Budget: 10-20 profiles for Apify enrichment = ~$0.10 per test run. Keep the subset small.
- The curation script is a developer tool — functional but not polished.
