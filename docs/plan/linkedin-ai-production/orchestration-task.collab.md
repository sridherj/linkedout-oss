# Orchestrate: LinkedIn AI Production — Classify Roles + Company Enrichment + Affinity V2

Single `/taskos-orchestrate` invocation that chains all 3 phases with gates between them. The orchestrator stops if any gate fails — no babysitting required.

## Invocation

```
/taskos-orchestrate ./docs/plan/linkedin-ai-production/orchestration-task.md --goal linkedin-ai-production
```

## Phases and Sub-Phases (execute in strict order)

### Phase 1: Classify Roles
**Plan:** `./docs/plan/linkedin-ai-production/2026-03-28-classify-roles-port-and-wiring.md`

| Sub-phase | Description | Dependencies |
|-----------|-------------|--------------|
| SP1 | Pure classification functions + 75 parametrized tests | None |
| SP2 | DB operations — role_alias upsert, experience/profile bulk updates | SP1 |
| SP3 | CLI wiring (`rcv2 db classify-roles`) + precommit-tests | SP2 |
| SP4 | **V1 Pipeline GATE** — run `uv pip install -r requirements.txt` then `classify-roles` → `backfill-seniority` → `compute-affinity`. All must exit 0. | SP3 |

**GATE after SP4:** If any of the 3 CLI commands fails, STOP. Do NOT proceed to Phase 2.

### Phase 2: Company Enrichment
**Plan:** `./docs/plan/linkedin-ai-production/2026-03-28-company-enrichment-port.md`

| Sub-phase | Description | Dependencies |
|-----------|-------------|--------------|
| SP5 | Schema extension — add `pdl_id`, `wikidata_id` to company entity + migration | Phase 1 GATE |
| SP6 | Utility functions — port `company_utils.py` + `wikidata_utils.py` + tests | Phase 1 GATE |
| SP7 | Core enrichment script — `enrich_companies.py` with PDL+Wikidata waterfall | SP5, SP6 |
| SP8 | CLI wiring (`rcv2 db enrich-companies`) + integration tests + precommit-tests | SP7 |

SP5 and SP6 can run **in parallel** (independent).

**GATE after SP8:** Phase 2 must complete fully before Phase 3 starts.

### Phase 3: Affinity V2 Enhancements
**Plan:** `./docs/plan/linkedin-ai-production/2026-03-28-affinity-v2-enhancements.md`

| Sub-phase | Description | Dependencies |
|-----------|-------------|--------------|
| SP9 | Schema migration — `affinity_external_contact`, `affinity_embedding_similarity` on connection + `source_label` on contact_source | Phase 2 GATE |
| SP10 | Company-size normalized career overlap — `log2` dampening + temporal overlap | SP9 |
| SP11a | External contact signal — phone=1.0, email=0.7, cap at highest tier | SP9 |
| SP11b | Embedding similarity signal — pgvector cosine distance | SP9 |
| SP12 | V2 weight revision (0.40/0.25/0.15/0.10/0.10) + spec updates + precommit-tests | SP10, SP11a, SP11b |

SP10, SP11a, SP11b can run **in parallel** (independent signals, no shared files).

## DAG Summary

```
SP1 ──> SP2 ──> SP3 ──> SP4 [V1 GATE] ──> SP5 ──┐
                                          ──> SP6 ──┤──> SP7 ──> SP8 [Phase 2 GATE] ──> SP9 ──> SP10  ──┐
                                                                                                  ──> SP11a ──┤──> SP12
                                                                                                  ──> SP11b ──┘
```

## Pre-Execution Setup

Before ANY sub-phase runner executes CLI commands, it must run:
```bash
cd . && uv pip install -r requirements.txt
```
This registers new Click commands from `pyproject.toml`. Required at minimum before SP4 (V1 pipeline gate).

## Key Decisions (baked into plans, do NOT re-ask)

- `alias_title` stored lowercase for reliable matching
- Two transactions for PDL vs Wikidata (PDL commits first)
- Required `--pdl-file` CLI flag (no default path)
- `csv.DictReader` + `islice` (no pandas dependency)
- 5 size tiers (`tiny`, `small`, `mid`, `large`, `enterprise`)
- External contact: cap at highest tier (phone=1.0, email=0.7, no stacking)
- `source_label` on `contact_source` (`google_personal`, `google_work`, `icloud`, `office365`)
- V2 weights: `career_overlap * 0.40 + external_contact * 0.25 + embedding_similarity * 0.15 + source_count * 0.10 + recency * 0.10`
- Embeddings are 1536-dim `text-embedding-3-small` (not 768-dim nomic)
- `EXTERNAL_SOURCE_TYPES` = `['google_contacts_job', 'gmail_email_only', 'contacts_phone']`

## Reference Files (absolute paths)

### Phase plan documents
| File | Phase |
|------|-------|
| `./docs/plan/linkedin-ai-production/2026-03-28-classify-roles-port-and-wiring.md` | Phase 1 |
| `./docs/plan/linkedin-ai-production/2026-03-28-company-enrichment-port.md` | Phase 2 |
| `./docs/plan/linkedin-ai-production/2026-03-28-affinity-v2-enhancements.md` | Phase 3 |
| `./docs/plan/linkedin-ai-production/review-findings.md` | Plan review (all issues resolved) |

### Specs
| File | Purpose |
|------|---------|
| `./docs/specs/linkedout_affinity_scoring.collab.md` | Affinity scoring spec (v1, with V2 planned behaviors) |
| `./docs/specs/linkedout_data_model.collab.md` | Data model spec |
| `./docs/specs/cli_commands.collab.md` | CLI commands spec |
| `./docs/specs/linkedout_intelligence.collab.md` | Intelligence spec (cross-refs affinity) |
| `./docs/specs/_registry.md` | Spec registry |

### Current linkedout code
| File | Purpose |
|------|---------|
| `./src/linkedout/intelligence/scoring/affinity_scorer.py` | Current V1 scorer |
| `./src/dev_tools/compute_affinity.py` | CLI compute-affinity script |
| `./src/dev_tools/cli.py` | CLI entry point |

### Old second-brain scripts to port
| File | Purpose |
|------|---------|
| `<prior-project>/linkedin-intel/scripts/classify_roles.py` | Old classify_roles to port (Phase 1) |
| `<prior-project>/linkedin-intel/scripts/enrich_companies.py` | Old enrich_companies to port (Phase 2) |
| `<prior-project>/linkedin-intel/scripts/company_utils.py` | Old company utils to port (Phase 2) |
| `<prior-project>/linkedin-intel/scripts/wikidata_utils.py` | Old wikidata utils to port (Phase 2) |
| `<prior-project>/linkedin-intel/scripts/compute_affinity.py` | Old affinity reference (Phase 3) |
