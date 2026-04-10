# Sub-phase 7: Documentation & Getting-Started Update

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP7 |
| Dependencies | SP4 (all demo commands finalized), SP5 (sample queries finalized) |
| Estimated effort | 0.5 sessions (~2 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-08-demo-seed-plan.md` — Sub-phase 7 |

## Objective

`docs/getting-started.md` describes the demo experience prominently. Users who read the docs know they can try demo mode. The README links to it. All demo CLI commands are documented with examples.

## Context

Documentation should make the demo path the most visible option for new users. The "Quick Demo" section should appear before the full setup instructions so users see the fastest path to value first.

### Key existing files (read these before implementing)

- `docs/getting-started.md` — Main setup guide (add demo section)
- `README.md` — Quick-start section (add demo mention)

## Tasks

### 1. Update docs/getting-started.md

- Add a "Quick Demo (2 minutes)" section right after Prerequisites
- Show the demo setup flow: `linkedout setup` -> accept demo offer -> try sample queries
- Explain what's in the demo: 2K profiles, search, affinity, AI agent
- Explain how to reset (`linkedout reset-demo`) and transition (`linkedout setup` again or `linkedout use-real-db`)
- Link to the full setup for real data

### 2. Add demo command reference

Add to `docs/getting-started.md` or a new `docs/demo.md`:

- `linkedout download-demo` — download demo database dump
- `linkedout restore-demo` — restore demo into `linkedout_demo`
- `linkedout reset-demo` — reset demo to original state
- `linkedout use-real-db` — switch to real database
- `linkedout demo-help` — show sample queries and demo profile

Each command should have a brief description and usage example.

### 3. Update README.md quick-start

Mention demo option in the quick-start section of README.md so users know about it immediately.

## Verification Checklist

- [ ] `docs/getting-started.md` has a "Try the Demo" section before or immediately after Prerequisites
- [ ] All demo commands are listed with descriptions and examples
- [ ] The demo flow is shown as an alternative path in the setup instructions
- [ ] `README.md` mentions "try with demo data" in the quick-start section

## Design Notes

No flags. Straightforward documentation update.
