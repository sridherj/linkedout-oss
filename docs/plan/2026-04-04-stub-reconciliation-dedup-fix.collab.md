# Plan: Fix Affinity Scoring — Stub Dedup + Seniority-Aware Career Overlap

## Context

Two compounding issues cause close colleagues like Nabhan (4 years at Crio.Do, in phone contacts) to score 21.3 and land in "acquaintance" tier:

1. **Stub dedup gap:** 3,196 Google Contact connections exist as separate stubs, not merged into LinkedIn connections. External_contact signal (25% weight) is stranded on the stub.
2. **Career overlap formula ignores seniority:** A co-founder at a 350-person company gets the same size_factor (0.118) as an intern. But a founder knows everyone; an intern knows their team. Nabhan's 46 months of concurrent employment at Crio.Do contributes only 6 points out of 100.

## Data Analysis

**Why stubs exist:** Phone contacts have no LinkedIn URL and usually no email. Dedup stages (URL → email → fuzzy name+company) all fail because phone contacts lack URLs, emails, and company info.

**Stub breakdown (1,152 stubs with phone numbers, first_name >= 3 chars):**

| Bucket | Count | Description | Can match? |
|--------|-------|-------------|------------|
| A: No LinkedIn match | 463 | First name doesn't exist in LinkedIn connections | No — genuinely non-LinkedIn contacts |
| B: Unique fname, no lname | 55 | "Ananya" → 1 LinkedIn "Ananya Bhuyan" | Yes, safe (unique) |
| C: Unique fname + has lname | 72 | "Amod Malviya" → 1 LinkedIn match | Yes, safe (unique + can verify lname) |
| D: Few fnames (2-5) + has lname | 110 | "Amrita MMT" → 3 LinkedIn "Amrita"s | Maybe — lname is often a company hint |
| E: Few fnames, no lname | 66 | "Akhilesh" → 3 LinkedIn matches | Risky — can't disambiguate |
| F: Too many (>5) | 386 | "Abhishek Myntra" → 220 LinkedIn "Abhishek"s | No — too ambiguous |

**Quality issues in contact names:** "last names" are often company labels ("PhonePe", "Crio", "Myntra"), tags ("ExFK", "PDP", "TA"), or junk ("Friend)", "(GS)"). Real last names are rare.

**False positive risk:** Exact first+last name match only found 3 stubs (including yourself) — contact "last names" almost never match LinkedIn last names. So first_name uniqueness is the main viable signal.

## Proposed Approach: 3-Tier Post-Dedup Reconciliation

Rather than complicating the import-time dedup pipeline, add a **reconciliation pass** that runs after import to merge stubs into LinkedIn connections. This is cleaner because:
- Import dedup stays simple and fast
- Reconciliation can use richer signals (experience data, embeddings)
- Can run as one-time fix AND on future imports

### Tier 1: Unique first-name match (Buckets B+C = ~127 stubs)

**Logic:** If a stub's `first_name` matches **exactly 1** LinkedIn connection's `first_name`:
- Match with `confidence = 0.70`
- If stub also has a last_name that matches LinkedIn last_name: `confidence = 0.95`

**False positive risk:** Moderate — uniqueness within LinkedIn eliminates ambiguity between connections, but doesn't prove the phone contact IS a LinkedIn connection. The contact "Aalvi" with phone +91... could be a different Aalvi not on LinkedIn. However, the cost of a false merge is low (the stub gains career data it shouldn't have, but the LinkedIn connection just gains a phone number), and the benefit for true matches is high (external_contact signal worth 25% of affinity score). Confidence set to 0.70 to reflect this uncertainty.

### Tier 2: First-name + company-hint disambiguation (Bucket D = ~110 stubs)

**Logic:** For stubs where 2-5 LinkedIn connections share the first name AND the stub has a "last name" that looks like a company:
- Check if the stub's last_name (e.g., "Crio", "PhonePe") fuzzy-matches any of the LinkedIn candidates' `current_company_name` or experience company names
- If exactly 1 candidate matches: merge with `confidence = 0.75`

**Example:** "Bhavani Sivakumar" has 3 LinkedIn "Bhavani"s. Check if any work/worked at a company matching "Sivakumar" — one works at "Crio.Do" so that doesn't help. But "Anurup Crio" → check LinkedIn "Anurup"s → one works at Crio.Do → match.

**False positive risk:** Medium — company matching helps but isn't perfect. Also, stub "last names" that look like companies could actually be real surnames (e.g., "Sivakumar"). Need a heuristic: if the stub last_name matches any `company.canonical_name` in DB → treat as company hint; otherwise treat as real last name and attempt exact match against LinkedIn last names.

### Tier 3: Skip (Buckets A, E, F = ~915 stubs)

Leave unmatched. These are either non-LinkedIn contacts (A), too ambiguous (E, F), or will need manual resolution.

### Implementation

**One-time reconciliation script:** `src/dev_tools/reconcile_stubs.py`

```
1. Load all stub connections with phones
2. Load all LinkedIn connections with first_name index
3. For each stub:
   a. Tier 1: unique first_name → merge
   b. Tier 2: few first_names + company hint → merge  
   c. Skip otherwise
4. For each merge (ORDER MATTERS):
   a. Log merge to reconciliation_log (stub snapshot for rollback)
   b. Update contact_source records to point to LinkedIn connection (FK first!)
   c. Move phones, emails, source_details from stub to LinkedIn connection
   d. Add 'google_contacts' to LinkedIn connection's sources array
   e. Soft-delete the stub connection + stub crawled_profile
5. Auto-trigger affinity recompute for the user (call `AffinityScorer.compute_for_user`)
```

**Future imports:** After each Google Contacts import completes, auto-trigger reconciliation for the importing user. This is a post-import hook in `ImportService.process_import()`, NOT an inline dedup stage — reconciliation runs after all dedup + merge is done, against the freshly created stubs.

### Key files

| File | Change |
|------|--------|
| `src/dev_tools/reconcile_stubs.py` | New: reconciliation logic (Tier 1 + Tier 2 matching, name-swap preprocessing) |
| `src/dev_tools/cli.py` | Add `reconcile-stubs` CLI command with `--dry-run` and `--user-id` |
| `src/linkedout/import_pipeline/merge.py` | Add `merge_stub_into_connection` function (move phones/emails/sources, repoint contact_sources, soft-delete stub) |
| `src/linkedout/import_pipeline/service.py` | Add post-import reconciliation hook (auto-trigger after Google Contacts imports) |

### Rollback & Audit

Every merge must be logged to a `reconciliation_log` (JSON file or DB table) with:
- `stub_connection_id`, `target_connection_id`, `tier`, `confidence`, `stub_snapshot` (phones, emails, full_name)
- This allows reversing any merge: restore the stub, repoint contact_sources, remove the merged data from the LinkedIn connection

### Name-swap preprocessing

Before matching, detect when a stub's `first_name` looks like a company name (check against `company.canonical_name` in DB). If it matches a company but `last_name` doesn't, swap first/last. Example: "Crio Nabhan" → first_name="Nabhan", last_name="Crio". This runs as the first step of reconciliation, before Tier 1/2 matching.

### Expected outcomes

- **Tier 1:** ~127 stubs merged (unique first-name matches)
- **Tier 2:** ~30-50 stubs merged (subset of 110 where company-hint resolves to exactly 1 candidate)
- **Total:** ~160-180 merges out of 3,196 stubs (~5%)
- **Remaining:** ~3,000 stubs stay as-is — genuinely non-LinkedIn contacts or too ambiguous

### Open questions

1. **Stubs without phones (2,549 stubs):** These came from `gmail_email_only` / `google_contacts_job` imports. They should have matched via email in dedup Stage 2. Verify no email-bearing stubs slipped through — if they did, it's a bug in the email matching, not a new-stage problem.

### NOT doing (dedup)
- Phone-to-phone matching: LinkedIn connections don't have phones, so no cross-reference possible
- LLM-based matching: overkill for this volume
- Lowering fuzzy name+company threshold: contacts lack company data

---

## Part 2: Seniority-Aware Career Overlap

### Problem

The current `size_factor = 1 / log2(employee_count + 2)` treats everyone at a company equally. But seniority determines how many people you actually know:

| Role | At 350-person company | People you know |
|------|----------------------|-----------------|
| Co-Founder | Everyone | ~350 |
| VP | Cross-functional | ~100 |
| Mid-level IC | Your team | ~15-30 |
| Intern | Immediate team | ~5-10 |

Result: SJ (co-founder) at Crio.Do gets the same size_factor as an intern — 46 months of overlap with Nabhan yields only 6 points.

### Data availability

Seniority data is well-populated: 79% of experiences have `seniority_level` (105K out of 133K). Values: `founder`, `c_suite`, `vp`, `director`, `manager`, `lead`, `senior`, `mid`, `junior`, `intern`. SJ's own experiences have been manually backfilled.

### Approach: Seniority boost multiplier on career_overlap

Apply a multiplier based on the **higher** seniority between user and connection at the shared company. Rationale: if either person is senior, they likely knew the other.

```python
SENIORITY_BOOST = {
    'founder':  3.0,
    'c_suite':  2.5,
    'vp':       2.0,
    'director': 1.8,
    'manager':  1.5,
    'lead':     1.3,
    'senior':   1.1,
    'mid':      1.0,  # baseline — no change
    'junior':   0.9,
    'intern':   0.7,
}

# Per shared-company pair:
boost = max(SENIORITY_BOOST[user_seniority], SENIORITY_BOOST[conn_seniority])
overlap_contribution = overlap_months * size_factor * boost
```

The boost is applied per-company overlap before summing and normalizing. Final career_overlap is still capped at 1.0.

### Impact (Nabhan, 46 months at Crio.Do, 350 employees)

| Scenario | career_overlap | Total score | Tier |
|----------|---------------|-------------|------|
| Current | 0.151 | 20.2 | acquaintance |
| + seniority boost (founder 3x) | 0.453 | 32.3 | familiar |
| + dedup merge (phone contact) | 0.151 | 48.2 | active |
| + both fixes | 0.453 | 60.3 | inner_circle |

### Key files

| File | Change |
|------|--------|
| `src/linkedout/intelligence/scoring/affinity_scorer.py` | Add `SENIORITY_BOOST` map, modify `_compute_career_overlap` to accept seniority data and apply boost per company pair |
| `src/linkedout/intelligence/scoring/affinity_scorer.py` | Update `_batch_fetch_*` to also fetch seniority_level from experience records |
| `tests/unit/intelligence/test_affinity_scorer.py` | Add tests for seniority boost: founder vs intern, missing seniority defaults to 1.0 |

### Edge cases

- **Missing seniority_level (21% of experiences):** Default to `mid` (boost = 1.0, no change from current behavior)
- **Multiple roles at same company:** Use the highest seniority across all overlapping roles
- **Both sides are founders at same company:** boost = 3.0 (max of both, same result)

### NOT doing (scoring)
- Changing the base size_factor curve (`1/log2`) — seniority boost handles the nuance better than flattening the curve for everyone
- Per-function-area proximity scoring (engineering+engineering closer than engineering+sales) — deferred

---

## Verification (combined)

1. **Dry-run reconciliation**: Run with `--dry-run`, report matches with confidence levels
2. **Spot checks**: Verify Ananya, Nabhan, and a sample of Tier 1+2 dedup matches
3. **Affinity recompute**: Run `rcv2 db compute-affinity --user-id usr_sys_001`
4. **Score verification**: Nabhan should reach ~60 (inner_circle), Ananya ~40 (active/familiar)
5. **Unit tests**: Dedup matching logic, seniority boost math, merge function
6. **Regression check**: Verify top-50 connections still look reasonable after seniority boost (no unexpected rank changes)
