# Phase F: Full Benchmark Run + Iterate

**Effort:** 1 session
**Dependencies:** Phases A-E complete
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Run the full 32-query benchmark with all changes in place. Measure improvement from ~3.1/5 baseline. Identify remaining stragglers and iterate.

## What to Do

### 1. Run full benchmark

```bash
cd .

# Run all 32 queries
python src/dev_tools/benchmark/runner.py

# Score results
python src/dev_tools/benchmark/scorer.py
```

### 2. Analyze results

Compare against baseline (~3.1/5 avg). Expected improvement areas:
- **Funding queries** (sj_03, rec_03, fnd_06): Should improve from Phase A
- **External context queries** (sj_09, fnd_04, rec_10): Should improve from Phase B
- **Intro queries** (sj_01): Should improve from Phase E
- **Overall reasoning quality**: Should improve from Phase C (prompt simplification)

Target: average score ~4.0+

### 3. Identify stragglers

For any query still scoring ≤ 3:
- Inspect Langfuse traces to understand what the agent tried
- Determine if the issue is:
  - **Missing tool**: Needs another capability
  - **Prompt issue**: Prompt is misleading the LLM
  - **Data issue**: Data doesn't support the query
  - **LLM limitation**: The model can't reason about this type of query
- Fix tool/prompt issues and re-run just those queries

### 4. Manual verification

Run the key validation query manually:
```
"Find people who can help me reach out to Lovable"
```

Compare output to spike results (4 tiers, ~15 people):
1. Direct employee: Abhijeet Jha
2. Community/ambassadors: Anadee, Nayana K.
3. Investor connections: Chitranjan, Rachitt at Accel
4. Former colleague warm paths: Dunno/Google overlap

### 5. Run full test suite

```bash
precommit-tests
```

## Verification

This IS the verification phase. Success criteria:
- Average benchmark score ≥ 4.0
- **No individual query below 3** (not 2 — raised threshold per plan)
- Manual "Lovable" query produces multi-tier results
- All tests pass

### Run commands

```bash
# Full 32-query benchmark
python -m src.dev_tools.benchmark

# Eval suite
pytest tests/eval/test_search_quality.py -m eval -v

# Multi-turn eval
pytest tests/eval/test_multiturn_poc.py -m eval -v

# Precommit
precommit-tests
```

### Specific queries to watch

These previously scored 2 and need targeted attention:

| Query ID | Query | Root Cause | Expected Fix |
|---|---|---|---|
| sj_09 | "college alumni doing impressive things" | Needs web context to assess "impressive" | Phase B web search |
| fnd_04 | "big tech to climate pivot" | Needs web context for climate companies | Phase B web search |
| fnd_08 | "repeat founders" | Was counting advisory roles as founding | Prompt/tool fix |
| rec_10 | "non-traditional backgrounds" | Needs web context for bootcamps | Phase B web search |

For each failing query: document root cause (tool gap vs prompt gap vs data gap), fix, re-run.

This phase may span multiple sessions — that's expected.

## Output

Document results in a brief summary:
- Before/after scores
- Per-category improvement
- Remaining gaps (if any)
- Whether target of 4.0+ was hit
