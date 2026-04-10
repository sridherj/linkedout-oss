# LinkedOut OSS

Open-source professional network intelligence tool. Python/FastAPI backend + Chrome extension + CLI.

## Behavioral Guidelines

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Scaffold First, Fill Later

**When dealing with a large problem, always scaffold first and fill later.**

1. Think through various ways by which you can decompose the problem
2. Extract out logical components
3. Then, and only then, fill in the details.
4. Look for opportunities to generalize (inheritance, modularity etc)

Ask yourself: "Would a senior architect decompose the problem into these components? Why/why not?"

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" -> "Write tests for invalid inputs, then make them pass"
- "Fix the bug" -> "Write a test that reproduces it, then make it pass"
- "Refactor X" -> "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

## Repo Structure

```
linkedout-oss/
├── backend/          # Python/FastAPI backend (has its own CLAUDE.md)
│   ├── src/
│   ├── migrations/   # Alembic
│   └── tests/
├── extension/        # Chrome extension (optional add-on)
├── skills/           # Cross-platform skill definitions
│   ├── claude-code/
│   ├── codex/
│   └── copilot/
├── seed-data/        # Seed data scripts
└── docs/             # All project documentation
    ├── specs/        # Product specs — source of truth (.collab.md)
    ├── decision/     # Architecture decision records (.collab.md)
    ├── plan/         # Planning docs (.collab.md)
    ├── execution/    # Agent-generated execution plans (.ai.md)
    ├── writeup/      # Human-written requirements/reviews (.human.md)
    ├── design/       # UX design docs (.human.md)
    ├── brand/        # Logos and brand assets
    ├── reference/    # Reference materials
    └── extension/    # Extension-specific docs (design system, schema mapping)
```

## Specs (Source of Truth)

Product specs are the **authoritative description** of how every feature works. They are not documentation — they are the contract. Each spec defines behavior, data contracts, edge cases, error handling, and cross-references to related specs. When code and spec disagree, the spec is right (or needs updating — never silently ignored).

- **Canonical location:** `docs/specs/`
- **Registry:** `docs/specs/_registry.md` — index of all specs with module, version, and last-verified date
- **When to consult:** Before modifying any feature. Before asking "how does X work?". Before planning changes.
- **Priority:** Check specs **first** — before reading code, before reading agents, before reading plans.
- **Updating specs:** If your changes alter a feature's behavior, update the spec to match. Bump the version number.

## Decision Records

Significant technical decisions are documented in `docs/decision/` as lightweight ADRs.
- **Format:** `YYYY-MM-DD-<short-slug>.collab.md` with Question, Key Findings, Decision, Implications
- **When to create:** go/no-go calls, architecture picks, tool/data source selections, strategy changes

## Documentation Authorship Convention

All authored `.md` files under `docs/` use authorship suffixes:

- **`.ai.md`** — AI/agent-authored (execution sub-phases, research, summaries)
- **`.human.md`** — Human-authored (requirements, writeups, UX designs)
- **`.collab.md`** — Collaborative (specs, plans, decision records, design reviews)

**Defaults by directory:**
| Directory | Default | Rationale |
|-----------|---------|-----------|
| `execution/` | `.ai.md` | Agent-generated execution plans |
| `writeup/` | `.human.md` | Human-written requirements |
| `design/` | `.human.md` | Human-authored UX designs |
| `plan/` | `.collab.md` | Plans refined by human + AI |
| `specs/` | `.collab.md` | Specs co-authored and reviewed |
| `decision/` | `.collab.md` | Decision records |

**Graduation:** Rename `.ai.md` -> `.collab.md` when human edits significantly.

**No suffix:** `_`-prefixed meta files (`_shared_context.md`, `_manifest.md`, `_registry.md`), non-markdown files, structured data.

**Date prefixes:** Plan and decision files use `YYYY-MM-DD-<slug>` format when tied to a specific date. Phase-numbered files skip dates.

## Design System

`docs/extension/linkedout-design-system.md` — font choices, colors, spacing, and aesthetic direction.
Always read before making any visual or UI decisions. Do not deviate without explicit user approval.

## Learnings

Reusable engineering principles from past sessions are in `backend/plan_and_progress/LEARNINGS.md` (if present).
- **When to consult:** Before debugging, before designing a new system, before making architectural choices
