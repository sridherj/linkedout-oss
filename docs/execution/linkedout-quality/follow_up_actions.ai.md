# Follow-Up Actions — LinkedOut Quality Execution

Tracked actions that need human attention or deferred work across sub-phases.

---

## SP1: Benchmark Infrastructure & Langfuse Tracing

**Status:** Partial — infrastructure built, captures in progress

- [ ] **[IN PROGRESS] Run baseline capture:** `python -m dev_tools.benchmark run --capture-baseline` (SJ running in separate terminal)
- [ ] **[IN PROGRESS] Run Claude Code gold standard:** `python -m dev_tools.benchmark run --capture-claude-code` (SJ running in separate terminal)
- [ ] **Verify Langfuse traces:** After a search, check Langfuse dashboard for traces with `session_id` metadata and nested spans (`search_agent_run > tool_call > sql_execution`)
- [ ] **Review 32 query definitions:** Ensure queries require multi-step reasoning. `expected_behavior` fields are sparse (one-liners) — consider enriching for better scoring
- [ ] **Run full benchmark + gap analysis:** After captures complete, run `python -m dev_tools.benchmark run` and generate gap analysis (Activity 1.6)
- [ ] **Save baseline scores:** Copy `benchmarks/scores/linkedout_scores.json` to `benchmarks/scores/baseline_scores.json`

---

## SP2: PostgreSQL RLS Implementation

**Status:** Completed

- [ ] **Verify search role password in .env.local:** Ensure `SEARCH_DATABASE_URL=postgresql://linkedout_search_role:search_role_pwd@localhost:5432/linkedout_db` matches what was set during manual role creation
- [ ] **Run Alembic migration on live DB:** `alembic upgrade head` (enables RLS policies)
- [ ] **Run /update-spec for linkedout_intelligence.collab.md:** Reverse the "Rejected: row-level security" decision, document RLS enforcement replacing advisory scoping (Activity 2.6 — deferred to SP4 batch update)
- [ ] **Run RLS isolation integration tests against live DB:** `RUN_RLS_TESTS=1 pytest tests/integration/linkedout/intelligence/test_rls_isolation.py`
- [ ] **Run benchmark post-RLS:** Compare against SP1 baseline to verify no regression

---

## SP3a: Tool Expansion & Prompt Engineering

**Status:** Completed

- [ ] **Run benchmark post-tools:** Compare against SP2 baseline, verify 0.5+ improvement target
- [ ] **Check Langfuse traces:** Verify new tools appear in traces when invoked on relevant queries

---

## SP3b: Why This Profile Improvement

**Status:** Completed

- [ ] **Manual inspection:** Run 10 queries, verify explanations reference specific match dimensions
- [ ] **Verify highlighted_attributes:** Check that color_tier mapping (0=lavender, 1=rose, 2=sage) produces sensible chips

---

## SP4: Quality Validation & Phase 1 Completion

**Status:** Partial — QUALITY GATE NOT MET

**Critical finding:** Post-improvement mean score (3.19) did NOT improve over baseline (3.28). 4 new zero-result regressions introduced by tool expansion (LLM over-engineers SQL when more tools available).

- [ ] **REVIEW: benchmarks/phase1_results.md** — decide whether to iterate on prompt tuning before Phase 2
- [ ] **FIX: 4 zero-result regressions** (fnd_09, rec_01, sj_03, sj_12) — add prompt guidance to start with simple SQL before using complex tools
- [ ] **FIX: RLS in scorer subprocess** — judge `claude -p` needs `set_config('app.current_user_id', ...)` in SQL instructions so it can query the DB
- [ ] **FIX: _collect_results missing career_tool/network_tool** — new tool responses not collected in benchmark runner
- [ ] **VERIFY: linkedout_intelligence.collab.md v6** — spec updated directly (not via /update-spec), verify it matches expectations
- [ ] **Run Alembic migration:** `alembic upgrade head` (includes RLS policies from SP2 + session tables from SP5)

---

## SP5: Session Persistence

**Status:** Completed

- [ ] **Run Alembic migration:** `alembic upgrade head` (SearchSession + SearchTag tables)
- [ ] **Verify session persistence end-to-end:** Create search, close browser, reopen — results should persist
- [ ] **Frontend (SP5.8):** Session switcher dropdown, active session label, session resume — needs separate implementation
- [ ] **Consider:** Add sliding-window summary generation to save_turn for conversations >2 turns

---

## SP6a: Context Engineering & Conversational Tools

**Status:** Completed

- [ ] **Run live LLM tests:** Test interaction patterns with real LLM to validate tool selection
- [ ] **Test multi-pattern messages:** "Remove FAANG and rank rest by affinity" — verify both tools invoked
- [ ] **Test 20+ turn conversation:** Validate sliding window doesn't lose original intent
- [ ] **Integrate run_turn() with session persistence:** Ensure result_snapshot, excluded_ids, conversation_state update per turn
- [ ] **Frontend (SP6a.10):** Conversation thread, follow-up input bar, interaction hint chips, excluded profiles banner

---

## SP6b: Profile Questions & Detail View

**Status:** Completed

- [ ] **Frontend (SP6b.2):** Profile slide-over panel (4 tabs: Overview, Experience, Affinity, Ask)
- [ ] **Wire request_enrichment:** Connect confirmation flow to actual Apify re-crawl
- [ ] **LLM-generated suggested_questions:** Currently returned empty — needs LLM call in controller or separate endpoint
- [ ] **Frontend:** Result card rendering with highlighted_attributes chips + unenriched state

---

## SP7: Phase 2 Validation & Polish

**Status:** Completed

- [ ] **Wire up integration test infrastructure:** `tests/integration/` collects 0 items — needs conftest/fixtures for real PostgreSQL
- [ ] **Write e2e integration test:** Session create → search → filter → tag → close → resume against real DB
- [ ] **Run Phase 1 benchmark:** Verify no quality regression from Phase 2 changes
- [ ] **Prompt tuning pass:** SP4 quality gate not met (scores flat) — needs targeted fixes for 4 zero-result regressions

---

## Cross-Cutting: Not Yet Done

### Must Do Before Production
- [ ] **Run `alembic upgrade head`** — RLS policies (SP2) + SearchSession/SearchTag tables (SP5)
- [ ] **Prompt tuning for quality** — 4 zero-result regressions, flat benchmark scores. Root cause: LLM over-engineers SQL with more tools
- [ ] **Fix benchmark scorer RLS** — judge subprocess needs `set_config('app.current_user_id', ...)` to query DB
- [ ] **Fix benchmark runner** — `_collect_results` missing career_tool/network_tool responses

### Frontend (4 designs, not implemented)
- [ ] SP5.8: Session switcher dropdown + "New Search" button (`session-history-new-search.html`)
- [ ] SP6a.10: Conversation thread + follow-up bar + hint chips (`conversation-history-followup.html`)
- [ ] SP6b.2: Profile slide-over panel, 4 tabs (`profile-slideover-panel.html`)
- [ ] SP6b.5: Result cards with highlighted_attributes chips (`result-cards-highlighted-attributes.html`)
