# Sub-Phase 1: Auth Verification & Documentation

**Phase:** 6 — Code Cleanup for OSS
**Plan task:** 6A (Auth & Multi-Tenancy Verification)
**Dependencies:** None
**Blocks:** sp2, sp3, sp4
**Can run in parallel with:** None

## Objective
Confirm the existing single-user auth setup (system tenant/BU/user) works in the OSS repo without any code changes. Produce documentation describing the auth model.

**CRITICAL CONSTRAINT:** DO NOT make any auth/multi-tenancy code changes without consulting SJ. The existing implementation is intentional.

## Context
- Read shared context: `docs/execution/phase-06/_shared_context.md`
- Read plan (6A section): `docs/plan/phase-06-code-cleanup.md`
- Read decision: `docs/decision/env-config-design.md` (for `agent-context.env` with tenant/BU/user IDs)
- Phase 0B (auth strategy) — SJ decided: keep as-is, no changes
- Phase 0D (multi-tenancy simplification) — SJ decided: current state is clean, no changes

## Deliverables

### 1. Read & Understand Auth Flow (NO code changes)

Inspect these files and trace the auth flow:

| File | What to Look For |
|------|-----------------|
| `backend/src/shared/auth/config.py` | `AuthConfig` class, `AUTH_ENABLED` flag, Firebase toggle |
| `backend/src/shared/auth/dependencies/` | FastAPI dependency injection — how requests get authenticated |
| `backend/src/shared/auth/providers/` | Firebase provider — stays but disabled by default |
| `backend/migrations/versions/d1e2f3a4b5c6_enable_rls_policies.py` | RLS migration — how row-level security is configured |
| `backend/src/shared/config/config.py` | Tenant/BU/user ID defaults |
| `backend/src/organization/` | Tenant, BU, enrichment config entities and services |

### 2. Add Firebase Preservation Comment

In `backend/src/shared/auth/providers/` (the main Firebase provider file), add this comment near the top of the class:
```python
# Firebase auth preserved for potential multi-user support — see Phase 0B decision.
```

This is the ONLY code change in this sub-phase.

### 3. Create `docs/architecture/auth-model.md` (NEW)

Document the auth model. Include:

1. **Overview** — LinkedOut OSS uses a single-user model with a system tenant, business unit, and user. Auth is disabled by default.
2. **Key Entities** — system tenant ID, system BU ID, system user ID, where they come from (`agent-context.env`), how they're injected into requests.
3. **RLS** — how row-level security policies use the tenant context. Reference the migration.
4. **Auth Middleware** — how `AUTH_ENABLED` controls the auth pipeline. When disabled, system user context is injected directly.
5. **Firebase Provider** — exists for future multi-user support, disabled by default.
6. **Configuration** — env vars (`AUTH_ENABLED`, `FIREBASE_*`), how to enable/disable.
7. **`organization/` module** — explain that this is NOT template scaffolding. It provides Tenant, BusinessUnit, and EnrichmentConfig entities that are core to the data model.

Keep it concise (~100-150 lines). This is a reference doc, not a tutorial.

### 4. Verification (Manual)

If a database is available:
- Start backend: `cd backend && uv run uvicorn main:app --port 8000`
- Hit `/api/v1/connections?page=1&per_page=10` with system tenant headers
- Verify response returns data (or empty list) without auth errors

If no database:
- Verify backend starts without import errors
- Verify auth-related modules import cleanly

## Verification
1. `docs/architecture/auth-model.md` exists and covers all 7 sections listed above
2. Firebase provider file has the preservation comment
3. No other code files modified (only the one comment + new doc)
4. `cd backend && uv run python -c "from shared.auth.config import AuthConfig; print('Auth imports OK')"` succeeds
5. `cd backend && uv run python -c "from organization.entities import TenantEntity; print('Org imports OK')"` succeeds

## Notes
- This sub-phase is intentionally read-heavy and write-light. The goal is understanding and documentation, not code changes.
- The auth model doc will be a valuable reference for later phases (Phase 12: multi-user upgrade).
- Do NOT remove any auth code. Do NOT refactor any auth code. Do NOT simplify any auth code.
