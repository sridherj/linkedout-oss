# Plan: Port classify-roles + Audit Second-Brain Leverage

## Context

Three dev-tools commands exist (`fix-none-names`, `backfill-seniority`, `compute-affinity`). The `backfill-seniority` command is blocked because `role_alias` has 0 rows. The old `second-brain/linkedin-intel` project already solved this — `classify_roles.py` produced 36K role aliases with 80% classification coverage. We need to port it to the new linkedout schema.

While investigating, we discovered that `second-brain/docs/execution/` contains significant completed work across 12+ execution folders that hasn't been leveraged in the linkedout project.

---

## Part 1: Port classify-roles

### What exists already

**Old script:** `<prior-project>/linkedin-intel/scripts/classify_roles.py` (200 lines)
- 10 seniority regex rules (c_suite → mid), 11 function regex rules (data → consulting)
- First-match-wins strategy, order is critical
- 75 parameterized tests verified it
- Produced 36K role_alias rows, 80% classification rate on 45K unique titles

**New schema differences:**
| Old | New |
|-----|-----|
| `role_aliases` | `role_alias` (MVCS: id prefix `ra`, is_active, version, timestamps) |
| `experiences` | `experience` (same columns: position, seniority_level, function_area) |
| `profiles` | `crawled_profile` (current_position, seniority_level, function_area) |
| raw psycopg | `db_session_manager` + `sqlalchemy.text()` |

**Existing CRUD stack:** RoleAliasEntity, Repository (get_by_alias_title), Service (create_role_aliases_bulk), Controller — all wired and functional. Just no data.

### Implementation

#### File 1: `src/dev_tools/classify_roles.py` (~180 lines)

Copy regex rules verbatim from old script. Pure functions `classify_seniority()` and `classify_function()` unchanged.

**`main(dry_run=False)` — 5 steps:**

| Step | What | SQL approach |
|------|------|-------------|
| 1 | Fetch distinct titles from `experience.position` UNION `crawled_profile.current_position` | Single SELECT DISTINCT |
| 2 | Classify each title in Python (pure regex, no DB) | In-memory loop |
| 3 | INSERT into `role_alias` with ON CONFLICT | Raw SQL, batched, generate `ra_` nanoid IDs |
| 4 | UPDATE `experience.seniority_level/function_area` via temp table JOIN | CREATE TEMP TABLE + bulk INSERT + UPDATE JOIN |
| 5 | UPDATE `crawled_profile` from current experience + direct role_alias fallback | Two UPDATE statements |

**Design choices:**
- Raw SQL with `sqlalchemy.text()` (not ORM) — 40K+ inserts need speed. Matches `seed_companies.py` pattern.
- Source from BOTH tables — `backfill_seniority` needs `crawled_profile.current_position` values in role_alias
- Include Steps 4-5 (experience + crawled_profile updates) — the old script did this in one pass, much more efficient than N+1 lookups in `backfill_seniority`
- Dry-run mode: Steps 1-2 only, prints stats and distribution preview

#### File 2: CLI wiring in `src/dev_tools/cli.py` (~10 lines)

```python
@db.command(name='classify-roles')
@click.option('--dry-run', is_flag=True, help='Classify and report only, do not write')
def db_classify_roles(dry_run):
    """Classify titles into seniority/function, populate role_alias, update experience + crawled_profile."""
    from dev_tools.classify_roles import main as classify_main
    exit_code = classify_main(dry_run=dry_run)
    if exit_code != 0:
        sys.exit(exit_code)
```

Plus alias: `classify_roles_command = db_classify_roles`

#### File 3: `tests/dev_tools/test_classify_roles.py` (~120 lines)

Port all 75 test cases as parametrized pytest. Pure-function tests, zero DB dependency.
- ~41 seniority cases (covering all 10 levels + ordering edge cases)
- ~34 function cases (covering all 11 areas + ordering edge cases)
- Key ordering tests: "Senior Manager" → manager, "Data Scientist" → data (not research), "Founder & CEO" → c_suite

### Verification

```bash
# 1. Unit tests
pytest tests/dev_tools/test_classify_roles.py -v

# 2. Dry run
rcv2 db classify-roles --dry-run

# 3. Real run
rcv2 db classify-roles

# 4. Verify downstream
rcv2 db backfill-seniority --dry-run   # should show matches now
rcv2 db compute-affinity --dry-run     # confirm ready

# 5. DB spot-check
psql $DATABASE_URL -c "SELECT COUNT(*) FROM role_alias;"
psql $DATABASE_URL -c "SELECT seniority_level, COUNT(*) FROM role_alias WHERE seniority_level IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;"
```

### Critical files
- **Source of truth (regex rules):** `<prior-project>/linkedin-intel/scripts/classify_roles.py`
- **New script:** `./src/dev_tools/classify_roles.py`
- **CLI:** `./src/dev_tools/cli.py`
- **Tests:** `./tests/dev_tools/test_classify_roles.py`
- **ID generation:** `shared.common.nanoids.Nanoid.make_nanoid_with_prefix('ra')`
- **DB session:** `shared.infra.db.db_session_manager` (DbSessionType.WRITE)

---

## Part 2: Second-Brain Leverage Audit

### Decisions Made

| # | Item | Decision | Reason |
|---|------|----------|--------|
| 1 | Role classification | **Yes, port now** | Unblocks seniority search + backfill-seniority + compute-affinity |
| 2 | Company enrichment (PDL+Wikidata) | **Yes, port next** | 47K companies with 0% industry/website/HQ — biggest metadata gap |
| 3 | External contact signal in affinity | **Yes, enhance AffinityScorer** | Data already in `connection.sources` (google_contacts). No API needed — comes via CSV import. Extend for Office/iCloud too. |
| 4 | Company normalization | **Skip** | 0 name/URL duplicates — import pipeline already handles this |
| 5 | ATS job parser | **Deferred** | Only if actively needed for opportunity tracking |

### Affinity Scoring Gap (Item 3 detail)

**Current state:**
- `AffinityScorer` uses 3 signals: `source_count * 0.375 + recency * 0.375 + career_overlap * 0.25`
- `source_count` = `len(connection.sources)` — treats all sources equally
- `connection.sources` already has: `linkedin_csv` (24K), `google_contacts` (3.2K), both (384)

**Old spec** (`second-brain/docs/specs/taskos_linkedin_ai.collab.md`):
- Weighted: `career_overlap * 0.5 + external_contact * 0.3 + embedding_similarity * 0.2`
- Dunbar tiers: layer_1 (top 5), layer_2 (top 15), layer_3 (top 50), layer_4 (rest)

**What's missing:**
- No `external_contact_score` signal — connections from `google_contacts` should get a warmth bonus
- `contact_source` table exists (has email, phone columns) but 0 rows — future imports will populate it
- No distinction between email-only contacts, phone contacts, or both (phone = higher affinity)
- Not extensible for `office_contacts`, `icloud_contacts` etc.

**Old script reference:** `<prior-project>/linkedin-intel/scripts/compute_affinity.py` — batch career overlap with company-size normalization (uses `log2(employee_count + 2)` dampening). More sophisticated than current linkedout scorer.

**Action:** Enhance `AffinityScorer` to add external contact signal. Separate task from classify-roles — plan after running all 3 commands.

### What's Already Ported

| Work | Second-Brain Source | LinkedOut Status |
|------|-------------------|-----------------|
| Affinity scoring | `linkedin_intel_phase3a/phase2c_affinity` | Ported as `AffinityScorer` (but missing external contact signal) |
| Embeddings generation | `linkedin_intel_phase3a/phase2a_embeddings` | Ported as `generate_embeddings.py` in dev_tools |
| Search vector (tsvector) | `linkedin_intel_phase3a/phase2b_search_vector` | Ported in crawled_profile entity |
| Query engine / search agent | `linkedin_intel_phase3a/phase3b_query_engine` + `linkedin_intel_phase4` | Ported as `SearchAgent` in `src/linkedout/intelligence/` |
| LLM client | `linkedin_intel_phase3a/phase1_llm_client` | Ported as `LLMManager` in `src/utilities/` |
| Discovery pipeline | `discovery_pipeline/*` | Running via `taskos-startup-pipeline` agent (systemd timer) |

### Execution Order

1. **Now:** Port classify-roles (Part 1 of this plan) → run backfill-seniority → run compute-affinity
2. **Next:** Port company enrichment (PDL + Wikidata) — fills 47K companies' industry/website/HQ
   - Dependencies to port with it: `company_utils.py` (cleanco suffix strip, subsidiary resolution, size tiers), `wikidata_utils.py` (Wikidata API + SPARQL wrapper)
   - Reference spikes: `spike_pdl_match.py` (slug extraction), `spike_wikidata.py` (field completeness benchmarks)
3. **Then:** Enhance AffinityScorer with external contact signal + company-size normalization
4. **Deferred:** ATS job parser, news enrichment, growth signals

### Scripts inventory (second-brain/linkedin-intel/scripts/)

| Script | Status | Notes |
|--------|--------|-------|
| `classify_roles.py` + tests | **Porting now** (Part 1) | |
| `enrich_companies.py` | **Port next** (item 2) | PDL slug + Wikidata SPARQL waterfall |
| `company_utils.py` | **Port with enrichment** | cleanco, subsidiary map, size tiers |
| `wikidata_utils.py` | **Port with enrichment** | Wikidata search + SPARQL batch |
| `spike_pdl_match.py` | Reference only | Slug extraction regex reusable |
| `compute_affinity.py` | **Reference for item 3** | Company-size normalization via log2 |
| `enrich_affinity_gmail.py` | **Reference for item 3** | RapidFuzz 85% threshold, multi-match disambig |
| `normalize_companies.py` | Skip | UnionFind clustering — not needed (0 dupes) |
| `bulk_load.py` | Skip | COPY protocol — nice perf optimization, not urgent |
| `extract_relations.py` | Already covered | Similar to `load_apify_profiles.py` |
| `generate_embeddings.py` | Already ported | `dev_tools/generate_embeddings.py` |
| `add_search_vector.py` | Already ported | In crawled_profile entity |
| `load_csv.py` | Already covered | Similar to import pipeline |
| `llm_client.py` | Already ported | `LLMManager` in utilities |
| `query_engine.py` | Already ported | `SearchAgent` in intelligence |
