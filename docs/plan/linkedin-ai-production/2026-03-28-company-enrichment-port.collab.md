# Port Company Enrichment: PDL + Wikidata Waterfall

## Overview

Port the company enrichment waterfall from second-brain (`enrich_companies.py` + `company_utils.py` + `wikidata_utils.py`) into linkedout's `dev_tools` module. The old script enriched companies via a two-phase waterfall: PDL free dataset for slug/name matching (high coverage), then Wikidata SPARQL for gap-filling (supplementary). 47K companies currently have 0% industry/website/HQ coverage -- this is the single biggest metadata gap in the system. The enrichment fills `industry`, `website`, `domain`, `founded_year`, `hq_city`, `hq_country`, `employee_count_range`, `estimated_employee_count`, and `size_tier` on the `company` table.

Key adaptation: the old script used raw psycopg with integer company IDs and columns like `pdl_id` and `wikidata_id` that don't exist in the linkedout schema. The port must add these columns via Alembic migration, switch to `sqlalchemy.text()` with `db_session_manager`, and adapt to nanoid string PKs.

## Operating Mode

**HOLD SCOPE** -- The high-level plan explicitly defines this as "port company enrichment (PDL + Wikidata)" with specific dependencies and reference scripts. No signals for expansion or reduction. Rigorous port of the existing waterfall approach.

## Sub-phase 1: Schema Extension -- Add Enrichment ID Columns

**Outcome:** `company` entity has `pdl_id` (String, nullable) and `wikidata_id` (String, nullable) columns. Alembic migration applied. Data model spec updated.

**Dependencies:** None

**Estimated effort:** 0.5 session (~1 hour)

**Verification:**
- `alembic upgrade head` succeeds
- `psql $DATABASE_URL -c "\d company"` shows `pdl_id` and `wikidata_id` columns
- `from linkedout.company.entities.company_entity import CompanyEntity` and inspecting columns shows new fields
- `rcv2 db validate-orm` passes

Key activities:

- Add two columns to `CompanyEntity` in `src/linkedout/company/entities/company_entity.py`:
  ```python
  pdl_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='People Data Labs company identifier')
  wikidata_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Wikidata Q-number identifier')
  ```
- Generate Alembic migration: `alembic revision --autogenerate -m "add_pdl_id_wikidata_id_to_company"`. Review the generated migration to confirm it only adds the two columns.
- Run `alembic upgrade head` against the dev DB.
- Update `docs/specs/linkedout_data_model.collab.md` -- add `pdl_id` and `wikidata_id` to the `company` table definition:
  ```sql
  -- External enrichment identifiers
  pdl_id                    TEXT,                     -- People Data Labs company ID
  wikidata_id               TEXT,                     -- Wikidata Q-number (e.g., Q95)
  ```
  Bump version. Delegate: `/taskos-update-spec` with the above changes. Review output.
- Run `rcv2 db validate-orm` to confirm ORM alignment.

**Design review:**
- Spec consistency: `linkedout_data_model.collab.md` > company table currently has no `pdl_id` or `wikidata_id`. Adding them is a non-breaking extension (nullable columns). Spec update required.
- Naming: `pdl_id` and `wikidata_id` are clear, lowercase, and match the external source naming convention. Consistent with `enrichment_sources` already tracking `'pdl'` and `'wikidata'` as source strings.
- Architecture: Adding columns to a shared entity requires only a migration -- no tenant scoping implications.

## Sub-phase 2: Utility Functions -- company_utils and wikidata_utils

**Outcome:** `src/dev_tools/company_utils.py` and `src/dev_tools/wikidata_utils.py` exist as importable modules. `compute_size_tier()`, `normalize_company_name()`, `resolve_subsidiary()` are available and tested. Wikidata API functions (`wikidata_search`, `batch_sparql_metadata`) are available and tested against the live API.

**Dependencies:** None (can run in parallel with Sub-phase 1)

**Estimated effort:** 1 session (~2-3 hours)

**Verification:**
- `pytest tests/dev_tools/test_company_utils.py -v` -- all cases pass (size tier, cleanco strip, subsidiary resolution)
- `pytest tests/dev_tools/test_wikidata_utils.py -v` -- passes (unit tests with mocked httpx)
- `pytest tests/live_services/test_wikidata_live.py -v` -- passes against real Wikidata API (1-2 known companies)
- `from dev_tools.company_utils import compute_size_tier, normalize_company_name, resolve_subsidiary` succeeds
- `from dev_tools.wikidata_utils import wikidata_search, batch_sparql_metadata` succeeds

Key activities:

- **Port `company_utils.py`** to `src/dev_tools/company_utils.py`. Copy verbatim:
  - `SUBSIDIARY_MAP` dict (hardcoded subsidiary-to-parent mappings)
  - `_REGIONAL_SUFFIX_RE` regex pattern
  - `normalize_company_name()` -- wraps `cleanco.basename()` for legal suffix stripping
  - `resolve_subsidiary()` -- checks hardcoded map + regional suffix regex
  - `compute_size_tier()` -- thresholds: <=50 tiny, <=200 mid, <=1000 large, else enterprise
  - Note: the old `size_tier` values differ from the data model spec comment which says `'tiny', 'small', 'mid', 'large', 'enterprise'`. The old script uses `tiny/mid/large/enterprise` (no `small`). The entity column is String(20) so either works, but verify which values are already in the DB from import pipeline and keep consistent. **[OPEN QUESTION: reconcile size_tier values]**

- **Add `cleanco` dependency** to `requirements.txt`. The old script depends on it; the linkedout project does not currently have it. Verify version compatibility: `pip install cleanco` and test import.

- **Port `wikidata_utils.py`** to `src/dev_tools/wikidata_utils.py`. Copy verbatim:
  - Constants: `WIKIDATA_API`, `SPARQL_ENDPOINT`, `SEARCH_DELAY` (0.3s), `USER_AGENT`, `HTTP_HEADERS`
  - `wikidata_search(client, name)` -- searches Wikidata wbsearchentities API, returns best match `{qid, label, description}` or None
  - `sparql_query(client, query)` -- executes SPARQL query, returns list of dicts
  - `batch_sparql_metadata(client, qids)` -- fetches P1128 (employees), P452 (industry), P571 (founded), P159 (HQ), P856 (website) for batches of 80 QIDs. Returns `{qid: {employees, industry, founded, hq, website}}`
  - Update `USER_AGENT` string from `"LinkedInIntelSpike/0.1"` to `"LinkedOut/1.0 (sridherj@gmail.com)"` to reflect the new project

- **Write unit tests** for `company_utils.py` in `tests/dev_tools/test_company_utils.py`:
  - Parametrized `compute_size_tier` tests: None->None, 1->tiny, 50->tiny, 51->mid, 200->mid, 201->large, 1000->large, 1001->enterprise
  - `normalize_company_name` tests: "Google LLC"->"Google", "Tata Consultancy Services Limited"->"Tata Consultancy Services", None->None, ""->None
  - `resolve_subsidiary` tests: "Amazon Web Services"->parent "Amazon", "Deloitte India"->parent "Deloitte", "Google"->no parent, "KPMG in India"->parent "KPMG"

- **Write unit tests** for `wikidata_utils.py` in `tests/dev_tools/test_wikidata_utils.py`:
  - Mock `httpx.Client` responses for `wikidata_search` -- test success, empty results, HTTP error
  - Mock SPARQL responses for `batch_sparql_metadata` -- test batch splitting, field extraction, gap filling from multiple rows

- **Write a live service test** in `tests/live_services/test_wikidata_live.py`:
  - Search for "Google" -- expect QID Q95 returned
  - Fetch metadata for Q95 -- expect non-empty industry and employee count
  - Mark with `@pytest.mark.live_services` so it's excluded from default test runs

**Design review:**
- Spec consistency: No spec covers dev_tools utility modules -- these are internal helpers. No conflict.
- Naming: `company_utils.py` and `wikidata_utils.py` match the old script names. Located in `dev_tools/` since they're only used by the enrichment CLI command, not by the CRUD stack.
- Architecture: These are pure utility modules with no DB dependencies (except `cleanco` third-party). Correct placement in `dev_tools/` rather than `shared/utils/` since they're enrichment-specific, not cross-cutting.
- Error paths: `wikidata_search` returns None on HTTP errors (old script behavior) -- caller handles gracefully. `batch_sparql_metadata` returns empty dict on SPARQL failure -- caller skips enrichment. Both are correct for a best-effort gap-fill.
- Security: Wikidata API is public, no auth needed. `USER_AGENT` follows Wikidata's User-Agent policy requirement. No secrets involved.

## Sub-phase 3: Core Enrichment Script -- PDL Scan + Wikidata Gap-Fill

**Outcome:** `src/dev_tools/enrich_companies.py` exists with a `main()` function implementing the full waterfall: PDL CSV scan (slug match -> name match fallback) then Wikidata SPARQL gap-fill. When run against the dev DB, it enriches company rows with industry/website/HQ/size data. Idempotent via `enrichment_sources` array check.

**Dependencies:** Sub-phase 1 (pdl_id/wikidata_id columns), Sub-phase 2 (utility functions)

**Estimated effort:** 2 sessions (~4-5 hours)

**Verification:**
- `rcv2 db enrich-companies --dry-run` prints target count, PDL file size, match preview
- `rcv2 db enrich-companies --skip-wikidata` enriches via PDL only; `psql` shows populated fields
- `rcv2 db enrich-companies` runs full waterfall
- `psql $DATABASE_URL -c "SELECT COUNT(*) FROM company WHERE 'pdl' = ANY(enrichment_sources);"` shows PDL-enriched count
- `psql $DATABASE_URL -c "SELECT COUNT(*) FROM company WHERE 'wikidata' = ANY(enrichment_sources);"` shows Wikidata-enriched count
- `psql $DATABASE_URL -c "SELECT COUNT(*) FROM company WHERE industry IS NOT NULL;"` shows industry coverage improvement
- `psql $DATABASE_URL -c "SELECT size_tier, COUNT(*) FROM company WHERE size_tier IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;"` shows size distribution
- Rerunning the command is a no-op (idempotent)

Key activities:

- **Create `src/dev_tools/enrich_companies.py`** with the following structure adapted from the old script:

  **Constants and helpers:**
  - `PDL_SIZE_MAP` -- maps PDL size strings ("1-10", "11-50", ...) to midpoint employee estimates. Copy verbatim.
  - `PDL_COLUMNS` -- list of CSV columns to read. Copy verbatim.
  - `DEFAULT_PDL_PATH` -- adapt to linkedout project data location. Use env var `PDL_COMPANIES_CSV` with fallback to `~/data/pdl/companies.csv`.
  - `_parse_founded(val)` -- extracts 4-digit year from PDL founded field. Copy verbatim.
  - `_extract_pdl_fields(row)` -- builds enrichment dict from a PDL CSV row (industry, founded_year, hq_country, hq_city, website, domain, employee_count_range, estimated_employee_count, size_tier, pdl_id). Copy verbatim, imports `compute_size_tier` from `dev_tools.company_utils`.
  - `_extract_slug(url)` -- extracts company slug from LinkedIn URL. Copy verbatim.

  **PDL phase (Phase A):**
  - `load_pdl_matches(pdl_path, target_slugs, target_names)` -- single-pass chunked CSV read via pandas. Vectorized slug extraction + name matching. Returns `{identifier: {pdl_fields...}}`. Copy the old script's approach but adapt the `import pandas` to be a lazy import (fail gracefully if pandas not installed with a clear error message).
  - `apply_pdl_enrichment(session, company_id, fields)` -- UPDATE company row using COALESCE (never overwrite existing data). Adapt from old psycopg to `sqlalchemy.text()` with named parameters. Key change: old script uses `%s` params (psycopg) -- new script uses `:param` (sqlalchemy). Also: `enrichment_sources` append uses `array_append` with the NULL-to-empty-array CASE guard (same pattern as old script).

  **Wikidata phase (Phase B):**
  - `run_wikidata_gapfill(session, limit=500)` -- queries companies missing key fields AND not already Wikidata-enriched, searches Wikidata for QIDs, batch-fetches metadata via SPARQL, applies gap-fill. Adapt from old psycopg to `sqlalchemy.text()`. Key changes:
    - Old script orders by `network_connection_count DESC` to prioritize high-value companies -- keep this behavior.
    - Old script limits to 500 companies per run (rate limit respect) -- keep this, add `--wikidata-limit N` CLI option.
    - Old script uses `httpx.Client` with 30s timeout -- keep this.
    - COALESCE-based UPDATE for Wikidata fields (same pattern as PDL).

  **`main(dry_run, skip_wikidata, pdl_file, wikidata_limit, force)` function:**
  - Use `db_session_manager.get_session(DbSessionType.WRITE)` for the session (same pattern as `classify_roles.py`).
  - Gather targets: SELECT id, universal_name, canonical_name FROM company (filtered by enrichment_sources if not --force).
  - Build slug-to-id and name-to-id lookup maps from company rows.
  - Phase A: PDL scan and apply.
  - Phase B: Wikidata gap-fill (unless --skip-wikidata).
  - Print summary: total companies, PDL-enriched count/%, Wikidata-enriched count/%, industry/website/size_tier coverage.
  - Commit transaction.
  - Return 0 on success, 1 on error.

  **Key adaptations from old script:**
  - `psycopg.connect(get_dsn())` -> `db_session_manager.get_session(DbSessionType.WRITE)` context manager
  - `conn.execute(sql, params)` with `%s` -> `session.execute(text(sql), params)` with `:param`
  - Integer company IDs -> nanoid string IDs (already stored in company table)
  - Old `companies.id` (integer) -> new `company.id` (string, `co_` prefix)
  - Old `companies.universal_name` -> new `company.universal_name` (same)
  - Old `companies.canonical_name` -> new `company.canonical_name` (same)
  - Add `pdl_id` and `wikidata_id` to the UPDATE statements (new columns from Sub-phase 1)

- **Handle dry-run mode:** When `--dry-run` is set:
  - Still gather targets and build lookup maps (to show target count)
  - Scan PDL file to count potential matches (without applying)
  - Print: target company count, PDL file size, estimated slug/name matches
  - Skip Wikidata entirely (too slow for dry-run)
  - Return 0

- **Error handling:** Wrap entire operation in single transaction. If PDL phase fails, rollback all. If Wikidata phase fails mid-way, the PDL enrichment is still committed (two separate commits or catch Wikidata errors independently). Decision: use a single transaction for PDL, separate transaction for Wikidata (so PDL results persist even if Wikidata API is down). **[OPEN QUESTION: single vs dual transaction]**

**Design review:**
- Spec consistency (`linkedout_data_model.collab.md` > company): All UPDATE targets (`industry`, `website`, `domain`, `founded_year`, `hq_city`, `hq_country`, `employee_count_range`, `estimated_employee_count`, `size_tier`, `enrichment_sources`, `enriched_at`) exist on CompanyEntity. No missing columns (after Sub-phase 1 adds `pdl_id`/`wikidata_id`).
- Spec consistency (`linkedout_enrichment_pipeline.collab.md`): That spec covers Apify profile enrichment, not company enrichment. No conflict -- this is a different enrichment domain (companies, not profiles). The spec's `enrichment_sources` pattern (array of strings) is reused here consistently.
- Naming: `enrich-companies` follows the kebab-case CLI convention. `enrich_companies.py` follows the underscore module convention.
- Architecture: Raw SQL via `sqlalchemy.text()` is appropriate for bulk company updates (same pattern as `classify_roles.py`). Not using ORM for 47K+ COALESCE updates.
- Error paths: PDL file not found -> clear error message with download instructions (ported from old script). Wikidata API down -> partial enrichment (PDL still applied). Rate limiting -> 0.3s delay between searches (ported from old script constants).
- Security: PDL CSV is a local file read (no user input in path unless CLI arg). Wikidata queries use parameterized QIDs in SPARQL VALUES clause, not string interpolation of user input.
- Data integrity: COALESCE semantics mean enrichment never overwrites existing data. The `enrichment_sources` array check prevents duplicate enrichment runs. Both patterns are proven from the old script.

## Sub-phase 4: CLI Wiring, Spec Updates, and End-to-End Verification

**Outcome:** `rcv2 db enrich-companies` is a working CLI command with `--dry-run`, `--skip-wikidata`, `--pdl-file`, `--wikidata-limit`, and `--force` options. CLI spec and data model spec are updated. Full pipeline run completes successfully on dev data.

**Dependencies:** Sub-phase 3

**Estimated effort:** 0.5 session (~1 hour)

**Verification:**
```bash
# CLI help
rcv2 db enrich-companies --help

# Dry run
rcv2 db enrich-companies --dry-run

# PDL only
rcv2 db enrich-companies --skip-wikidata

# Full waterfall
rcv2 db enrich-companies

# Idempotent rerun
rcv2 db enrich-companies  # should show 0 new enrichments

# Coverage check
psql $DATABASE_URL -c "
  SELECT
    COUNT(*) AS total,
    COUNT(industry) AS with_industry,
    COUNT(website) AS with_website,
    COUNT(size_tier) AS with_size_tier,
    COUNT(CASE WHEN 'pdl' = ANY(enrichment_sources) THEN 1 END) AS pdl_enriched,
    COUNT(CASE WHEN 'wikidata' = ANY(enrichment_sources) THEN 1 END) AS wd_enriched
  FROM company;
"

# Integration tests for enrichment script
pytest tests/dev_tools/test_enrich_companies.py -v

# All tests still pass
rcv2 test all
```

Key activities:

- Add the `db enrich-companies` command to `src/dev_tools/cli.py`:
  ```python
  @db.command(name='enrich-companies')
  @click.option('--dry-run', is_flag=True, help='Show enrichment targets without writing')
  @click.option('--skip-wikidata', is_flag=True, help='PDL enrichment only, skip Wikidata API')
  @click.option('--pdl-file', type=click.Path(exists=True), default=None, help='Path to PDL companies CSV')
  @click.option('--wikidata-limit', type=int, default=500, help='Max companies to search on Wikidata')
  @click.option('--force', is_flag=True, help='Re-enrich all companies regardless of prior enrichment')
  def db_enrich_companies(dry_run, skip_wikidata, pdl_file, wikidata_limit, force):
      """Enrich companies with metadata from PDL dataset + Wikidata API."""
      from dev_tools.enrich_companies import main as enrich_main
      exit_code = enrich_main(dry_run=dry_run, skip_wikidata=skip_wikidata,
                              pdl_file=pdl_file, wikidata_limit=wikidata_limit, force=force)
      if exit_code != 0:
          sys.exit(exit_code)
  ```
- Add backward-compatible alias: `enrich_companies_command = db_enrich_companies`
- Update CLI Commands spec (`docs/specs/cli_commands.collab.md`):
  - Add `src/dev_tools/enrich_companies.py`, `src/dev_tools/company_utils.py`, `src/dev_tools/wikidata_utils.py` to `linked_files`
  - Add `db enrich-companies` behavior entry under DB Group:
    ```
    - **db enrich-companies**: Given company rows with missing metadata (industry, website, size, HQ). Running the command enriches companies via a waterfall: PDL free dataset (slug+name match) then Wikidata SPARQL (gap-fill for remaining). Uses COALESCE to never overwrite existing data. Verify `--dry-run` reports target counts without writing, `--skip-wikidata` runs PDL only, `--force` re-enriches all companies, and `--wikidata-limit N` caps Wikidata searches.
    ```
  - Bump version
  - Delegate: `/taskos-update-spec` with the above. Review output.
- Update data model spec (`docs/specs/linkedout_data_model.collab.md`) if not already done in Sub-phase 1.
- **Add integration tests** for `enrich_companies.py` in `tests/dev_tools/test_enrich_companies.py` (3-4 tests against test PostgreSQL):
  - **Dry-run writes nothing:** Call `main(dry_run=True, ...)` with a small test PDL CSV fixture (3-5 companies). Verify DB is unchanged after.
  - **Basic enrichment populates columns:** Call `main(dry_run=False, skip_wikidata=True, pdl_file=fixture_csv)` with fixture containing known slug matches. Verify `industry`, `website`, `estimated_employee_count`, `size_tier` are populated on matched companies. Verify `enrichment_sources` contains `'pdl'`.
  - **Idempotency:** Run enrichment twice. Verify second run produces 0 new enrichments (enrichment_sources check prevents re-enrichment). Verify data is unchanged.
  - **COALESCE semantics:** Pre-populate a company with `industry='Technology'`. Run enrichment where PDL has a different industry. Verify the existing industry is NOT overwritten.
  - Use a small CSV fixture file (5-10 rows) created in `tests/dev_tools/fixtures/pdl_test_companies.csv`. No real PDL data needed.
- Run `precommit-tests` to confirm nothing is broken.
- Run the full enrichment on dev data and spot-check results.

**Design review:**
- Spec consistency: Adding to DB Group follows established pattern. The behavior description uses Given/Running/Verify format.
- Naming: `enrich-companies` is kebab-case, consistent with `classify-roles`, `fix-none-names`, etc.
- Architecture: Lazy import pattern matches all other db commands. CLI options match the old argparse flags.
- Test coverage: Integration tests cover the 4 most dangerous failure modes (dry-run safety, basic correctness, idempotency, COALESCE data safety).
- No flags.

## Build Order

```
Sub-phase 1 (Schema Extension) ──┐
                                  ├──> Sub-phase 3 (Core Script) ──> Sub-phase 4 (CLI + E2E)
Sub-phase 2 (Utility Functions) ──┘
```

**Critical path:** Sub-phase 2 -> Sub-phase 3 -> Sub-phase 4 (Sub-phase 1 is parallel with Sub-phase 2 but must complete before Sub-phase 3)

Sub-phases 1 and 2 are independent and can run in parallel.

### Cross-Phase Execution Order

This is **Phase 2 of 3**. Runs after Phase 1's V1 Pipeline Gate (Sub-phase 4) confirms baseline scores exist. Populates `estimated_employee_count` on 47K companies, which directly feeds Phase 3's company-size normalized career overlap. Phase 3 (Affinity V2) runs after this completes.

**Prerequisite gate:** Phase 1 Sub-phase 4 (V1 Pipeline) must have exited 0 for all three commands (`classify-roles`, `backfill-seniority`, `compute-affinity`).

```
Phase 1: Classify Roles ──> V1 Pipeline GATE ──> Phase 2: Company Enrichment ──> Phase 3: Affinity V2 ──> Run V2 + Eyeball Session
                                                         ^^^^ YOU ARE HERE
```

## Design Review Flags

| Sub-phase | Flag | Action |
|-----------|------|--------|
| Sub-phase 1 | `pdl_id` and `wikidata_id` columns not in current entity or spec | Add columns via migration + update data model spec |
| Sub-phase 2 | `cleanco` is not in `requirements.txt` | Add `cleanco` to requirements.txt |
| Sub-phase 2 | `size_tier` values: old script uses 4, spec says 5 | RESOLVED: Use 5 tiers (tiny/small/mid/large/enterprise). Define breakpoints during implementation. |
| Sub-phase 3 | Old script uses `psycopg` `%s` params; new script needs `sqlalchemy.text()` `:param` syntax | Systematic find-replace of param style in ported SQL |
| Sub-phase 3 | Old script uses integer `companies.id`; new schema uses nanoid string `company.id` | No code change needed -- SQL queries work on both types, but verify JOIN/WHERE clauses |
| Sub-phase 3 | `pandas` is used for chunked CSV reading -- verify it's in requirements.txt | RESOLVED: Use csv.DictReader + islice instead. No pandas dependency. |
| Sub-phase 3 | PDL file path default needs adaptation from second-brain layout | RESOLVED: Required --pdl-file CLI flag, no default/env var. |
| Sub-phase 3 | Transaction strategy: single vs dual (PDL + Wikidata separate) | RESOLVED: Two transactions. PDL commits first, Wikidata separate. |

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| PDL CSV file is large (~2GB) and slow to scan | Med | Uses `csv.DictReader` with `itertools.islice` chunking (no pandas). First run may take 5-10 minutes for a 2GB file. Monitor timing — if too slow, consider pre-filtering the CSV or indexing by slug. |
| Wikidata API rate-limits or goes down | Low | 0.3s delay between searches. `--skip-wikidata` flag allows PDL-only enrichment. Wikidata is supplementary -- PDL is primary. |
| `cleanco` Python package has compatibility issues with current Python version | Low | `cleanco` is a stable, well-maintained package. Pin to latest version. If issues, the `normalize_company_name()` function can be replaced with a simple regex strip of common suffixes. |
| PDL slug matching has low hit rate due to schema differences (old used raw profiles, new uses extracted `universal_name`) | Med | The old script's spike showed viable match rates. Run `--dry-run` first to verify match rate before committing. The `universal_name` column on `company` contains the same slug data. |
| Existing data in `enrichment_sources` column uses different format than expected | Med | Check current DB state: `SELECT DISTINCT unnest(enrichment_sources) FROM company WHERE enrichment_sources IS NOT NULL`. If non-empty, verify the `'pdl' = ANY(...)` check is compatible. |
| COALESCE-based UPDATE leaves stale data if PDL/Wikidata has better info than existing values | Low | By design -- enrichment never overwrites. The `--force` flag re-runs but still uses COALESCE. If overwrite is needed, it requires a manual SQL UPDATE. This is intentional data safety. |

## Open Questions

- **size_tier value reconciliation:** ~~RESOLVED~~ Use 5 tiers (`tiny, small, mid, large, enterprise`) as the spec defines. Define exact breakpoints during implementation. The old script's 4 tiers were a simplification.

- **Transaction strategy for PDL vs Wikidata:** ~~RESOLVED~~ Two separate transactions — PDL commits first, then Wikidata separately. PDL is high-value local data; Wikidata is a flaky live API. Don't risk losing PDL results.

- **PDL file location convention:** ~~RESOLVED~~ Required `--pdl-file` CLI flag, no default path or env var. This is a rare enrichment run — explicit flag is clearer than indirection.

- **pandas dependency:** ~~RESOLVED~~ Use Python's built-in `csv.DictReader` with `itertools.islice` chunking. No pandas. The only feature needed is chunked reading, which is trivial without it.

## Spec References

| Spec | Sections Referenced | Conflicts Found |
|------|---------------------|-----------------|
| `linkedout_data_model.collab.md` | company table definition, BaseEntity fields, enrichment_sources | 1 -- `pdl_id` and `wikidata_id` columns missing from entity and spec. Resolved by Sub-phase 1 migration. |
| `linkedout_data_model.collab.md` | company > size_tier | 1 -- spec comment says 5 tiers (`tiny, small, mid, large, enterprise`) but old script uses 4 tiers (`tiny, mid, large, enterprise`). See Open Questions. |
| `cli_commands.collab.md` | DB Group, linked_files, Exit codes | None -- new command follows established pattern. Spec update needed in Sub-phase 4. |
| `linkedout_enrichment_pipeline.collab.md` | Enrichment tracking, enrichment_sources pattern | None -- that spec covers profile enrichment via Apify, not company enrichment. The `enrichment_sources` array pattern is reused consistently. |
