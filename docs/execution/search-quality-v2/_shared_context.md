# Shared Context: Search Agent Quality V2

**Plan:** `./docs/plan/search-agent-quality-v2.collab.md`
**Goal:** Close quality gap between LinkedOut search (~3.1/5 avg) and Claude Code by adding tools + simplifying prompts.
**Spike validated:** `tmp_spike_web_search.py` proved zero-prompt-engineering + right tools = Claude Code quality.

---

## Key Architectural Decisions

1. **Tool-first, not prompt-first.** A 12-line prompt with rich tools beats a 94-line prescriptive prompt with limited tools. The LLM naturally decomposes and plans when given the right capabilities.

2. **Web search as a function tool.** `web_search` is a regular function tool in `_TOOL_DEFINITIONS`. Implementation delegates to OpenAI Responses API (`gpt-4.1-mini` + `web_search_preview`). No LangChain or `llm_client.py` changes needed. Guardrails: max 3 calls/turn, 10s timeout.

3. **Frontend owns session lifecycle.** Backend has zero pivot detection or auto-archiving logic. New conversation = frontend sends no `session_id`. Continuation = frontend sends `session_id`. Backend is stateless with respect to session decisions.

4. **Conversation history in `llm_manager/`, not `LLMClient`.** New `ConversationManager` class — generic infrastructure, caller provides summarization prompt. `LLMClient` stays untouched.

5. **No backward compatibility.** Existing search history in DB discarded. Old columns/contracts removed outright. No migration path for old data.

6. **Turn-based conversation storage.** Each search turn writes a new `search_turn` row instead of overwriting `conversation_state` on the session entity.

7. **Result set tools removed.** `filter_results`, `exclude_from_results`, `rerank_results`, `aggregate_results`, `start_new_search` all removed. The LLM re-queries with adjusted criteria instead. `tag_profiles`, `get_tagged_profiles`, `compute_facets` kept.

8. **Funding tables exposed.** `funding_round` (198 rows) and `startup_tracking` (182 rows) made visible to the LLM via schema context and SQL tool. NOT user-scoped (public company data).

---

## Repo Locations

- **Backend:** `.` (absolute: `.`)
- **Frontend:** `<linkedout-fe>` (absolute: `<linkedout-fe>`)

## Key Specs (read before modifying)

- `./docs/specs/linkedout_intelligence.collab.md`
- `./docs/specs/search_sessions.collab.md`
- `./docs/specs/search_conversation_flow.collab.md`
- `./docs/specs/llm_client.collab.md`
- `./docs/specs/prompt_management.collab.md`
- `./docs/specs/tracing.collab.md`

## Exploration Artifacts

- `./.taskos/exploration/code_exploration.ai.md`
- `./.taskos/exploration/playbook_search_quality.ai.md`
- `./.taskos/exploration/playbook_why_this_profile.ai.md`
- `./.taskos/exploration/playbook_conversational_search.ai.md`
- `./.taskos/spike_tool_expansion_results.ai.md`
- `./.taskos/spike_llm_judge.ai.md`

## Spike Artifact

- `./tmp_spike_web_search.py`

## Phase Dependencies (DAG)

```
A ──┐
    ├── C ──┐
B ──┘       ├── D.1 → D.2 → D.3 → D.4 ──┐
            │                              ├── F
E ──────────┘                              │
                                           ├── G.1 → G.2 → G.3
                                           │
                                           ├── H.1 (with D)
                                           ├── H.2 (with G)
                                           ├── H.3 (with D.2)
                                           └── H.4 (with B+C)
```

- **A, B, E** can start independently
- **C** depends on A+B (prompt references funding tables from A, web search tool from B)
- **D.1-D.4** are strictly sequential (each builds on prior)
- **D.1** depends on C being done (prompt simplification removes result set tools referenced in D.3)
- **F** depends on A-E complete
- **G.1-G.3** depend on D.4 complete (backend API must be stable)
- **H sub-phases** can run alongside their corresponding implementation phases

## Verification

After each phase, run:
```bash
# Unit tests for intelligence module
pytest tests/unit/intelligence/ -v

# Full precommit suite (unit + integration + live_llm)
precommit-tests
```

After Phase F:
```bash
# Benchmark
python src/dev_tools/benchmark/runner.py
python src/dev_tools/benchmark/scorer.py
# Target: avg score ~3.1 → ~4.0+
```
