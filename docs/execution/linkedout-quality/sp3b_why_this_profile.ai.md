# Sub-phase 3b: "Why This Profile" Improvement

## Prerequisites
- **SP2 complete** (better search results feed better explainer inputs; Langfuse enables debugging)

## Outcome
Profile explanations are 2-3 sentences with explicit match dimensions. Full profile context (all experiences, education, company metadata, affinity). Output includes `highlighted_attributes` for result card content slots.

## Estimated Effort
2-3 sessions

## Verification Criteria
- [ ] 10 representative benchmark queries: each explanation references specific match dimensions relevant to the query
- [ ] No truncation: profiles with 15+ roles show relevant experience from the full history
- [ ] Explanations reference education, company metadata, and network proximity when relevant
- [ ] Output includes `highlighted_attributes: [{text, color_tier}]` per profile (max 3)
- [ ] Latency: <3s per batch of 10 profiles

---

## Activities

### 3b.1 Study Claude Code's Reasoning Patterns
- From gap analysis artifacts (`spike_query_traces/gap_analysis.md`): capture how Claude Code cites career trajectory patterns, company stage alignment, skill depth, network proximity, tenure velocity, seniority progression
- LinkedOut currently cites none of these (gap analysis Q1-Q5 all show raw filter results without inference)
- Document the reasoning patterns as a template for the new explainer prompt

### 3b.2 Expand Profile Context
- **Current:** 5 most recent roles + 10 skills (truncated)
- **New:** fetch full profile data per profile:
  - All experience records (not truncated)
  - Education records
  - Company metadata per experience: `company.size_tier`, `company.industry`
  - Affinity score + sub-scores: `affinity_recency`, `affinity_career_overlap`, `affinity_mutual_connections` (exist in DB, currently unused)
  - Dunbar tier
  - Connection metadata (date connected, source)
- Implementation: modify data fetching in `why_this_person.py`. Single query with JOINs across `connection > crawled_profile > experience > company + education + profile_skill`
- **Key file:** `src/linkedout/intelligence/explainer/why_this_person.py`

### 3b.2.5 Rewrite Explainer Infrastructure (Plan Review Amendment C1)
- **Current `_fetch_enrichment_data()`** only fetches experiences + skills (2 queries). Expand to include education, company metadata (size_tier, industry), affinity sub-scores, Dunbar tier, connection metadata
- **Current `_PROMPT_TEMPLATE`** expects "ID: explanation" text format. Rewrite for structured JSON output with `explanation` + `highlighted_attributes`
- **Current `_parse_explanations()`** parses plain text. Replace with JSON parser that produces `dict[str, dict]` (connection_id -> {explanation, highlighted_attributes}) instead of `dict[str, str]`
- **Update `WhyThisPersonExplainer.explain()` return type** accordingly
- This is a full rewrite of the prompt + parser + return type — not incremental changes

### 3b.3 Rewrite Explainer Prompt
- 2-3 sentences per profile with explicit match dimensions
- Query-aware: deeply reason about mapping between query intent and profile attributes
- Example output: "Relevant because: 8 years in backend engineering with Kubernetes expertise at both Flipkart (startup) and Microsoft (big tech). Currently 18 months at current role -- below their average tenure of 2.4 years, suggesting potential openness to new opportunities."
- Structured output format:
  ```json
  {
    "connection_id": "conn_abc123",
    "explanation": "...",
    "highlighted_attributes": [
      {"text": "IC → PM in 18 mo", "color_tier": 0},
      {"text": "3 promos in 4 yrs", "color_tier": 1},
      {"text": "Series B → growth", "color_tier": 2}
    ]
  }
  ```

### 3b.4 Output Format for Result Cards
- Each profile must include fields needed by the result card design (`<linkedout-fe>/docs/design/result-cards-highlighted-attributes.html`):
  - `explanation` (2-3 sentences)
  - `highlighted_attributes: [{text, color_tier}]` (max 3 chips)
  - `color_tier` assignment: primary match dimension = 0 (lavender), secondary = 1 (rose), tertiary = 2 (sage)
- For unenriched profiles: `highlighted_attributes` is empty, `explanation` is lower-confidence with caveat
- Use a **fixed set of attribute types** (skill_match, company_match, career_trajectory, network_proximity, tenure_signal, seniority_match) rather than freeform strings -- ensures stability for frontend consumption

### 3b.5 Batch Processing for Large Result Sets
- Split results into batches of **10 profiles** (not 20 -- Plan Review Amendment P1)
- Full profile data is ~2,000+ tokens/profile; 10 x 2K = 20K tokens keeps within context window
- Process batches in parallel where possible
- Monitor token usage via Langfuse

### 3b.6 Instrument with Langfuse
- Span per batch: input token count, output token count, latency
- Per-profile logging: which attributes were cited, explanation length

### 3b.7 Validate
- Run 10 representative queries through the benchmark
- Manual inspection: do explanations help understand why each person was returned?
- Latency check: <3s per batch of 10 profiles
- **Error path:** If LLM returns malformed JSON, parse with fallback: extract explanation text only, set `highlighted_attributes` to empty array. Log parse failure to Langfuse.

---

## Design Review Notes

| ID | Issue | Resolution |
|----|-------|------------|
| C1 | WhyThisProfile prompt + parser need full rewrite for structured JSON with `highlighted_attributes` | Activity 3b.2.5 covers prompt, parser, return type rewrite |
| P1 | Token budget: 2K+ tokens/profile x 20 = 40K+ | Batch size reduced to 10 (Plan Review amendment) |
| Spec conflict | `linkedout_intelligence.collab.md` > "1-sentence explanations" | Changes to 2-3 sentences. `/update-spec` deferred to SP4 |
| Spec conflict | `linkedout_intelligence.collab.md` > "ID: explanation" format | Changes to structured JSON. `/update-spec` deferred to SP4 |
| Architecture | `highlighted_attributes` stability | Fixed attribute types for frontend stability |

## Key Files to Read First
- `src/linkedout/intelligence/explainer/why_this_person.py` -- current explainer (full rewrite target)
- `.taskos/exploration/playbook_why_this_profile.ai.md` -- detailed playbook for this work
- `spike_query_traces/gap_analysis.md` -- Claude Code reasoning patterns to emulate
- `<linkedout-fe>/docs/design/result-cards-highlighted-attributes.html` -- UI design for result cards
- `docs/specs/linkedout_intelligence.collab.md` -- current spec for WhyThisProfile
