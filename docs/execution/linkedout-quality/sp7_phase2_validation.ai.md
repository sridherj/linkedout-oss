# Sub-phase 7: Phase 2 Validation & Polish

## Prerequisites
- **SP6a complete** (context engineering & conversational tools)
- **SP6b complete** (profile questions & detail view)

## Outcome
Full conversational search works end-to-end: search -> refine -> compare -> tag -> close laptop -> return next day -> continue. All 11 interaction patterns pass validation. Performance targets met. All specs updated.

## Estimated Effort
2-3 sessions

## Verification Criteria
- [ ] End-to-end: search, refine, tag, close browser, return next day, see results + tags, continue -- all works
- [ ] Session load <500ms
- [ ] Follow-up turn latency comparable to initial search
- [ ] In-memory filtering <100ms
- [ ] All 11 interaction patterns pass validation test cases (from SP6a)
- [ ] Langfuse shows session-level tracing with per-turn spans
- [ ] All specs updated
- [ ] Phase 1 benchmark scores maintained (no regression)

---

## Activities

### 7.1 End-to-End Integration Testing
- Full conversational workflow across multiple browser sessions
- Test realistic multi-day usage: search day 1, continue day 2
- Edge cases:
  - 20+ turn conversations -- does structured summary preserve intent?
  - Empty results after narrowing -- does LLM suggest relaxation?
  - Conflicting filters
  - Concurrent sessions from same user -- no cross-contamination

### 7.2 Performance Testing
- Session load time against 500ms target
- Follow-up turn latency vs initial search
- In-memory filtering speed against 100ms target
- Measure: total conversation cost (tokens) for a 10-turn conversation

### 7.3 Edge Case Testing
- Very long conversations (20+ turns) -- structured summary preserves intent?
- Zero results after narrowing -- LLM suggests relaxation?
- Tag operations across sessions -- tags survive session archival?
- Concurrent sessions from same user -- no cross-contamination?

### 7.4 Spec Updates
- `/update-spec` for `linkedout_intelligence.collab.md` -- extend with:
  - Session support
  - Conversational tools (filter/exclude/tag/rerank/aggregate/profile_detail)
  - Interaction patterns (11 types, LLM-driven selection)
  - In-memory result set tools
  - `suggested_actions` and `facets` in response format
  - LLM response structure for conversation turns (message, chips, suggestions, exclusion_state, metadata, facets)
- `/update-spec` for `search_sessions.collab.md` -- extend with:
  - Behaviors discovered during implementation
  - Pivot detection mechanism
  - Undo stack for result set operations
  - Edge cases for long conversations
- Review both spec outputs for completeness against implemented behavior

### 7.5 UX Polish
- Conversation history display clarity
- Session navigation smoothness
- Profile detail transitions (slide-over animation, backdrop)
- Result card content rendering (highlight chips, unenriched state)
- Loading states for follow-up turns

### 7.6 Phase 1 Regression Check
- Run Phase 1 benchmark to ensure quality gains maintained through Phase 2 changes
- Any regression means Phase 2 changes broke Phase 1 quality -- investigate and fix
- Compare against post-improvement baseline captured in SP4

---

## Design Review Notes

No flags. This sub-phase is validation and polish, not new architecture.

## Key Files to Read First
- Benchmark runner: `src/dev_tools/benchmark/runner.py` -- for regression check
- `docs/specs/linkedout_intelligence.collab.md` -- major extension target
- `docs/specs/search_sessions.collab.md` -- extension target (created in SP5)
- All design files in `<linkedout-fe>/docs/design/` -- for UX polish reference
