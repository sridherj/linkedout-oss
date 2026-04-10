# Shared Context: LinkedOut Quality Execution

## Goal
Close the quality gap between LinkedOut search and Claude Code (Phase 1), then transform search into a persistent conversational workspace (Phase 2).

## Operating Mode
- **HOLD SCOPE** -- Requirements are explicit. No expansion or reduction.
- **NO BACKWARD COMPATIBILITY** -- Greenfield quality overhaul. Existing entities (SearchHistory) can be ignored/replaced/dropped. No migration, no dual-path.

## DAG (Build Order)
```
SP1 -> SP2 -> SP3a||SP3b -> SP4 -> SP5 -> SP6a||SP6b -> SP7
```
- Phase 1 boundary: SP1-SP4 (~12-16 sessions)
- Phase 2 boundary: SP5-SP7 (~12-15 sessions)

## Key Codebase Locations

| Component | Path |
|-----------|------|
| Backend (API, agents, tools, DB) | `.` (aka `.`) |
| Frontend (Next.js) | `<linkedout-fe>` |
| Frontend docs & design system | `<linkedout-fe>/docs` |
| Design files (HTML mockups) | `<linkedout-fe>/docs/design/` |
| Search agent | `src/linkedout/intelligence/agents/search_agent.py` |
| SQL tool | `src/linkedout/intelligence/tools/sql_tool.py` |
| Vector tool | `src/linkedout/intelligence/tools/vector_tool.py` |
| WhyThisProfile explainer | `src/linkedout/intelligence/explainer/why_this_person.py` |
| Schema context builder | `src/linkedout/intelligence/schema_context.py` |
| Search system prompt | `src/linkedout/intelligence/prompts/search_system.md` |
| LLM client | `src/linkedout/utilities/llm_client.py` |
| Contracts | `src/linkedout/intelligence/contracts.py` |
| DB session manager | `src/linkedout/shared/infra/db_session_manager.py` |
| CLI/dev tools | `src/dev_tools/` |
| Existing benchmark spike code | `src/dev_tools/benchmark/spike_queries.py`, `spike_scorers.py` |
| Spike query traces | `spike_query_traces/` |

## Specs (Check Before Modifying)
| Spec | Path | Version |
|------|------|---------|
| Intelligence | `docs/specs/linkedout_intelligence.collab.md` | v5 |
| Tracing | `docs/specs/tracing.collab.md` | v1 |
| CRUD Layer | `docs/specs/linkedout_crud.collab.md` | v2 |
| Data Model | `docs/specs/linkedout_data_model.collab.md` | v5 |
| Search Sessions | `docs/specs/search_sessions.collab.md` | NEW (create in SP5) |
| Spec Registry | `docs/specs/_registry.md` | - |

## Key Decisions from Plan Review

1. **Spike vs Production:** Spike artifacts *inform* but *don't constrain* production design. Split into "reusable data" (gold standard scores, query definitions, sql_tool bugfix) vs "spike learnings" (scorer approach, contract names, method signatures). Design production versions fresh.

2. **`ReplayMode` -> `ContextStrategy`:** Rename enum to `ContextStrategy` with values `FULL_HISTORY`, `SLIDING_WINDOW`, `SUMMARY_ONLY`. Rename field `replay_mode` -> `context_strategy`.

3. **Two DB engines:** `DbSessionManager` gets two engines -- main for writes, `linkedout_search_role` for RLS-enforced reads. Add `get_search_session()` method.

4. **WhyThisProfile batch size:** 10 profiles per LLM call (not 20). Full profile data is ~2K tokens/profile; 10 x 2K = 20K keeps within bounds.

5. **Unit tests per tool:** SQLite-pattern unit tests for each new tool in SP3a (not just benchmark validation).

6. **Interaction pattern tests:** Live LLM tests in benchmark suite (not pytest). Quality validation, not regression.

7. **No pattern router:** The 11 interaction patterns are validation test cases, not if/else code. The LLM selects tools based on context (Decision #10).

## Spike Artifacts Reference

### Reusable Artifacts (keep as-is)
| File | What's Reusable | Used In |
|------|-----------------|---------|
| `src/dev_tools/benchmark/spike_queries.py` | 10 calibration query definitions (data) | SP1 |
| `benchmarks/spike/spike_scores_gold_standard.json` | Gold standard scores for 10 queries | SP1 |
| `src/linkedout/intelligence/tools/sql_tool.py` | SQL error rollback fix (production bugfix) | SP6a |

### Spike Learnings (inform, don't extend)
| File | Validated Approach | Used In |
|------|-------------------|---------|
| `src/dev_tools/benchmark/spike_scorers.py` | Claude Code subprocess as judge (rho=0.739) | SP1 |
| `src/linkedout/intelligence/contracts.py` | Multi-turn contracts, structured_summary | SP5, SP6a |
| `src/linkedout/intelligence/agents/search_agent.py` | `_inject_conversation_history()`, `run_turn()` approach | SP5, SP6a |
| `spikes/s8_tool_expansion_spike.py` | Tool concepts, "think before you write" insight | SP3a |
| `tests/eval/multi_turn_runner.py` | Sliding window + summary_window_size=2 | SP5, SP6a |

### Spike Reports (in .taskos/ goal dir)
| Report | Key Finding |
|--------|------------|
| `rls-spike-report.md` | RLS Option B: GO, zero correctness issues |
| `spike_query_traces/gap_analysis.md` | Root causes: single-shot SQL, missing tools, no career patterns |
| `spike_llm_judge.ai.md` | DeepEval disqualified (rho=0.000), Claude subprocess works (rho=0.739) |
| `spike_tool_expansion_results.ai.md` | resolve_company_aliases=P0, "think before you write" is highest-leverage |
| `spike_multiturn_conversation_results.ai.md` | Sliding window beats full history; structured summary beats raw replay |

## Manual Prerequisites (Already Done)
- Frozen DB snapshot at `~/linkedout-benchmark-db/linkedout_snapshot_20260401.dump` (483MB)
- `linkedout_search_role` created in PostgreSQL

## Spec Operations Plan
| Spec | Action | When |
|------|--------|------|
| `tracing.collab.md` | Update | SP1 |
| `linkedout_intelligence.collab.md` | Update (batch) | SP4 |
| `linkedout_intelligence.collab.md` | Update (extend) | SP7 |
| `search_sessions.collab.md` | Create new | SP5 |

## Design Files
| Design | File | Sub-phases |
|--------|------|------------|
| Result cards + highlights | `result-cards-highlighted-attributes.html` | SP3b, SP6b |
| Session history + new search | `session-history-new-search.html` | SP5 |
| Conversation + follow-up | `conversation-history-followup.html` | SP6a |
| Profile slide-over panel | `profile-slideover-panel.html` | SP6b |
