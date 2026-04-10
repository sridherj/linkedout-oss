# Sub-Phase 7: Agent Definition Updates

**Goal:** linkedin-ai-production
**Phase:** 2b — Startup Pipeline Compatibility
**Depends on:** SP-4 (DB Layer Updates — shared DB layer must be migrated first)
**Estimated effort:** 6.5h
**Source plan steps:** Steps 9, 10, 11
**Parallel with:** SP-5 (Discovery Path), SP-6 (News Path)

---

## Objective

Update the three startup agents' definitions and code to target the LinkedOut database instead of the lost `linkedin_intel` DB.

## Context

**Agent definitions:** `~/.claude/agents/taskos-startup-discover.md`, `taskos-startup-enrich.md`, `taskos-startup-pipeline.md`
**Pipeline code:** `<prior-project>/agents/pipeline/`

The agents form a connected workflow:
1. `startup-pipeline` — automated daily (systemd), pulls RSS feeds, runs all 7 stages
2. `startup-enrich` — triggered after pipeline or manually, enriches specific companies
3. `startup-discover` — manual ad-hoc, discovers new companies from curated sources

---

## Step 9: Rewrite `startup-discover` Agent (~4h)

The agent currently targets `agents/shared/db.py` (SQLite-style). Rewrite to use the pipeline's PostgreSQL DB layer.

### Changes needed:

1. **Agent definition** (`~/.claude/agents/taskos-startup-discover.md`):
   - Remove all SQLite references (`data/companies.db`)
   - Update to reference LinkedOut's `company` + `startup_tracking` tables
   - Update tool descriptions for new column names

2. **Database operations** — switch from `agents.shared.db` to `agents.pipeline.db` + `agents.pipeline.company_ops`:
   - `add_company()` → `insert_or_match_company()` (returns nanoid `str`)
   - `company_exists()` → `SELECT FROM company WHERE normalized_name = %s`
   - `find_by_normalized_name()` → already exists in `company_ops`
   - `get_company_count()` → `SELECT COUNT(*) FROM company`

3. **New**: After inserting a company, also create/update `startup_tracking` row with `watching = true`, `vertical`, `sub_category` from discovery data.

4. **ID handling**: All company IDs are now nanoid strings, not integers.

5. **Connection**: Use `LINKEDOUT_DSN` env var.

### Verification:
- Run discover agent manually for 2-3 companies
- Companies appear in `company` table with nanoid PKs
- `startup_tracking` rows created with `watching = true`
- No writes to SQLite or `linkedin_intel`

---

## Step 10: Update `startup-enrich` Agent (~2h)

The agent is partially stale — uses correct PostgreSQL path but with old schema.

### Changes needed:

1. **Agent definition** (`~/.claude/agents/taskos-startup-enrich.md`):
   - Update database references from `linkedin_intel` to LinkedOut
   - Update `--company-id` examples from integers to nanoid strings
   - Update vertical taxonomy references (confirm they match `startup_tracking.vertical`)

2. **CLI commands**: Already use `agents.pipeline.enrichment.helpers` which delegates to `db.py` and `company_ops.py` — these are already fixed in SP-4.

3. **Connection**: Inherits from updated `db.py` (`LINKEDOUT_DSN`).

4. **ID handling**: `--company-id` is now `str` (fixed in SP-6 Step 8).

### Verification:
- Run enrich agent for 2-3 test companies
- `funding_round` rows created with `fr_xxx` nanoids
- `growth_signal` rows created with `gs_xxx` nanoids
- `startup_tracking` updated with funding summaries

---

## Step 11: Update `startup-pipeline` Agent (~30 min)

Minimally stale — just needs env var and output format updates.

### Changes needed:

1. **Agent definition** (`~/.claude/agents/taskos-startup-pipeline.md`):
   - Update database references
   - Update env var from `LINKEDIN_INTEL_DSN` to `LINKEDOUT_DSN`

2. **Environment**: Add `LINKEDOUT_DSN` to the systemd unit file or `.env` that the pipeline timer uses.

3. **Output parsing**: If the agent parses stage output for counters, verify formats haven't changed.

### Verification:
- Run `uv run python -m agents.pipeline.run` end-to-end
- All 7 stages complete without error

---

## Completion Criteria

- [ ] `startup-discover` agent definition updated, no SQLite references
- [ ] `startup-enrich` agent definition updated, no `linkedin_intel` references
- [ ] `startup-pipeline` agent definition updated, uses `LINKEDOUT_DSN`
- [ ] All three agents can be invoked without errors
- [ ] Company creation via discover/enrich creates proper nanoid PKs
- [ ] `startup_tracking` rows created with correct `watching` flag

## Verification

```bash
# Quick smoke test for each agent
# discover: invoke for 1 company, check company + startup_tracking tables
# enrich: invoke for 1 company, check funding_round + growth_signal tables
# pipeline: run full pipeline, check all 7 stages complete
```
