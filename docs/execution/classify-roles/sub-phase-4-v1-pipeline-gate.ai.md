# Sub-Phase 4: Run V1 Pipeline (GATE — blocks Phase 2 and Phase 3)

**Goal:** linkedin-ai-production
**Source plan:** 2026-03-28-classify-roles-port-and-wiring.md
**Type:** Pipeline execution + validation gate — no code changes
**Estimated effort:** ~30 minutes
**Dependencies:** Sub-Phase 3 (CLI must be wired)
**Can parallelize with:** Nothing (gate)

---

## Overview

Run the full V1 pipeline: `classify-roles` → `backfill-seniority` → `compute-affinity`. All three must exit 0. This is a **GATE** — Phase 2 (Company Enrichment) and Phase 3 (Affinity V2) MUST NOT proceed until this completes successfully.

---

## GATE CONDITION

**All three commands must exit 0.** If any command fails, Phase 2 and Phase 3 MUST NOT proceed. Diagnose and fix before continuing.

---

## Step 1: Ensure CLI Package is Installed

**What:** Make sure the new command is registered.

**Actions:**
1. Run `uv pip install -r requirements.txt` to ensure the local CLI package from `pyproject.toml` is installed with the new `classify-roles` command

**Verification:**
- [ ] `rcv2 db classify-roles --help` works

---

## Step 2: Run classify-roles

**What:** Populate role_alias and update experience + crawled_profile.

**Actions:**
1. Run `rcv2 db classify-roles` (no `--dry-run`)
2. Verify:
   ```bash
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM role_alias;"
   # Expect ~36K rows
   ```
3. Verify classification rate matches expectations (~80% coverage)

**MUST exit 0 to proceed.**

---

## Step 3: Run backfill-seniority

**What:** Propagate seniority to remaining profiles.

**Actions:**
1. Run `rcv2 db backfill-seniority`
2. Verify:
   ```bash
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM crawled_profile WHERE seniority_level IS NOT NULL;"
   # Expect significant coverage
   ```

**MUST exit 0 to proceed.**

---

## Step 4: Run compute-affinity (V1)

**What:** Produce baseline V1 affinity scores and Dunbar tiers.

**Actions:**
1. Run `rcv2 db compute-affinity`
2. Verify:
   ```bash
   psql $DATABASE_URL -c "SELECT dunbar_tier, COUNT(*) FROM connection WHERE affinity_score IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;"
   # Expect all connections scored with tier distribution
   ```

**MUST exit 0 to proceed.**

---

## Step 5: Spot-Check and Gate Confirmation

**What:** Sanity-check top connections and confirm gate passes.

**Actions:**
1. Query top-15 connections (inner_circle) for the primary user
2. Sanity-check that the ranking makes sense
3. If ALL commands succeeded:
   ```
   echo "V1 pipeline complete. Phase 2 and Phase 3 are unblocked."
   ```

**Verification:**
- [ ] All three pipeline commands exited 0
- [ ] role_alias has ~36K rows
- [ ] crawled_profile has significant seniority coverage
- [ ] All connections have affinity_score and dunbar_tier
- [ ] Top-15 inner circle connections look reasonable

---

## Completion Criteria

- [ ] `rcv2 db classify-roles` — exit 0
- [ ] `rcv2 db backfill-seniority` — exit 0
- [ ] `rcv2 db compute-affinity` — exit 0
- [ ] Baseline V1 scores exist for all connections
- [ ] Gate passes — Phase 2 and Phase 3 are unblocked

---

## If Any Command Fails

1. **Do NOT proceed** to Phase 2 or Phase 3
2. Investigate the error output
3. Fix the issue in the relevant sub-phase
4. Re-run the failed command and all subsequent commands
5. Only declare the gate passed when all three succeed
