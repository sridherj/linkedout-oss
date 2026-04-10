# Sub-Phase 8: Environment Config + E2E Validation

**Goal:** linkedin-ai-production
**Phase:** 2b — Startup Pipeline Compatibility
**Depends on:** SP-5, SP-6, SP-7 (all pipeline code and agent changes must be complete)
**Estimated effort:** 1.5-2.5h
**Source plan steps:** Steps 12, 13

---

## Objective

Configure environment variables for the migrated pipeline and run comprehensive end-to-end validation across all agents and the LinkedOut ORM.

---

## Step 12: Environment Configuration (~30 min)

### Second-brain `.env`:
- Add `LINKEDOUT_DSN=postgresql://user:pass@localhost:5432/linkedout`
- Remove or comment out `LINKEDIN_INTEL_DSN`

### Agent `.env` files (if separate):
- Update any agent-specific env configs

### LinkedOut awareness:
- No changes to LinkedOut's `.env.local` — the pipeline is a separate process
- Document in `docs/reference/startup_pipeline_migration.md` that migration is complete

### Verification:
```bash
# From pipeline context
echo $LINKEDOUT_DSN  # returns valid DSN
```

---

## Step 13: End-to-End Validation (~1-2h)

### Test 1: Full pipeline run
1. Set `LINKEDOUT_DSN` pointing to LinkedOut DB
2. Run `uv run python -m agents.pipeline.run`
3. Verify all 7 stages complete
4. Check tables have data with correct nanoid PKs

### Test 2: Discover agent
1. Run `startup-discover` for 3-5 companies from a YC batch
2. Verify `company` + `startup_tracking` rows

### Test 3: Enrich agent
1. Run `startup-enrich` for 2-3 of the discovered companies
2. Verify `funding_round` + `growth_signal` + `startup_tracking` updates

### Test 4: Pipeline + Enrich flow
1. Run pipeline → identify a new company → enrich it
2. Full workflow validates

### Test 5: LinkedOut CRUD coexistence
1. Call LinkedOut API to list companies: `GET /companies`
2. Verify pipeline-created companies appear via the ORM
3. Create a company via LinkedOut API → verify pipeline can read it

---

## Completion Criteria

- [ ] `LINKEDOUT_DSN` configured in second-brain `.env`
- [ ] `LINKEDIN_INTEL_DSN` removed/commented
- [ ] Migration documentation written
- [ ] Test 1 passes: full pipeline run, all 7 stages complete
- [ ] Test 2 passes: discover agent creates companies with nanoid PKs
- [ ] Test 3 passes: enrich agent creates funding_round + growth_signal rows
- [ ] Test 4 passes: pipeline → discover → enrich flow works end-to-end
- [ ] Test 5 passes: pipeline (raw SQL) and LinkedOut (ORM) coexist on same data

## Verification

```bash
# Final check: all tables have data with correct ID formats
psql -d linkedout -c "
SELECT 'company' as tbl, count(*), left(id, 3) as prefix FROM company GROUP BY 3
UNION ALL
SELECT 'funding_round', count(*), left(id, 3) FROM funding_round GROUP BY 3
UNION ALL
SELECT 'growth_signal', count(*), left(id, 3) FROM growth_signal GROUP BY 3
UNION ALL
SELECT 'startup_tracking', count(*), left(id, 3) FROM startup_tracking GROUP BY 3
UNION ALL
SELECT 'raw_feed_item', count(*), left(id, 4) FROM raw_feed_item GROUP BY 3
UNION ALL
SELECT 'news_article', count(*), left(id, 3) FROM news_article GROUP BY 3
ORDER BY 1;
"
```
