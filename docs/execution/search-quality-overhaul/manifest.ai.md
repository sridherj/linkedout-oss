# Search Quality Overhaul — Execution Manifest

**Source plan:** `./docs/plan/search-quality-overhaul.collab.md`
**Working directory:** `./`
**Created:** 2026-03-31

## Sub-Phases

| # | File | Description | Depends On | Parallel? |
|---|------|-------------|------------|-----------|
| 1 | `sub-phase-1-prompt-cleanup.ai.md` | Fix system prompt: remove dead alias examples, add data warnings | — | No |
| 2 | `sub-phase-2-schema-context.ai.md` | Add data availability notes to schema_context.py | — | Yes (with 1) |
| 3 | `sub-phase-3-match-context.ai.md` | Add match_context to contracts + capture extra SQL columns | 1, 2 | No |
| 4 | `sub-phase-4-dedup-retry.ai.md` | Dedup results + fix broken retry loop | 3 | No |
| 5 | `sub-phase-5-explainer-enrichment.ai.md` | Enrich explainer with DB data, rewrite prompt, wire session | 3 | No |
| 6 | `sub-phase-6-eval-framework.ai.md` | Build 30-query eval framework | — | Yes (with 4, 5) |

## Execution Order (DAG)

```
[1: prompt-cleanup] ──┐
                       ├──→ [3: match-context] ──→ [4: dedup-retry]
[2: schema-context] ──┘                       ──→ [5: explainer-enrichment]

[6: eval-framework]  (independent, can run any time)
```

**Critical path:** 1 → 3 → 5 (prompt fix → contract change → explainer enrichment)

## Verification

After all sub-phases:
1. Run `precommit-tests` — must pass
2. Manual smoke test: "People at IT services companies" should return TCS/Infosys results
3. Run eval suite (once Phase 6 is complete): `pytest tests/eval/ -m eval`

## Review Decisions (carried from plan)

All review decisions from the plan are embedded in the relevant sub-phase files. See the plan's "Review Decisions" table for the full index.
