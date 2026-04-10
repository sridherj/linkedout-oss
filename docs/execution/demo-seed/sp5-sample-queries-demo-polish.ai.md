# Sub-phase 5: Sample Queries & Demo Experience Polish

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP5 |
| Dependencies | SP3 (successful demo restore flow), SP6 (demo user profile must match generation) |
| Estimated effort | 1 session (~3 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-08-demo-seed-plan.md` — Sub-phase 5 |
| Spec reference | `backend/docs/specs/onboarding-experience.md` |

## Objective

After demo restore, the user sees sample queries demonstrating all three pillars (search, affinity, AI agent). Each query has followups. The demo user's profile is explained so affinity scores make sense. A `linkedout demo-help` command re-shows these at any time.

## Context

This sub-phase is the "wow moment" for demo users — the first queries they run should produce meaningful, impressive results. The sample queries are curated for educational value and must work with the demo dump produced by SP6. The demo user profile description must match what's actually in the dump.

### Key existing files (read these before implementing)

- `backend/src/linkedout/commands/restore_demo.py` — Modify to show sample queries after restore (from SP2)
- `backend/src/linkedout/setup/demo_offer.py` — Modify to show sample queries after demo setup (from SP3)
- `backend/src/linkedout/cli.py` — Command registration

## Tasks

### 1. Create sample queries module

Create `backend/src/linkedout/demo/sample_queries.py`:

- `DEMO_USER_PROFILE_DESCRIPTION`: Multi-line string describing the demo user's identity (founder/CTO composite, Bengaluru-based, ML + product + data skills, 8 years experience). Written as prose, not a data structure.

- `SAMPLE_QUERIES`: List of dicts, each with `category` (search/affinity/agent), `query`, `explanation`, `followups` (list of strings). Example queries:
  1. **Semantic search:** "Who in my network has experience with distributed systems at a Series B startup?" — Followup: "Tell me more about [name]'s background"
  2. **Affinity:** "Who are my strongest connections in ML?" — Followup: "Why does [name] score higher than [name]?" — Explanation: scores reflect shared skills, company overlap, seniority proximity
  3. **AI agent:** "Compare the top 3 data scientists in my network for a founding engineer role" — Followup: "Draft a reachout message for [name]"

- `format_sample_queries() -> str`: Returns formatted string with all queries, suitable for terminal output. Uses section headers, indentation, and color (via click.style).

- `format_demo_profile() -> str`: Returns the profile description formatted for terminal output.

### 2. Create demo-help command

Create `backend/src/linkedout/commands/demo_help.py`:

- Click command `demo-help`
- Prints the demo profile description followed by sample queries
- Works regardless of demo mode (informational, not gated)

### 3. Integrate with restore and setup flows

- Modify `restore_demo.py` to call `format_demo_profile()` and `format_sample_queries()` after successful restore.
- Modify `demo_offer.py` to show sample queries after successful demo setup in the orchestrator flow.

### 4. Register command in CLI

Register `demo-help` in `cli.py`.

## Verification Checklist

- [ ] After `linkedout restore-demo` or setup demo acceptance, sample queries are printed
- [ ] Sample queries cover: semantic search, affinity/relationship, AI agent
- [ ] Each sample includes 1-2 followup queries
- [ ] The demo user profile is described (role, company, location, skills, experience years)
- [ ] `linkedout demo-help` re-displays all sample queries and profile explanation
- [ ] Explanations include "why" behind affinity scores (shared company, skills, seniority)
- [ ] All tests pass

## Design Notes

- **Hardcoded queries:** The sample queries are hardcoded strings, not generated from DB content. Intentional — they're curated for educational value and work with any demo dump that has the expected profile distribution.
- **Data coupling:** The demo user profile description must match what's in the dump (SP6). This creates a coupling. Mitigated by using the same constant for generation and display. If the dump changes significantly, update the queries in the same PR.
