# SP1: Backend & Extension Constants Audits

**Sub-phase:** 1 of 7
**Plan tasks:** 4A (Backend Constants Audit) + 4F (Extension Constants Audit)
**Dependencies:** None (first sub-phase)
**Estimated complexity:** M (combined)
**Changes code:** No — read-only audits, produces documentation only

---

## Objective

Produce two comprehensive audit documents cataloging every hardcoded constant in both codebases. These audits are the source of truth for all subsequent extraction sub-phases.

---

## Task 1: Backend Constants Audit (4A)

### What to do

Read every file listed below and catalog all hardcoded values. For each constant, record:
- File path and line number
- Current hardcoded value
- What it controls (plain English)
- Category (see list below)
- Recommendation: `externalize` / `keep hardcoded` / `defer`

### Files to audit

- `backend/src/shared/config/config.py` — current config centralization point
- `backend/src/shared/utilities/logger.py` — log rotation settings
- `backend/src/shared/infra/reliability/retry_policy.py` — retry configs
- `backend/src/shared/infra/reliability/timeout_policy.py` — timeout configs
- `backend/src/shared/common/nanoids.py` — ID generation sizes
- `backend/src/linkedout/enrichment_pipeline/apify_client.py` — Apify URLs, costs, timeouts
- `backend/src/linkedout/enrichment_pipeline/controller.py` — cache TTL, inline URLs
- `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` — scoring weights and thresholds
- `backend/src/utilities/llm_manager/embedding_client.py` — model names, dimensions, polling
- `backend/src/dev_tools/generate_embeddings.py` — batch sizes, timeouts
- `backend/main.py` — server config
- **Also scan for any files not in this list** that contain hardcoded constants (grep for numeric literals, URL strings, model names)

### Categories

API URLs, model names, rate limits, cache TTLs, retry/timeout, batch sizes, scoring weights, DB settings, port numbers, ID prefixes, log settings, cost tracking, magic numbers

### Output

Create `docs/audit/backend-constants-audit.md` with:
- Table format: File | Line | Value | Description | Category | Recommendation
- Group by category
- Summary counts per category and per recommendation

---

## Task 2: Extension Constants Audit (4F)

### What to do

Read every file listed below and catalog all hardcoded values. For each constant, record:
- File path and line number
- Current hardcoded value
- What it controls
- Fragility assessment: `fragile` (could break with LinkedIn changes) / `stable`
- Recommendation: `externalize to config.ts` / `keep in constants.ts` / `keep inline`

### Files to audit

- `extension/lib/constants.ts` — primary constants file
- `extension/lib/rate-limiter.ts` — timing calculations
- `extension/lib/log.ts` — storage caps
- `extension/lib/voyager/client.ts` — Voyager API params, decoration IDs
- `extension/lib/mutual/extractor.ts` — mutual connections params, decoration ID
- `extension/lib/backend/client.ts` — API endpoints, defaults
- `extension/entrypoints/voyager.content.ts` — debounce timer, speed multipliers
- **Also scan for any files not in this list** that contain hardcoded constants

### Output

Create `docs/audit/extension-constants-audit.md` with:
- Table format: File | Line | Value | Description | Fragility | Recommendation
- Voyager decoration IDs explicitly flagged as fragile with breakage risk documented
- Summary of what goes to `config.ts` vs stays in `constants.ts`

---

## Verification

- [ ] `docs/audit/backend-constants-audit.md` exists and is non-empty
- [ ] `docs/audit/extension-constants-audit.md` exists and is non-empty
- [ ] Every file listed above was actually read and audited
- [ ] Each constant has a clear recommendation (externalize / keep / defer)
- [ ] Voyager decoration IDs are flagged as fragile in the extension audit

---

## Notes

- This is a **read-only** sub-phase. Do NOT modify any source code.
- Create `docs/audit/` directory if it doesn't exist.
- Be thorough — scan beyond the listed files. Use grep to find hardcoded numbers, URLs, and model names across both codebases.
- The audit documents will be referenced by every subsequent sub-phase.
