# Phase C: Prompt Simplification + SQL Resilience

**Effort:** 1 session
**Dependencies:** Phase A (funding tables referenced in prompt), Phase B (web search referenced in prompt)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Replace the prescriptive 94-line system prompt with a simpler capabilities-oriented prompt. The spike proved the LLM reasons better with fewer constraints. Also add SQL resilience rules.

## What to Do

### 1. Read the current prompt

**File:** `./src/linkedout/intelligence/prompts/search_system.md`

Understand the current structure before modifying.

### 2. Simplify the prompt

**Remove:**
- The prescriptive "When to Use Which Tool" decision table (roughly lines 46-54)
- The "Think Before You Write" rules that lock specific tools to specific query patterns (roughly lines 3-12)
- Any sections that tell the LLM *when* to use which tool in a rigid way

**Replace with** a simpler capabilities summary:
```markdown
## Your Capabilities

You have access to the user's LinkedIn network database (~28K connections) and web search.

- **Database tools** let you query connections, experience history, education, skills, 
  company data, and funding information
- **Web search** lets you look up anything not in the database — company info, investors, 
  industry context, recent news
- **Semantic search** lets you find people by meaning/concept when SQL isn't enough
- **Helper tools** resolve company names, classify companies, analyze career patterns

Be thorough. Combine multiple tools for complex queries. A good answer to 
"who can intro me to X" might use web search (learn about the company/investors), 
database queries (find connections), and career analysis (identify warm paths).
```

**Keep unchanged:**
- Schema context section (tables, columns, types)
- Enum values (dunbar tiers, affinity ranges, etc.)
- Output format requirements
- Safety/security rules
- Result set tool guidance (tag_profiles, compute_facets) — but note D.3 will later remove filter/exclude/rerank references

### 3. Add SQL resilience rules

Add to the Rules section:
```markdown
- **Zero-result fallback:** If a query returns 0 results, try a simpler version before giving up. 
  Remove the most restrictive filter.
- **Timeout recovery:** If SQL times out (5s limit), simplify. Prefer UNION of simple queries 
  over one complex multi-JOIN query.
```

### 4. Read the spec before modifying

**Read:** `./docs/specs/linkedout_intelligence.collab.md`

Ensure prompt changes are consistent with the spec. Note any spec sections that will need updating (tracked in Phase H.4).

## Verification

```bash
# Unit tests still pass
pytest tests/unit/intelligence/ -v

# Eval suite (if available)
pytest tests/eval/ -m eval -v 2>/dev/null || echo "Eval tests not configured"

# Manual: read the prompt and verify it's shorter, clearer, and references web search + funding
cat ./src/linkedout/intelligence/prompts/search_system.md
```

## Expected Impact

Unlocks natural LLM reasoning. The LLM will use tools based on its own judgment rather than following a rigid decision tree. Combined with Phase A+B, this should produce measurably better results.

## Caution

This is a high-risk change — prompt changes can cause unexpected regressions. After this phase, run the benchmark (or at least a subset of queries manually) to verify quality hasn't degraded.
