# Sub-phase 04: Spec Updates

## Metadata
- **Depends on:** 01, 02a-d, 03 (documents behaviors implemented in those phases)
- **Blocks:** nothing
- **Estimated scope:** 1 file modified
- **Plan section:** Phase 4 (4a-4e)

## Context

Read `_shared_context.md` for system record IDs and conventions being documented.

## Task

**File:** `docs/specs/onboarding-experience.md`

### 4a. Bootstrap behavior — under "Common Infrastructure (Steps 1-4)"

Add:
> **System record bootstrap after migrations**: Step 3 (Database Setup) bootstraps the
> system tenant (`tenant_sys_001`), business unit (`bu_sys_001`), and app user
> (`usr_sys_001`) via idempotent INSERTs (`ON CONFLICT DO NOTHING`) after Alembic
> migrations succeed. These records are FK targets for `connection.tenant_id`,
> `connection.bu_id`, `connection.app_user_id`, `enrichment_event.tenant_id`, and all
> RLS-scoped operations. Without them, CSV import and enrichment fail with FK violations.

### 4b. Degradation behavior for optional keys — under "Full Setup Prompt Principles"

Add documentation for:
- **Without OpenAI key (local embeddings):** Local nomic model, 768-dim vs 1536-dim,
  slightly lower quality, ~0.2s/profile on CPU. Marginal difference under 5K profiles.
- **Without Apify key (no enrichment):** Stub profiles only (name, company, title, URL).
  No work history/education/skills. Affinity falls back to connection-level signals.
  Queries like "who has ML experience?" return incomplete results.

### 4c. Non-TTY behavior — under "Implementation Conventions"

Add:
> **EOFError handling in setup prompts**: Every `input()` and `getpass()` call wraps with
> `try/except (EOFError, KeyboardInterrupt)` and defaults to the safe/conservative choice.
> Enables non-interactive execution via AI skills and CI pipelines. Pattern follows
> `demo_offer.py`.

### 4d. Implementation conventions — new section before "Decisions"

Add three conventions:
1. CLI entry point for subprocesses (`linkedout` not `sys.executable`)
2. Timestamps in raw SQL (`NOW()` for `created_at`/`updated_at`)
3. Skill pre-configuration (collect inputs before invoking setup)

### 4e. Metadata updates

- Bump `version:` from 3 to 4
- Update `last_verified:` to `2026-04-10`
- Add `Updated:` line noting bootstrap, degradation, non-TTY, conventions

## Completion Criteria
- [ ] Bootstrap behavior documented
- [ ] Degradation behavior documented
- [ ] Non-TTY behavior documented
- [ ] Implementation conventions section added
- [ ] Metadata bumped to v4
