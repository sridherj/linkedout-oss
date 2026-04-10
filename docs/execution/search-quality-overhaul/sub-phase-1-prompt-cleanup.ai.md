# Sub-Phase 1: System Prompt Cleanup (Phase 1b + 1c)

**Working directory:** `./`
**Depends on:** Nothing
**Modifies:** `src/linkedout/intelligence/prompts/search_system.md`

## Context

The search system prompt teaches the LLM SQL patterns, but some are broken:
- Lines 69-73: Business rules referencing `co.industry`, `co.size_tier`, `co.estimated_employee_count` — these columns are ALL NULL across 47K companies. However, company enrichment is in progress and will populate these columns. **Do NOT replace these with name-based ILIKE workarounds** (Phase 1a was dropped).
- Lines 79-87: Few-shot examples use `company_alias` table which has 0 rows.
- No warnings about partial data coverage for seniority/function fields.

## Review Decisions

- **Arch-1:** Phase 1a (hardcoded company name lists) is DROPPED. The existing column-based filters for `co.industry`, `co.size_tier` etc. stay as-is — they'll work once enrichment lands.

## Tasks

### 1b. Fix few-shot SQL examples (lines 79-87)

**File:** `src/linkedout/intelligence/prompts/search_system.md`

Remove the company alias fallback example block (lines 79-87):
```markdown
**Company lookup — always check aliases:**
```sql
-- When filtering by company name, always include company_alias fallback
WHERE (co.canonical_name ILIKE '%google%'
   OR EXISTS (
     SELECT 1 FROM company_alias ca
     WHERE ca.company_id = co.id AND ca.alias_name ILIKE '%google%'
   ))
```
```

Replace with:
```markdown
**Company lookup:**
```sql
-- When filtering by company name, use canonical_name with ILIKE.
-- Note: company names have variants (e.g., 'Tata Consultancy Services',
-- 'Tata Consultancy Servicess', 'TCS'). Use broad patterns.
WHERE co.canonical_name ILIKE '%google%'
```
```

### 1c. Add data availability warnings

Add a new section after the business rules table (after line 75) and before the "Few-Shot SQL Examples" section:

```markdown
## Data Availability Warnings

- ~79% of experience records have `seniority_level`; ~63% have `function_area`. When filtering by seniority or function, add an ILIKE fallback on `current_position` to catch unclassified profiles.
- `co.industry`, `co.size_tier`, and `co.estimated_employee_count` are being populated by an enrichment pipeline. Until complete, some company-type queries may return fewer results than expected.
```

## Verification

1. Read the modified file and confirm:
   - No reference to `company_alias` table in few-shot examples
   - Data availability warnings section exists
   - Business rules for `co.industry` etc. (lines 69-73) are UNCHANGED
2. Run: `cd . && python -c "from linkedout.intelligence.prompts import search_system; print('prompt loads OK')"`
   - If the prompt is loaded differently (e.g., read from file), just confirm the .md file is valid markdown
