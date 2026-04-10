# Sub-Phase 4: CLI Wiring, Spec Updates, and End-to-End Verification (GATE)

**Goal:** linkedin-ai-production
**Phase:** 2 — Company Enrichment
**Depends on:** SP-3 (Core Enrichment Script)
**Estimated effort:** 1h
**Source plan section:** Sub-phase 4
**Gate:** This sub-phase is the Phase 2 GATE. Must pass before Phase 3 (Affinity V2) begins.

---

## Objective

Wire `enrich_companies.main()` to the `rcv2 db enrich-companies` CLI command. Update CLI and data model specs. Write integration tests. Run full E2E verification on dev data.

## Context

- **Code directory:** `./`
- **CLI pattern:** See existing `db` group commands in `src/dev_tools/cli.py` (e.g., `classify-roles`, `fix-none-names`)
- **Spec update tool:** `/taskos-update-spec`
- All CLI commands use kebab-case. Module names use underscores.

## Pre-Flight Checks

Before starting, verify:
- [ ] SP-3 completed: `from dev_tools.enrich_companies import main` works
- [ ] Existing CLI commands work: `rcv2 db --help` lists current commands
- [ ] Test fixtures directory exists: `tests/dev_tools/fixtures/` (or create it)

## Files to Create/Modify

```
./
├── src/dev_tools/cli.py                                    # ADD: db enrich-companies command
├── docs/specs/cli_commands.collab.md                       # UPDATE: add enrich-companies (via /taskos-update-spec)
├── docs/specs/linkedout_data_model.collab.md               # VERIFY: pdl_id/wikidata_id added in SP-1
├── tests/dev_tools/test_enrich_companies.py                # NEW: integration tests
└── tests/dev_tools/fixtures/pdl_test_companies.csv         # NEW: small test fixture (5-10 rows)
```

---

## Step 1: Add CLI Command

**Tasks:**
1. Open `src/dev_tools/cli.py`
2. Add the `db enrich-companies` command under the `db` group:
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
3. Follow the lazy import pattern (import inside the function, not at top of file).

**Verify:**
```bash
rcv2 db enrich-companies --help
```
Should show all options with descriptions.

## Step 2: Update CLI Commands Spec

**Tasks:**
1. Delegate to `/taskos-update-spec` with these changes to `docs/specs/cli_commands.collab.md`:
   - Add to `linked_files`: `src/dev_tools/enrich_companies.py`, `src/dev_tools/company_utils.py`, `src/dev_tools/wikidata_utils.py`
   - Add behavior entry under DB Group:
     ```
     - **db enrich-companies**: Given company rows with missing metadata (industry, website, size, HQ). Running the command enriches companies via a waterfall: PDL free dataset (slug+name match) then Wikidata SPARQL (gap-fill for remaining). Uses COALESCE to never overwrite existing data. Verify `--dry-run` reports target counts without writing, `--skip-wikidata` runs PDL only, `--force` re-enriches all companies, and `--wikidata-limit N` caps Wikidata searches.
     ```
   - Bump version
2. Review the spec update output.

## Step 3: Verify Data Model Spec

**Tasks:**
1. Confirm `docs/specs/linkedout_data_model.collab.md` has `pdl_id` and `wikidata_id` columns (should have been added in SP-1).
2. If not present, delegate to `/taskos-update-spec` to add them.

## Step 4: Create Test Fixture

**Tasks:**
1. Create `tests/dev_tools/fixtures/pdl_test_companies.csv` with 5-10 rows of synthetic PDL data:
   - Include columns matching `PDL_COLUMNS` from the enrichment script
   - Include at least 2 rows with LinkedIn URLs matching known test company slugs
   - Include at least 1 row with a company name match (no slug match)
   - Include at least 2 rows that should NOT match any company in test DB

## Step 5: Write Integration Tests

**Tasks:**
Create `tests/dev_tools/test_enrich_companies.py`:

1. **`test_dry_run_writes_nothing`**
   - Set up: insert 2-3 test companies in DB
   - Call `main(dry_run=True, skip_wikidata=True, pdl_file=fixture_csv)`
   - Assert: DB state unchanged (no enrichment_sources, no pdl_id)

2. **`test_basic_enrichment_populates_columns`**
   - Set up: insert companies with `universal_name` matching fixture slugs
   - Call `main(dry_run=False, skip_wikidata=True, pdl_file=fixture_csv)`
   - Assert: matched companies have `industry`, `website`, `estimated_employee_count`, `size_tier` populated
   - Assert: `enrichment_sources` contains `'pdl'`
   - Assert: `pdl_id` is set

3. **`test_idempotency`**
   - Run enrichment twice with same fixture
   - Assert: second run produces 0 new enrichments
   - Assert: data unchanged between runs

4. **`test_coalesce_does_not_overwrite`**
   - Set up: insert company with `industry='Technology'` already set
   - Run enrichment where fixture has a different industry for that company
   - Assert: `industry` is still `'Technology'` (NOT overwritten)

**Verify:**
```bash
pytest tests/dev_tools/test_enrich_companies.py -v
```

## Step 6: End-to-End Verification

**Tasks:**
Run the full pipeline on dev data and verify:

```bash
# 1. CLI help
rcv2 db enrich-companies --help

# 2. Dry run
rcv2 db enrich-companies --dry-run --pdl-file /path/to/pdl/companies.csv

# 3. PDL only
rcv2 db enrich-companies --skip-wikidata --pdl-file /path/to/pdl/companies.csv

# 4. Full waterfall (if Wikidata access available)
rcv2 db enrich-companies --pdl-file /path/to/pdl/companies.csv

# 5. Idempotent rerun
rcv2 db enrich-companies --pdl-file /path/to/pdl/companies.csv
# Should show 0 new enrichments

# 6. Coverage check
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
```

## Step 7: Run Full Test Suite

**Tasks:**
```bash
# Integration tests
pytest tests/dev_tools/test_enrich_companies.py -v

# All tests still pass
rcv2 test all
```

---

## Gate Criteria

This is the **Phase 2 GATE**. All of the following must be true before Phase 3 (Affinity V2) begins:

- [ ] `rcv2 db enrich-companies --help` shows all options
- [ ] `rcv2 db enrich-companies --dry-run` exits 0
- [ ] `rcv2 db enrich-companies --skip-wikidata` enriches companies via PDL
- [ ] `rcv2 db enrich-companies` runs full waterfall (PDL + Wikidata)
- [ ] Idempotent rerun shows 0 new enrichments
- [ ] Coverage improved: `industry IS NOT NULL` count increased
- [ ] Coverage improved: `size_tier IS NOT NULL` count increased
- [ ] `pytest tests/dev_tools/test_enrich_companies.py -v` — all pass
- [ ] `rcv2 test all` — no regressions
- [ ] CLI spec updated
- [ ] Data model spec has `pdl_id` and `wikidata_id`

## Verification Checklist

- [ ] CLI command registered and shows correct help
- [ ] Dry-run writes nothing to DB
- [ ] Basic enrichment populates expected columns
- [ ] COALESCE semantics protect existing data
- [ ] Idempotency works
- [ ] Integration tests pass
- [ ] Full test suite passes
- [ ] Specs updated
- [ ] Gate criteria met
