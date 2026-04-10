# Sub-phase 4: Quality Validation & Phase 1 Completion

## Prerequisites
- **SP3a complete** (tool expansion and prompt engineering)
- **SP3b complete** ("Why This Profile" improvement)

## Outcome
LinkedOut average relevance score is within 1 point of Claude Code across the full 30+ query benchmark. All Phase 1 changes are validated, documented, and spec'd. Post-improvement baseline captured for Phase 2 regression testing.

## Estimated Effort
2-3 sessions

## Verification Criteria
- [ ] Full benchmark: average score within 1 point of Claude Code on 1-5 scale
- [ ] Worst-performing queries identified with root causes documented
- [ ] All specs updated: `linkedout_intelligence.collab.md`, `tracing.collab.md`
- [ ] Gap analysis report finalized: before/after by category
- [ ] Frozen post-improvement benchmark snapshot captured as Phase 2 regression baseline

---

## Activities

### 4.1 Full Benchmark Run
- Run complete 30+ query suite with all improvements in place
- Compare against: (a) original LinkedOut baseline (from SP1), (b) Claude Code gold standard
- Use Claude Code subprocess scorer for automated scoring
- Output: comprehensive report with per-query scores, per-persona averages, aggregate

### 4.2 Targeted Fix Cycle
- For each query scoring below 3: diagnose root cause from Langfuse traces
  - Missing tool selection? -> Adjust tool descriptions or add prompting examples
  - Wrong SQL? -> Check if schema context is missing relevant tables/columns
  - Correct SQL, wrong interpretation? -> Prompt tuning for the specific pattern
- **Change one thing at a time**, re-benchmark after each change
- Document fixes in `benchmarks/fix_log.md`

### 4.3 Spec Updates (Batch)
- `/update-spec` for `linkedout_intelligence.collab.md` -- bulk update covering:
  - RLS enforcement replaces advisory scoping model (from SP2)
  - 7+ tools replaces "two bound tools" (from SP3a)
  - Routing rules stripped from prompt (from SP3a)
  - WhyThisProfile: 2-3 sentences with structured JSON + `highlighted_attributes` (from SP3b)
  - "ID: explanation" format replaced by structured JSON (from SP3b)
  - Multi-turn support mention (forward-look for Phase 2)
- Verify `tracing.collab.md` was already updated in SP1 -- if not, update now

### 4.4 Phase 1 Handoff Document
- `benchmarks/phase1_results.md`: what changed, score improvements by category, remaining limitations, Phase 2 regression baseline
- This becomes the handoff document for Phase 2

### 4.5 Capture Post-Improvement Baseline
- Freeze a new benchmark snapshot (post-improvements) as the regression baseline for Phase 2
- Store alongside original baseline for comparison

---

## Design Review Notes

No flags. This sub-phase is validation and documentation, not new architecture.

## Key Files to Read First
- Benchmark runner: `src/dev_tools/benchmark/runner.py`, `scorer.py`, `reporter.py` (from SP1)
- `docs/specs/linkedout_intelligence.collab.md` -- major update target
- `docs/specs/tracing.collab.md` -- verify SP1 update was done
- `benchmarks/results/` -- baseline and current results
