# Sub-phase 1: Measurement Foundation — Benchmark Infrastructure & Langfuse Tracing

## Prerequisites
- **None** (first sub-phase)
- Manual prereqs already done: frozen DB snapshot at `~/linkedout-benchmark-db/linkedout_snapshot_20260401.dump`, `linkedout_search_role` created

## Outcome
A repeatable, automated benchmark scores LinkedOut search quality on 30+ queries against a frozen DB snapshot, with baseline scores captured. Langfuse tracing covers the full search flow with session_id from day one.

## Estimated Effort
4-5 sessions

## Verification Criteria
- [ ] `python -m dev_tools.benchmark run` produces a markdown report with per-query scores (1-5), per-persona averages, and aggregate score
- [ ] `python -m dev_tools.benchmark run --compare baseline` shows delta from baseline
- [ ] Frozen DB snapshot restores in <2 minutes via `benchmarks/restore_snapshot.sh`
- [ ] A search in the app produces a Langfuse trace with nested spans: `search_request > search_agent_loop > [tool_call_N > sql_execution | vector_search] > why_this_profile`
- [ ] All traces include `session_id` metadata field (generated UUID for now)
- [ ] Baseline LinkedOut scores captured (pre-improvement)

---

## Activities

### 1.1 Frozen DB Snapshot
- `pg_dump` already done: `~/linkedout-benchmark-db/linkedout_snapshot_20260401.dump` (483MB)
- Create `benchmarks/restore_snapshot.sh` -- single command, idempotent restore script
- Create `benchmarks/README.md` documenting: profile count, experience count, company count for SJ's user, known data quality issues (verify `company_alias` table emptiness), snapshot date, restore instructions

### 1.2 Query Suite Design (30+ queries)
- **Starting set:** 10 calibration queries from `src/dev_tools/benchmark/spike_queries.py` + 5 gap analysis queries from `spike_query_traces/`
- Expand to 30+: ~12 SJ persona, ~10 recruiter, ~10 founder
- Store as YAML in `benchmarks/queries/{persona}_{slug}_{nnn}.yaml`:
  ```yaml
  id: sj_01
  persona: sj
  query: "Who are the strongest warm intro paths to someone at Stripe?"
  dimensions: [network_proximity, company, multi_hop_reasoning]
  difficulty: hard
  expected_behavior: "Should find direct connections at Stripe, then 2nd-degree paths via shared companies/alumni"
  ```
- **Quality bar:** Queries must require multi-step reasoning, inference from incomplete data, combining multiple signals. Simple lookups are insufficient.

### 1.3 Benchmark Runner (`src/dev_tools/benchmark/`)
- `runner.py`: Orchestrates execution. For each query: call LinkedOut search API, capture full response (results, SQL, tools invoked, latency, WhyThisProfile explanations). Store as JSON in `benchmarks/results/linkedout/{query_id}.json`
- `scorer.py`: **Design production scorer informed by spike's Claude Code subprocess approach** (spike validated `run_opus_judge_scorer()` -- subprocess + DB access, Spearman rho = 0.739). Each judge session: `claude -p --model sonnet` subprocess with DB access, scores relevance 1-5, provides reasoning. Gold standard scores for 10 queries at `benchmarks/spike/spike_scores_gold_standard.json`. **Do NOT extend spike_scorers.py** -- design production scorer fresh.
- `reporter.py`: Markdown report. Per-query scores, per-persona averages, aggregate mean/median, worst-performing queries, delta from baseline if `--compare` flag
- CLI: `python -m dev_tools.benchmark run [--compare baseline] [--queries sj_*] [--report-only]`

### 1.4 Claude Code Gold Standard Capture
- Run all 30+ queries through Claude Code (`claude -p` with DB access), capture: SQL, tools, reasoning, results
- Store as `benchmarks/results/claude_code/{query_id}.json`
- 5 queries already captured from gap analysis spike -- extend to full set

### 1.5 LinkedOut Baseline Capture
- Run all 30+ queries through current LinkedOut (pre-improvement)
- Store as `benchmarks/results/linkedout_baseline/{query_id}.json`
- 5 baseline traces already exist from spike

### 1.6 Extended Gap Analysis
- Expand spike's gap analysis from 5 queries to all 30+
- Known root causes (confirmed by spike): single-shot SQL, no career pattern analysis, no graph reasoning, no company classification
- Output: `benchmarks/gap_analysis.md` with per-category failure patterns and prioritized fix list

### 1.7 Langfuse Instrumentation
- Add `@observe` decorators to the search flow:
  - `search_controller.search()` -- top-level trace with `session_id` metadata
  - `search_agent.run()` -- span for the agent loop
  - Each tool call in the loop -- span per invocation with args/response/latency
  - `sql_tool.execute()` -- span with SQL text, execution time, row count
  - `search_profiles` (in `vector_tool.py`) -- span with query text, similarity scores
  - `why_this_person.explain()` -- span with input context size, output per profile
- Token usage tracked per LLM call (already available via LLMMetrics)
- All traces tagged with `session_id` (generated UUID for now; Phase 2 replaces with real session ID)
- **Error path:** Benchmark runner must NOT depend on Langfuse. Tracing is observe-only; benchmark captures its own structured output independently.

### 1.8 Spec Update
- `/update-spec` for `tracing.collab.md`: add search-level trace hierarchy, session_id tagging, custom spans per tool call. Remove "no custom trace attributes or tags per agent" from Not Included section.

---

## Design Review Notes

| ID | Issue | Resolution |
|----|-------|------------|
| Spec conflict | `tracing.collab.md` > Not Included > "Custom trace attributes or tags per agent" | Contradicted by session_id tagging and per-tool spans. Activity 1.8 addresses via `/update-spec` |
| Naming | Benchmark CLI | `python -m dev_tools.benchmark` follows existing `python -m dev_tools.cli` pattern |
| Architecture | Scorer as subprocess | Spawning `claude -p` per query is slow but validated by spike (rho=0.739). Parallelism (4-5 concurrent scorers) can reduce wall clock time |
| Error path | Langfuse unreachable during benchmark | Benchmark must NOT depend on Langfuse. Tracing is observe-only |

## Key Files to Read First
- `src/dev_tools/benchmark/spike_queries.py` -- existing calibration queries (data, reusable)
- `src/dev_tools/benchmark/spike_scorers.py` -- spike scorer approach (learn from, don't extend)
- `benchmarks/spike/spike_scores_gold_standard.json` -- gold standard scores (reusable)
- `spike_query_traces/gap_analysis.md` -- root cause analysis from spike
- `docs/specs/tracing.collab.md` -- current tracing spec (will be updated)
- `src/linkedout/intelligence/agents/search_agent.py` -- search flow to instrument
- `src/linkedout/intelligence/tools/sql_tool.py` -- SQL tool to instrument
- `src/linkedout/intelligence/tools/vector_tool.py` -- vector tool to instrument
- `src/linkedout/intelligence/explainer/why_this_person.py` -- explainer to instrument
