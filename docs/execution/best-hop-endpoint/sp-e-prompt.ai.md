# Sub-phase E: Best Hop Prompt

**Effort:** 30-45 minutes
**Dependencies:** None (can start anytime, but must be done before F)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Create the system prompt template for LLM-based best-hop ranking.

## What to Do

### 1. Create prompt file

**File:** `src/linkedout/intelligence/prompts/best_hop_ranking.md`

### 2. Prompt Structure

The prompt should follow the same markdown template pattern as `search_system.md`. Key sections:

**Role & Task:**
- You are ranking mutual connections as potential introduction paths
- You receive pre-assembled data about the target and each mutual connection
- Rank by combining two signals: user's affinity with mutual (pre-computed) + mutual's likely closeness to target (inferred)

**Two-Hop Ranking Framework:**
- Leg 1 (User → Mutual): affinity_score, dunbar_tier, affinity_career_overlap, affinity_external_contact, affinity_recency
- Leg 2 (Mutual → Target): inferred from shared companies, overlapping roles, seniority proximity, location, industry alignment

**Ranking Signals to Consider:**
- Same current/past company as target (strongest signal)
- Same industry/role function
- Seniority proximity (VP introducing to VP > intern introducing to VP)
- Geographic proximity
- Recency of connection (recently connected = more likely active relationship)
- High affinity with the user (easier to ask for the intro)

**Output Format:**
```json
[
  {
    "crawled_profile_id": "cp_xxx",
    "rank": 1,
    "why_this_person": "John worked at Stripe with the target for 3 years (2019-2022) and you have a strong affinity (82). He's your best path because of the direct professional overlap."
  },
  ...
]
```

- Return up to 30 ranked results
- `why_this_person` should be 1-2 sentences explaining both legs (why they know the target + why they'd help you)
- Output ONLY the JSON array, no preamble

**Context Injection Point:**
The service (subphase C) will inject the assembled data below the template. Mark the injection point:
```
{context}
```

### 3. Prompt Design Principles

- Keep it concise (under 50 lines of template text)
- Be specific about the two-hop ranking framework
- Don't prescribe exact weights — let the LLM synthesize
- Include the output format specification inline
- Mention tools are available as a safety net but discourage use ("You already have all the data you need. Only use tools if something critical is missing.")

## Verification

```bash
# File exists and is readable
cat src/linkedout/intelligence/prompts/best_hop_ranking.md | head -5

# Template has context injection point
grep '{context}' src/linkedout/intelligence/prompts/best_hop_ranking.md
```

## What NOT to Do

- Do not over-engineer the prompt — start simple, iterate based on test results
- Do not add few-shot examples in v1 — the structured context is sufficient
- Do not reference specific tools by name in the prompt — just mention they're available if needed
