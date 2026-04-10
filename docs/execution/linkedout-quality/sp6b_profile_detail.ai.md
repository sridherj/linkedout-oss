# Sub-phase 6b: Profile Questions & Detail View

## Prerequisites
- **SP5 complete** (session context must persist so returning from profile detail doesn't re-trigger search)

## Outcome
Users click profiles to see a slide-over panel with full details (4 tabs: Overview, Experience, Affinity, Ask). Users ask questions about profiles using existing data. External enrichment only on explicit request. Result cards show fixed scaffold + LLM-driven highlighted attributes.

## Estimated Effort
3-4 sessions

## Verification Criteria
- [ ] Click profile -> slide-over with full details. Click another -> panel updates. Close -> results unchanged
- [ ] "How long has X been in AI?" -> answered from stored data without external calls
- [ ] "Check if Y has published papers" -> system informs user this needs external lookup, confirms before proceeding
- [ ] Result cards show fixed zones (name, headline, role/company, affinity, tags, WhyThisProfile) + LLM-driven 2-3 highlighted attributes
- [ ] Profile question suggestions are profile-specific and query-aware

---

## Activities

### 6b.1 `get_profile_detail` Tool
- **Shared with SP6a** (registered as one of the conversational tools)
- Must return all data needed by all four panel tabs:
  - **Overview:** `why_this_person_expanded` (full paragraph, longer than card version), `key_signals: [{icon, label, value, color_tier}]` (3 items with full-sentence explanations)
  - **Experience:** `experiences: [{role, company, start_date, end_date, duration, is_current}]` -- FULL list, no truncation
  - **Education:** `education: [{school, degree, start_year, end_year}]`
  - **Skills:** `skills: [{name, is_featured}]` -- `is_featured` = relevant to current query (accent-highlighted in UI)
  - **Affinity:** `affinity: {score, tier, tier_description, sub_scores: [{name, value, max_value}]}` -- sub-scores: recency, career_overlap, mutual_connections
  - **Connection:** `connected_date`, `connection_source`
  - **Tags:** list of tags applied to this profile
- `suggested_questions: [str]` -- 3 profile-specific, query-aware question suggestions for Ask tab (LLM-generated)
- Implementation: SQL query with JOINs across `connection > crawled_profile > experience > company + education + profile_skill`, formatted as structured JSON

### 6b.2 Frontend: Profile Slide-Over Panel
- **Design reference:** `<linkedout-fe>/docs/design/profile-slideover-panel.html`
- Fixed panel on right side (520px default, 600px on ≥1400px, 680px on ≥1800px), slides in with animation (0.25s ease-out)
- Backdrop overlay, non-selected cards dim to 0.45 opacity
- **Panel header:** large avatar (52px), name, headline, location + connected date, affinity + tier badges, LinkedIn link, close button
- **Tab navigation:** Overview | Experience | Affinity | Ask (marked "New")
- **Overview tab:**
  1. Why This Person -- expanded version (accent-left-bordered, full paragraph with network proximity reasoning)
  2. Key Signals (labeled "AI") -- 3 expanded rows: icon + label (mono uppercase) + value (full sentence). Color-coded backgrounds (purple, rose, sage)
  3. Experience Timeline -- full chronological list, vertical line connecting dots, current role with "Current" badge
  4. Education -- school icon + name + degree + dates
  5. Skills -- grid of tags, featured skills in accent color
- **Affinity tab:** large score number (2.5rem, accent), sub-score breakdown bars, Dunbar tier info box
- **Ask tab (panel footer, always visible):** "Ask about {name}" input + send button + 3 suggestion chips

### 6b.3 Profile Questions (Existing Data)
- LLM uses `get_profile_detail` + existing SQL tools to answer questions
- No external calls unless explicitly requested
- Example: "How long has X been in AI?" -> fetch profile detail, compute from experience records
- Natural LLM behavior -- no special implementation beyond the tool

### 6b.4 External Enrichment Flow
- When user explicitly requests: inform user, confirm before proceeding
- Use existing Apify infrastructure for LinkedIn re-crawl
- Add `request_enrichment` tool that returns confirmation prompt before proceeding
- **Security constraint:** Decision #8 -- "External enrichment is always user-triggered". Tool must NOT auto-trigger.

### 6b.5 LLM-Driven Result Card Content
- **Design reference:** `<linkedout-fe>/docs/design/result-cards-highlighted-attributes.html`
- **Fixed scaffold:** avatar + name + affinity badge + Dunbar tier badge + headline + location + role summary + Why This Person box + footer (connected date + LinkedIn + View profile)
- **LLM-driven zone:** 2-3 highlight chips from SP3b `highlighted_attributes`, rendered as colored pills:
  - Lavender (color_tier 0), Rose (color_tier 1), Sage (color_tier 2)
  - Each chip: dot indicator + short text
  - Max 3 chips per card
- **Unenriched profile state:** card dimmed (0.85 opacity), no chips, "Enrich" prompt bar instead, why-box at lower opacity (0.7)
- Start fully LLM-driven, lock down scaffold based on what works (Decision #14)

### 6b.6 Backend Response Format
- All search responses need consistent profile data shape across cards, conversation, and slide-over
- Same profile appears at different detail levels:
  - **Card:** name, headline, affinity, dunbar_tier, why_this_person (2-3 sentences), highlighted_attributes (max 3), is_enriched, connected_date
  - **Conversation mention:** name, brief reference
  - **Slide-over:** full detail (all tabs)
- Consider `detail_level` parameter or separate endpoints

---

## Design Review Notes

| ID | Issue | Resolution |
|----|-------|------------|
| Architecture | Slide-over preserves search context | Frontend must NOT navigate away. Slide-over/drawer pattern correct |
| Security | External enrichment only on explicit request | `request_enrichment` tool must NOT auto-trigger (Decision #8) |
| Error path | Profile data incomplete | Display what's available, indicate missing sections. Don't show "None" literal |
| Architecture | Profile detail has 4 tabs | `get_profile_detail` response must cover all tabs' data needs |
| Architecture | Ask tab needs profile-specific suggestions | LLM-generated `suggested_questions` in profile detail response |

## Key Files to Read First
- `src/linkedout/intelligence/explainer/why_this_person.py` -- current explainer (for expanded version)
- `<linkedout-fe>/docs/design/profile-slideover-panel.html` -- UI design (4 tabs)
- `<linkedout-fe>/docs/design/result-cards-highlighted-attributes.html` -- card design
- `src/linkedout/intelligence/agents/search_agent.py` -- tool registration
- `docs/specs/linkedout_intelligence.collab.md` -- current spec
