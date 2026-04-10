# Sub-phase B: Best Hop Contracts

**Effort:** 15-20 minutes
**Dependencies:** None (can start immediately)
**Working directory:** `.`
**Shared context:** `_shared_context.md`
**Agent:** `schema-creation-agent` (or manual — simple enough)

---

## Objective

Add `BestHopRequest` and `BestHopResultItem` Pydantic models to `contracts.py`.

## What to Do

### 1. Add contracts to `contracts.py`

**File:** `src/linkedout/intelligence/contracts.py`

```python
class BestHopRequest(BaseModel):
    """Incoming best-hop ranking request from the Chrome extension."""
    target_name: str                     # "Chandra Sekhar Kopparthi"
    target_url: str                      # "https://linkedin.com/in/chandrasekharkopparthi"
    mutual_urls: list[str]               # LinkedIn URLs from mutual connections page
    session_id: Optional[str] = None     # Resume existing session (future)


class BestHopResultItem(BaseModel):
    """Single ranked result in best-hop SSE stream.

    The LLM returns rank + why_this_person. Service merges in
    SQL-sourced fields (connection_id, full_name, etc.) before
    emitting as an SSE result event.
    """
    rank: int
    connection_id: str
    crawled_profile_id: str
    full_name: str
    current_position: Optional[str] = None
    current_company_name: Optional[str] = None
    affinity_score: Optional[float] = None
    dunbar_tier: Optional[str] = None
    linkedin_url: Optional[str] = None
    why_this_person: str
```

### 2. Verify imports

Ensure both models are importable:

```python
from linkedout.intelligence.contracts import BestHopRequest, BestHopResultItem
```

## Verification

```bash
# Import check
python -c "from linkedout.intelligence.contracts import BestHopRequest, BestHopResultItem; print('OK')"

# Existing tests still pass
pytest tests/unit/intelligence/ -v

# Validate schema
python -c "
from linkedout.intelligence.contracts import BestHopRequest, BestHopResultItem
r = BestHopRequest(target_name='Test', target_url='https://linkedin.com/in/test', mutual_urls=['https://linkedin.com/in/a'])
print(r.model_dump())
i = BestHopResultItem(rank=1, connection_id='c1', crawled_profile_id='p1', full_name='Test', why_this_person='reason')
print(i.model_dump())
"
```

## What NOT to Do

- Do not modify existing contracts
- Do not add request/response wrappers beyond what's specified — the SSE stream uses `BestHopResultItem` directly as the `result` event payload
