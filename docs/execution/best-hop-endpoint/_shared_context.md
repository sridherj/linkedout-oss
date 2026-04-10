# Shared Context: Best Hop Dedicated Endpoint

**Plan:** `docs/plan/best-hop-dedicated-endpoint.md`
**Goal:** Replace the 42-second agentic best-hop flow (7 LLM iterations via `/search`) with a dedicated `POST /best-hop` endpoint that pre-assembles context and completes in ~6-9s (1 LLM call).

---

## Core Insight

Best hop is a **two-hop ranking** problem. For each mutual connection M:
- **Leg 1 (User → M)**: Pre-computed `affinity_score` / `dunbar_tier`
- **Leg 2 (M → Target)**: Inferred from experience overlap, shared companies, seniority proximity

The LLM ranks by synthesizing both legs with a single context-injected call, not iterative tool discovery.

## Key Decisions

1. **Pre-assemble context, not agentic.** 4 batch SQL queries (~100ms) replace 7 LLM iterations (~35s). LLM gets a running start.
2. **Optional tools as safety net.** `get_profile_detail` and `execute_sql` available but not expected path (1-2 iterations max, likely 1).
3. **Same SSE contract as `/search`.** Extension parsing unchanged. Event types: `session`, `thinking`, `result`, `done`.
4. **Same model as search.** Uses `SEARCH_LLM_MODEL` config.
5. **Reuse SearchSession/SearchTurn.** No entity changes needed. `initial_query = "Best hop → {target_name}"`.
6. **Target always in DB.** Extension enriches target profile on visit before best-hop triggers.
7. **Result limit: 30.** Enough variety without overwhelming.
8. **Report unmatched URLs in `done` event.** Transparency for future background enrichment.

## DAG (Build Order)

```
A ──────────────────────┐
                        ├── D ──┐
B ── C ─────────────────┘       ├── F
                                │
     E (independent) ───────────┘

G (frontend, independent of backend)
H (frontend, independent of backend)
```

- A before D (controller needs SSE helpers)
- B before C (service needs contracts)
- C + D before F (tests need service + controller)
- E (prompt) can be done anytime before F
- G, H are fully independent of backend subphases

## Repo Locations

| Component | Path |
|-----------|------|
| Backend root | `.` |
| Frontend root | `<linkedout-fe>` |
| Extension code | `<linkedout-fe>/extension/` |
| Search controller | `src/linkedout/intelligence/controllers/search_controller.py` |
| Search agent | `src/linkedout/intelligence/agents/search_agent.py` |
| Contracts | `src/linkedout/intelligence/contracts.py` |
| Prompts dir | `src/linkedout/intelligence/prompts/` |
| DB session manager | `src/linkedout/shared/infra/db/db_session_manager.py` |
| LLM client | `src/linkedout/utilities/llm_client.py` |
| SearchSession service | `src/linkedout/search_session/services/search_session_service.py` |
| SearchTurn entity | `src/linkedout/search_session/entities/search_turn_entity.py` |
| Why This Person | `src/linkedout/intelligence/explainer/why_this_person.py` |

## Key Specs (read before modifying)

- `docs/specs/linkedout_intelligence.collab.md`
- `docs/specs/search_sessions.collab.md`
- `docs/specs/chrome_extension.collab.md`
- `docs/specs/llm_client.collab.md`

## Exploration Artifacts

- `.taskos/exploration/code_exploration.ai.md` — codebase analysis for extension integration
- `.taskos/exploration/playbooks.ai.md` — implementation playbooks
- `.taskos/docs/spike-linkedin-scraper-repos.ai.md` — Voyager API spike results

## SSE Pattern Reference

The existing `search_controller.py` has these helpers that subphase A will extract:

- `_sse_line(event: dict) -> str` — serialize one SSE event (line 38)
- `_stream_with_heartbeat()` — wrap generator with periodic heartbeats (line 470)
- `_create_or_resume_session()` — create/resume SearchSession (line 237)
- `_save_session_state()` — persist turn data to search_turn (line 307)

## SQL Queries (from plan)

**Query 1 — Mutual connections (batch lookup by URL):**
```sql
SELECT cp.id, cp.full_name, cp.headline, cp.current_position,
       cp.current_company_name, cp.linkedin_url, cp.location_city,
       cp.seniority_level, cp.about,
       c.id AS connection_id, c.affinity_score, c.dunbar_tier,
       c.affinity_career_overlap, c.affinity_external_contact,
       c.affinity_recency, c.connected_at
FROM crawled_profile cp
JOIN connection c ON c.crawled_profile_id = cp.id
WHERE cp.linkedin_url = ANY(:mutual_urls)
ORDER BY c.affinity_score DESC NULLS LAST
```

**Query 2 — Experience for top 50 mutuals:**
```sql
SELECT e.crawled_profile_id, e.company_name, e.company_id, e.position,
       e.start_date, e.end_date, e.is_current, e.seniority_level
FROM experience e
WHERE e.crawled_profile_id = ANY(:top_50_profile_ids)
ORDER BY e.crawled_profile_id, e.start_date DESC
```

**Query 3 — Target profile:**
```sql
SELECT cp.id, cp.full_name, cp.headline, cp.current_position, cp.current_company_name,
       cp.location_city, cp.seniority_level, cp.about
FROM crawled_profile cp
WHERE cp.linkedin_url = :target_url
LIMIT 1
```

**Query 4 — Target experience:**
```sql
SELECT e.company_name, e.company_id, e.position, e.start_date, e.end_date,
       e.is_current, e.seniority_level
FROM experience e
WHERE e.crawled_profile_id = :target_profile_id
ORDER BY e.start_date DESC
```

**Query 5 — Target connection status (optional extra context):**
```sql
SELECT c.affinity_score, c.dunbar_tier
FROM connection c WHERE c.crawled_profile_id = :target_profile_id
LIMIT 1
```
