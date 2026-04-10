# Sub-phase C: Best Hop Service

**Effort:** 2-3 sessions
**Dependencies:** B (needs `BestHopRequest`, `BestHopResultItem` contracts)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Create `best_hop_service.py` — the core logic for pre-assembling context, calling the LLM, and merging results. This is NOT standard CRUD — it does not extend `BaseService`.

## What to Do

### 1. Create service file

**File:** `src/linkedout/intelligence/services/best_hop_service.py`

### 2. Data Assembly Method

```python
class BestHopService:
    def __init__(self, session: Session, app_user_id: str):
        self.session = session
        self.app_user_id = app_user_id

    def assemble_context(self, request: BestHopRequest) -> BestHopContext:
        """Run batch SQL queries to pre-assemble all data the LLM needs.

        Returns a BestHopContext dataclass with:
        - target_profile: dict (Query 3)
        - target_experience: list[dict] (Query 4)
        - target_connection: dict | None (Query 5 — affinity if direct connection)
        - mutuals: list[dict] (Query 1 — matched mutual connections with affinity)
        - mutual_experience: dict[str, list[dict]] (Query 2 — keyed by crawled_profile_id)
        - matched_count: int
        - unmatched_count: int
        - unmatched_urls: list[str]
        """
```

Run the 5 SQL queries from `_shared_context.md`. Use `sqlalchemy.text()` with parameterized queries. RLS scopes connection queries to `app_user_id`.

**Important details:**
- Query 1 returns matched mutuals. Compare against `request.mutual_urls` to compute `unmatched_urls` and counts.
- Query 2 only runs for top 50 mutuals by affinity_score (not all).
- If target not found in DB, raise a clear error (target should always be enriched before best-hop triggers).

### 3. Prompt Building Method

```python
    def build_prompt(self, context: BestHopContext) -> str:
        """Build the system prompt with injected context.

        Reads the prompt template from prompts/best_hop_ranking.md (subphase E),
        then injects:
        - Target profile + experience as structured text
        - Each mutual's profile + experience + affinity data
        - Whether target is a direct connection
        """
```

Format the context as structured text sections within the prompt. The LLM should receive something like:

```
## Target
Name: Chandra Sekhar Kopparthi
Position: VP Engineering at Stripe
Experience: [formatted list]

## Your Mutual Connections (18 found, ordered by affinity)

### 1. John Doe (affinity: 82, tier: inner_circle)
Position: Senior Engineer at Stripe
Experience: [formatted list]
...
```

### 4. LLM Ranking Method

```python
    def rank(self, request: BestHopRequest) -> Generator[BestHopResultItem, None, BestHopDone]:
        """Assemble context, call LLM, merge results.

        Yields BestHopResultItem for each ranked candidate.
        Returns BestHopDone with summary stats on completion.

        Uses SEARCH_LLM_MODEL via llm_client.call_llm_with_tools().
        Tools available: get_profile_detail, execute_sql (safety net).
        """
```

**LLM call details:**
- Use `llm_client.call_llm_with_tools()` with the same model as search agent (`SEARCH_LLM_MODEL` from config).
- System prompt: built by `build_prompt()` with all context injected.
- User message: "Rank the top mutual connections for introducing me to {target_name}. For each, explain why they're a good connector."
- Tools: `get_profile_detail` and `execute_sql` available as safety net (same tool definitions as search agent).
- Expected: LLM returns structured JSON with `[{crawled_profile_id, rank, why_this_person}, ...]`.

**Result merge:**
- Build a lookup dict from Query 1 results keyed by `crawled_profile_id`.
- For each LLM result, enrich with SQL-sourced fields: `connection_id`, `full_name`, `current_position`, `current_company_name`, `affinity_score`, `dunbar_tier`, `linkedin_url`.
- Yield `BestHopResultItem` per candidate.

### 5. Helper Dataclasses

Define at module level or in a separate `_types.py` if needed:

```python
@dataclass
class BestHopContext:
    target_profile: dict
    target_experience: list[dict]
    target_connection: dict | None
    mutuals: list[dict]
    mutual_experience: dict[str, list[dict]]
    matched_count: int
    unmatched_count: int
    unmatched_urls: list[str]

@dataclass
class BestHopDone:
    total: int
    matched: int
    unmatched: int
    session_id: str
```

## Verification

```bash
# Unit test: mock DB session, verify query construction
pytest tests/unit/intelligence/ -k "best_hop" -v

# Import check
python -c "from linkedout.intelligence.services.best_hop_service import BestHopService"
```

## What NOT to Do

- Do not extend `BaseService` — this is not CRUD
- Do not add web search or vector search — all data comes from batch SQL
- Do not add WhyThisProfile explainer — the LLM's `why_this_person` is the explanation
- Do not hard-code SQL strings outside the service — keep queries co-located
