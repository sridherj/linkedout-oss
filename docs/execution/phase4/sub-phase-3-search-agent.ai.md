# Sub-Phase 3: SearchAgent Core

**Goal:** linkedin-ai-production
**Phase:** 4 — Intelligence: Search Engine + Affinity Scoring
**Depends on:** SP-1 (Query Tools + Schema Context)
**Estimated effort:** 2-3h
**Source plan sections:** 4.2

---

## Objective

Build the `SearchAgent` that orchestrates the LLM tool-calling loop. The agent receives a natural language query, decides whether to use SQL, vector search, or both, executes the tools, and returns structured results. This is an agentic workflow (LLM decides tool sequence), NOT a CRUD operation.

## Context

The SearchAgent extends `BaseAgent` and uses LangChain's tool-calling. It replaces `<prior-project>/agents/linkedin/run.py`. The two tools from SP-1 (`execute_sql`, `search_profiles`) are bound to the LLM via `ChatOpenAI.bind_tools()`.

## Pre-Flight Checks

Before starting, verify these exist:
- [ ] `src/linkedout/intelligence/tools/sql_tool.py` — `execute_sql()` (SP-1 output)
- [ ] `src/linkedout/intelligence/tools/vector_tool.py` — `search_profiles()` (SP-1 output)
- [ ] `src/linkedout/intelligence/schema_context.py` — `build_schema_context()` (SP-1 output)
- [ ] `src/utilities/llm_manager/__init__.py` — `LLMClient` / `LLMFactory` exists
- [ ] A `BaseAgent` class exists to inherit from (check `src/` for existing agent base)

If `BaseAgent` doesn't exist yet, create a minimal one or have `SearchAgent` be standalone. Do not block on this.

## Files to Create

```
src/linkedout/intelligence/
├── contracts.py                     # SearchRequest, SearchResponse, SearchEvent, SearchResultItem
├── agents/
│   ├── __init__.py
│   └── search_agent.py              # SearchAgent (extends BaseAgent or standalone)
└── prompts/
    └── search_system.md             # System prompt template
```

---

## Step 1: Contracts (`contracts.py`)

Define the Pydantic models that form the search API contract:

```python
class SearchRequest(BaseModel):
    query: str                                          # NL query text
    conversation_state: ConversationState | None = None
    limit: int = Field(default=20, le=100)

class SearchResultItem(BaseModel):
    """Shared SSE contract — Phase 4 produces, Phase 5a consumes."""
    connection_id: str
    crawled_profile_id: str
    full_name: str
    headline: str | None
    current_position: str | None
    current_company_name: str | None
    location_city: str | None
    location_country: str | None
    linkedin_url: str | None
    public_identifier: str | None
    affinity_score: float | None
    dunbar_tier: str | None
    similarity_score: float | None          # only for vector searches
    connected_at: str | None                # ISO date string
    has_enriched_data: bool

class SearchResponse(BaseModel):
    answer: str                             # LLM-generated summary
    results: list[SearchResultItem]
    query_type: str                         # sql | vector | hybrid | direct
    result_count: int
    follow_up_suggestions: list[str]

class SearchEvent(BaseModel):
    """SSE event — Phase 5a consumes via fetch + ReadableStream."""
    type: str       # thinking | result | explanations | done | error
    message: str | None = None
    payload: dict | None = None
```

---

## Step 2: System Prompt (`prompts/search_system.md`)

**Template variables:** `{schema_context}`, `{app_user_id}`

**Content must include:**
- Role: "You are a search engine for a user's LinkedIn network"
- Schema reference (injected via `{schema_context}`)
- Query routing rules:
  - Structured queries (company, location, role, skill, counts) → `execute_sql`
  - Semantic/concept queries ("working on AI agents", "climate tech") → `search_profiles`
  - Hybrid: SQL to pre-filter, then semantic to rank (call both tools)
- User-scoping mandate: "ALWAYS include `WHERE c.app_user_id = :app_user_id` in SQL queries"
- Safety: "Only generate SELECT queries. Never modify data."
- Output format instructions

---

## Step 3: SearchAgent (`search_agent.py`)

```python
class SearchAgent(BaseAgent):  # or standalone if BaseAgent doesn't exist
    """Agentic NL query engine for user-scoped LinkedIn network search."""

    def __init__(self, session: Session, app_user_id: str):
        self._session = session
        self._app_user_id = app_user_id

    def run(self, query: str, conversation_state: ConversationState | None = None) -> SearchResponse:
        """Synchronous search — returns full result set."""

    async def run_streaming(self, query: str, ...) -> AsyncGenerator[SearchEvent, None]:
        """Async streaming — yields SSE events."""
```

**Porting from:** `<prior-project>/agents/linkedin/run.py`

**Key implementation details:**

1. **LLM client:** Use `SEARCH_LLM_MODEL` env var (default `gpt-5.4-mini`). Add to `config.py`, `.env.local`, `.env.test`.
2. **Tool binding:** Use LangChain's `ChatOpenAI.bind_tools()` with the two tools
3. **Tool-calling loop:**
   - Build system prompt with schema context
   - Send user query to LLM
   - LLM returns tool calls → execute them → feed results back
   - Repeat until LLM returns final text answer (no more tool calls)
   - MAX_ITERATIONS = 5
4. **Error recovery:** Column-not-found → retry with schema hint. Timeout → simplify query. Max 2 retries per tool call.
5. **Streaming variant (`run_streaming`):**
   - Uses `asyncio.to_thread()` to run the sync tool-calling loop
   - Yields SSE events via a queue:
     - `{"type": "thinking", "message": "Routing query..."}` — before first LLM call
     - `{"type": "thinking", "message": "Querying database..."}` — when tool is called
     - `{"type": "result", "payload": {...}}` — for each result
     - `{"type": "done", "payload": {"total": N, "query_type": "..."}}` — when complete
     - `{"type": "error", "message": "..."}` — on failure

---

## Step 4: Config Updates

Add `SEARCH_LLM_MODEL` to:
- `src/shared/config/config.py` — new config field
- `.env.local` — default value `gpt-5.4-mini`
- `.env.test` — test value

---

## Step 5: Unit Tests

Create `tests/unit/linkedout/intelligence/test_search_agent.py`:
- Tool routing: structured query → `execute_sql` called
- Tool routing: semantic query → `search_profiles` called
- Iteration loop respects MAX_ITERATIONS
- Error recovery: retries on column-not-found
- Final response maps to `SearchResponse` model
- Mock both tools and LLM client

---

## Completion Criteria

- [ ] `SearchAgent.run()` returns `SearchResponse` with results, answer, and query_type
- [ ] `SearchAgent.run_streaming()` yields `SearchEvent` objects
- [ ] LLM tool-calling loop correctly routes to `execute_sql` or `search_profiles`
- [ ] MAX_ITERATIONS = 5 enforced
- [ ] Error recovery works (retry with hint on column-not-found)
- [ ] `SEARCH_LLM_MODEL` env var added and read by SearchAgent
- [ ] System prompt includes schema context and routing rules
- [ ] Contracts defined and importable
- [ ] Unit tests pass with mocked tools and LLM
