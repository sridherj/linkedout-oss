# Decision: Drop SearchHistory without data migration

**Date:** 2026-04-04
**Status:** Accepted
**Context:** LinkedOut search feature -- consolidating data models

## Question
Should SearchHistory data be migrated into SearchSession, or can the table be dropped cleanly?

## Key Findings
- SearchSession + SearchTurn already captured all active search data since multi-turn was introduced
- SearchHistory was being dual-written but never read by the primary search flow
- The history page was the only consumer, and it was migrated to use SearchSession
- No user-facing "saved searches" existed on the old model that would be lost
- `query_type` (only field unique to SearchHistory) was diagnostic metadata, not user-facing

## Decision
Drop SearchHistory table entirely via Alembic migration. No data migration. `is_saved` and `saved_name` columns added to SearchSession (session-level, not turn-level) to replace the save functionality.

## Implications
- Migration `a1b2c3d4e5f6` drops the table -- irreversible after running in production
- Save/bookmark UX is now session-scoped: users save entire conversations, not individual queries
- If per-turn bookmarking is needed later, it would require a new column on SearchTurn
- Frontend `useSearchHistory` hook and types fully removed; no backward compatibility path

## References
- Migration: `src/linkedout/shared/infra/persistence/migrations/versions/a1b2c3d4e5f6_*.py`
- SearchSession entity: `src/linkedout/search_session/`
- Frontend hooks: `linkedout-fe/src/hooks/useSession.ts`
