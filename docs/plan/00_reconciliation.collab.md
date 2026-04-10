# Execution Plan Reconciliation — Cross-Phase Analysis

## Plan Summary

| Phase | File | Size | Producer |
|-------|------|------|----------|
| 2 | `phase_2_mvcs_tenantbu.md` | 18KB / 466 lines | Child agent |
| 3 | `phase_3_example_domain.md` | 42KB / 1270 lines | Child agent |
| 4 | `phase_4_auth.md` | 42KB / 1065 lines | Child agent |
| 5 | `phase_5_testing.md` | 39KB / 1156 lines | Child agent |
| 6 | `phase_6_ai_agent.md` | 44KB / 1098 lines | Child agent |
| 7 | `phase_7_ops_crosscutting.md` | 49KB / 873 lines | Child agent (late completion) |

---

## 0. CRITICAL ISSUES (Must Resolve Before Execution)

### BLOCKER 1: AppUser Entities Missing
Phase 4 auth Layer 2 (`get_valid_user`) requires `AppUserEntity`, `AppUserTenantRoleEntity`, `AppUserBuRoleEntity` and their services (`AppUserService`, `AppUserTenantRoleService`, `AppUserBuRoleService`). **No phase creates these.** Phase 4 acknowledges this in "Open Questions" but doesn't resolve it.
- **Action**: Add AppUser MVCS to Phase 3 (under `src/organization/`) or as a Phase 4 pre-step.

### BLOCKER 2: Phase 3 Contradicts Phase 2's backref Design
Phase 2 switches `TenantBuMixin` to `backref` so TenantEntity/BuEntity never need explicit domain relationship declarations. Phase 3 then **re-adds explicit relationships** to TenantEntity/BuEntity (`labels`, `priorities`, `projects`, `tasks` with `back_populates`). This undoes Phase 2's decoupling and will cause SQLAlchemy relationship configuration errors.
- **Action**: Remove all explicit relationship additions from Phase 3's TenantEntity/BuEntity sections. The `backref` in TenantBuMixin handles them automatically.

### BLOCKER 3: CRUDRouterFactory Has Zero Consumers
R3 explicitly requires "at least one entity that uses generic CRUD cleanly." Phase 3 uses manual controllers for ALL entities. `CRUDRouterFactory` — a key piece of the generic CRUD infrastructure — remains untested with zero consumers.
- **Action**: Make Label or Priority use `CRUDRouterFactory` in Phase 3.

### ISSUE 4: Module Name Mismatch
Phase 6 uses `src/project_management/` (24 references) while Phases 3, 5, 7 all use `src/project_mgmt/`.
- **Action**: Standardize to `project_mgmt` (shorter, matches majority).

### ISSUE 5: Phase 3 Incomplete Packhouse Removal
Phase 3 deletes `src/rcm/` but does NOT update all files that import from it: `migrations/env.py`, `db_session_manager.py`, `validate_orm.py`, `verify_seed.py`. These will break after deletion.
- **Action**: Add these files to Phase 3's deletion/cleanup checklist.

### ISSUE 6: Auth Config Duplication
Phase 4 creates a separate `AuthConfig` class in `src/shared/auth/config.py`. Phase 7 re-declares the same fields (`AUTH_ENABLED`, `FIREBASE_ENABLED`, etc.) on `BaseConfig` in `src/shared/config/config.py`.
- **Action**: Pick one location. Recommend adding to `BaseConfig` (Phase 7 approach) since all other config is there.

### ISSUE 7: Dual Agent Registries
Phase 6 creates a programmatic `_agent_registry` dict in `agent_executor_service.py`. Phase 7 creates a separate `AGENT_REGISTRY` in `src/dev_tools/run_agent.py`.
- **Action**: Phase 7 CLI should use Phase 6's registry, not create its own.

### ISSUE 8: Data Inconsistencies Between Plans
- Task status `'open'` in Phase 5 fixtures doesn't exist in Phase 3's `TaskStatus` enum (which defines BACKLOG, TODO, IN_PROGRESS, IN_REVIEW, DONE, CANCELLED)
- AgentRun ID prefix: Phase 5 uses `ar`, Phase 6 uses `arn`
- Router naming: Phase 3 uses plural (`labels_router`), Phase 7 uses singular (`label_router`)
- Phase 5 auth mock uses `Principal(id=...)` but Phase 4 defines `Principal(auth_provider_id=...)`
- **Action**: Align all data values to Phase 3/4 definitions as source of truth.

---

## 1. CROSS-PHASE CONFLICTS (Shared Files)

### `main.py` — touched by 5 phases
| Phase | What it does | Order |
|-------|-------------|-------|
| 2 | No changes (rcm routers stay) | — |
| 3 | Replace rcm router imports with project_mgmt routers | First |
| 4 | Add auth middleware/dependencies to app | Second |
| 6 | Add AgentRun router import | Third |
| 7 | Add logging middleware, setup_logging call, update app metadata | Last |

**Risk**: Low — each phase adds/replaces different code sections. Sequential execution handles this cleanly.

### `src/shared/config/config.py` — touched by 5 phases
| Phase | What it adds |
|-------|-------------|
| 2 | No changes |
| 4 | `AUTH_ENABLED`, `FIREBASE_ENABLED`, `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_PATH`, `SERVICE_ACCOUNT_TOKENS` |
| 5 | References config but no modifications |
| 6 | `LLM_TRACING_ENABLED` |
| 7 | Retry/timeout config fields (`LLM_RETRY_MAX_ATTEMPTS`, `LLM_TIMEOUT_SECONDS`, etc.), env file cleanup |

**Risk**: Medium — Phase 4 creates `AuthConfig` as separate class; Phase 7 adds same fields to `BaseConfig`. See ISSUE 6 above.

### `conftest.py` (root) — touched by 4 phases
| Phase | What it does |
|-------|-------------|
| 2 | No changes (rcm imports stay) |
| 3 | Update entity imports from rcm → project_mgmt (minimal, enough to pass tests) |
| 4 | Add auth fixture (mock/bypass auth for tests) |
| 5 | Full overhaul: replace all rcm entity imports, update SeedDb, update fixtures |

**Risk**: Medium — Phase 3 makes minimal changes, Phase 5 does a full overhaul. Phase 5 should subsume Phase 3's conftest changes. **Recommendation**: Phase 3 should make only the minimum conftest changes needed for its tests to pass. Phase 5 does the proper cleanup.

### `tests/seed_db.py` — touched by 3 phases
| Phase | What it does |
|-------|-------------|
| 2 | No changes (has its own TableName enum independent of base_entity) |
| 3 | Needs minimal updates for project_mgmt entities |
| 5 | Full replacement: new TableName enum, new SeedConfig for project-management domain |

**Risk**: Low — same pattern as conftest.py. Phase 5 subsumes Phase 3's changes.

### `migrations/env.py` — touched by 3 phases
| Phase | What it does |
|-------|-------------|
| 3 | Should replace rcm entity imports with project_mgmt (**currently missing from Phase 3 plan — see ISSUE 5**) |
| 6 | Add AgentRunEntity import |
| 7 | Final verification, generate fresh initial migration |

**Risk**: Medium — Phase 3's plan doesn't mention this file but deletes `src/rcm/`. Will break if not addressed.

### `src/organization/entities/tenant_entity.py` + `bu_entity.py` — touched by 2 phases
| Phase | What it does |
|-------|-------------|
| 2 | Strips ALL domain relationships, switches to `backref` via mixin |
| 3 | Re-adds explicit relationships with `back_populates` (**contradicts Phase 2 — see BLOCKER 2**) |

**Risk**: High — direct contradiction. Phase 3 must NOT re-add explicit relationships.

### `src/common/entities/base_entity.py` (TableName) — touched by 2 phases
| Phase | What it does |
|-------|-------------|
| 2 | Strips rcm entries, keeps only TENANT/BU. Says "domain tables in module-level enums" |
| 3 | Adds project_mgmt entries (LABEL, PRIORITY, PROJECT, TASK) back into base TableName |

**Risk**: Medium — Phase 3 contradicts Phase 2's stated design principle. Either project_mgmt tables go in a module-level enum (consistent with Phase 2) or Phase 2's comment should be removed. Minor but should be explicit.

### `src/dev_tools/cli.py` — touched by 2 phases
| Phase | What it does |
|-------|-------------|
| 6 | Adds agent-related CLI commands |
| 7 | Full CLI restructure into Click groups (db, test, prompt, agent, dev) |

**Risk**: Medium — Phase 7 rewrites the whole CLI. Phase 6's additions would be lost. **Recommendation**: Phase 6 should only add the agent runner module (`run_agent.py`), not CLI commands. Phase 7 wires everything into the new CLI structure.

---

## 2. DEPENDENCY VERIFICATION

| Phase | Assumes | Verified? |
|-------|---------|-----------|
| 3 → 2 | Generalized base classes with TenantBuMixin using `backref` | Yes — Phase 3 uses `TenantBuMixin`, `BaseRepository`, `BaseService`, `CRUDRouterFactory` as generalized in Phase 2 |
| 4 → 3 | Endpoints exist to wire auth into | Yes — Phase 4 adds `Depends()` to routers from Phase 3 |
| 5 → 3 | Domain entities exist for testing | Yes — Phase 5 creates tests for Label, Priority, Project, Task |
| 5 → 4 | Auth dependencies are mockable | Yes — Phase 5 accounts for `AUTH_ENABLED=false` in test env |
| 6 → 3 | Task/Project entities exist for TaskTriageAgent context builder | Yes — Phase 6 references Task and Project entities |
| 6 → 5 | Test infrastructure in place | Yes — Phase 6 uses same test patterns |
| 7 → 6 | All features exist for CLI exposure | Yes — Phase 7 wraps existing functionality |

### Broken Assumptions Found

1. **Phase 4 → Phase 3**: Phase 4 requires `AppUserEntity`, `AppUserTenantRoleEntity`, `AppUserBuRoleEntity` and their services. Phase 3 does not create them. **BLOCKER** — see Section 0.
2. **Phase 5 pre-conditions**: Lists "AgentRun" as available from Phase 3, but Phase 6 creates it. Phase 5 should stub/skip agent tests until Phase 6 completes.
3. **Phase 7 stale assumptions**: Phase 7 assumes rcm imports still exist in `migrations/env.py`, `validate_orm.py`, `verify_seed.py`. Phase 3 deletes `src/rcm/` — if Phase 3 doesn't update these files, they break before Phase 7 runs.

---

## 3. GAPS

### Major Gaps

1. **R2: AppUser entities** — Phase 4 auth requires AppUser entities and role junction tables. No phase creates them. See BLOCKER 1.
2. **R3: CRUDRouterFactory consumer** — R3 requires "at least one entity that uses generic CRUD cleanly." Zero consumers exist. See BLOCKER 3.

### Minor Gaps

1. **R4 acceptance: "A developer can trace the MVCS flow through the example entities"** — No phase explicitly creates developer documentation or a README walkthrough. Phase 3 creates the code, but no guide.
   - **Recommendation**: Add a brief ARCHITECTURE.md or README section in Phase 7.

2. **R1 acceptance: "replacing bu with workspace or app_user should require localized, understandable changes"** — Phase 2 achieves structural isolation but no phase creates a written guide for the replacement procedure.
   - **Recommendation**: Add a short "Switching Tenancy Mode" section to docs in Phase 7.

3. **R9 acceptance: "DB, prompt, test, and agent operations are discoverable and documented"** — Phase 7 creates CLI commands but no `--help` text verification or CLI documentation page.
   - **Recommendation**: Phase 7 should include a verification step that runs all `--help` outputs.

4. **AgentRun mentioned in R4 as L4 entity** — Phase 3's plan lists it at L4 but doesn't implement it. Phase 6 implements it in `src/common/`. Phase 5's pre-conditions list it alongside Phase 3 entities ("Label, Priority, Project, Task, ProjectSummary, AgentRun"). This creates an ordering ambiguity.
   - **Recommendation**: Clarify that AgentRun is Phase 6's responsibility. Phase 5 creates agent test patterns after Phase 6 delivers AgentRun.

---

## 4. INCONSISTENCIES

### CRITICAL: Module Name Mismatch
| Phase | Module Name Used |
|-------|-----------------|
| 3 | `src/project_mgmt/` (27 references) |
| 5 | `src/project_mgmt/` (24 references) |
| 7 | `src/project_mgmt/` (27 references) |
| **6** | **`src/project_management/`** (24 references) |

Phase 6 uses `project_management` while all others use `project_mgmt`. **Must be resolved before execution.** Recommendation: Use `project_mgmt` (shorter, matches majority).

### AgentRun Entity Location
- Phase 6 places AgentRun MVCS in `src/common/` (entities, repositories, services, controllers, schemas)
- Phase 3's high-level domain table lists AgentRun at L4 under example domain
- Phase 5 pre-conditions list AgentRun alongside Phase 3 entities

**Resolution**: Phase 6's placement in `src/common/` is correct — AgentRun is infrastructure, not domain-specific. Phase 5 should adjust its pre-conditions: basic test infra can proceed without AgentRun; agent-specific tests added after Phase 6.

### BaseAgent Location
- Phase 6 places `BaseAgent` in `src/common/services/base_agent.py`
- Phase 6 places `TaskTriageAgent` in `src/project_management/agents/task_triage/`

**Issue**: `BaseAgent` in `common/services/` alongside `BaseService` is a bit odd — it's not a CRUD service. Consider `src/common/agents/base_agent.py` as an alternative. But this is minor — either works.

### CLI Restructure vs Agent CLI Additions
- Phase 6 adds agent CLI commands to existing flat `cli.py`
- Phase 7 restructures CLI into Click groups, potentially losing Phase 6's additions

**Resolution**: Phase 6 should create the agent runner module only (`src/dev_tools/run_agent.py`). Phase 7 wires it into the new CLI structure.

---

## 5. PARALLELIZATION

```
Phase 2 (MUST be first — foundational)
  └──> Phase 3 (MUST follow Phase 2 — builds on generalized bases)
         ├──> Phase 4 (can start immediately after Phase 3)
         ├──> Phase 5-basic (can start repo/service/controller tests without auth)
         └──> Phase 6-infra (LLM client, prompt manager, BaseAgent — no domain dependency)
                │
         Phase 4 done ──> Phase 5-auth-tests (add auth mocking)
         Phase 6 done ──> Phase 5-agent-tests (add agent test patterns)
                          Phase 7 (MUST be last — needs everything)
```

**Maximum parallelism**: After Phase 3, run Phase 4 + Phase 5-basic + Phase 6-infra in parallel. Then Phase 5 completes auth+agent tests. Then Phase 7.

**Minimum sequential path**: 2 → 3 → {4, 5-basic, 6-infra} → 5-complete → 7

---

## 6. RISK ASSESSMENT

### Phase Risk Ranking
| Phase | Risk | Reason |
|-------|------|--------|
| 2 | **Medium** | `backref` vs `back_populates` switch could break SQLAlchemy relationships |
| 3 | **High** | Largest scope (5 entities × full MVCS), most files, rcm removal |
| 4 | **Medium** | Auth wiring touches all controllers; provider seam is new code |
| 5 | **Medium** | Full test infra overhaul; seed data dependencies; parallel test isolation |
| 6 | **Medium-High** | Agent lifecycle generalization from rcm; new BaseAgent pattern |
| 7 | **Low** | Polish/additive; no architectural changes |

### Top 3 Risks

1. **AppUser entity gap blocks Phase 4 auth** (BLOCKER): Phase 4's `get_valid_user` dependency loads user from DB, validates tenant access via `AppUserTenantRoleService`. No phase creates these entities or services. Phase 4 will fail to implement the full auth chain. Mitigation: Add AppUser creation to Phase 3 or Phase 4.

2. **Phase 3 rcm deletion breaks files not in its cleanup list**: Phase 3 deletes `src/rcm/` but `migrations/env.py`, `db_session_manager.py`, `validate_orm.py`, `verify_seed.py` all import from rcm. Phase 3's plan doesn't mention updating these files. `precommit-tests` will fail at end of Phase 3. Mitigation: Add explicit file checklist to Phase 3.

3. **Phase 2↔3 backref contradiction**: Phase 2 switches to `backref` to decouple Tenant/BU from domain entities. Phase 3 re-adds explicit `back_populates` relationships to Tenant/BU. SQLAlchemy will raise configuration errors when both `backref` (from mixin) and `back_populates` (from explicit declaration) create the same reverse attribute. Mitigation: Phase 3 must NOT touch TenantEntity/BuEntity relationship declarations.

---

## 7. REQUIREMENTS COVERAGE MATRIX

| Req | Acceptance Criteria | Phase(s) | Status |
|-----|-------------------|----------|--------|
| **R1** | All tests run in TenantBu mode | 2, 5 | Covered |
| | All scoped entities use TenantBu consistently | 2, 3 | Covered |
| | URL paths consistent with TenantBu | 3 | Covered |
| | Replacing bu→workspace requires localized changes | 2 | Structurally covered; no written guide |
| **R2** | Dependency-based auth works e2e | 4 | Covered |
| | Firebase JWT supported as default | 4 | Covered |
| | API key auth via provider seam | 4 | Covered |
| | Tenant + BU authorization enforced | 4 | **GAP** — requires AppUser entities (BLOCKER 1) |
| | Local auth bypass is explicit/safe | 4 | Covered |
| **R3** | Adding simple CRUD entity is low effort | 2, 3 | Covered (Label/Priority demonstrate) |
| | Useful filtering patterns work | 2 | Covered (FilterSpec already supports all types) |
| | At least one generic CRUD entity using CRUDRouterFactory | 3 | **GAP** — factory has zero consumers (BLOCKER 3) |
| | At least one non-trivial service/controller | 3 | Covered (Task with orchestration) |
| **R4** | Domain coherent, no linkedout naming | 3 | Covered |
| | Developer can trace MVCS flow | 3 | Code covered; no walkthrough doc |
| | Simple CRUD + non-trivial orchestration | 3 | Covered |
| | AgentRun as first-class example | 6 | Covered |
| **R5** | Unit tests without PostgreSQL | 5 | Covered (SQLite) |
| | Integration tests with worker isolation | 5 | Covered |
| | Read/write session semantics enforced | 2 | Covered (already in base) |
| | Alembic migrations supported | 7 | Covered |
| **R6** | All test layers have examples | 5 | Covered |
| | Seeding is declarative and reusable | 5 | Covered |
| | Tests run in parallel without interference | 5 | Covered |
| | Agent tests without live LLM calls | 6 | Covered |
| **R7** | Agent lifecycle works e2e | 6 | Covered |
| | Context builder pattern clear/reusable | 6 | Covered |
| | LLM calls mockable | 6 | Covered |
| | Post-validation and enrichment demonstrated | 6 | Covered |
| **R8** | Prompt source switchable via config | 6 | Covered |
| | Tracing on/off independent of prompt source | 6 | Covered |
| | Repo works without Langfuse | 6 | Covered |
| | Prompt tooling via CLI | 7 | Covered |
| **R9** | Common actions via CLI | 7 | Covered |
| | DB/prompt/test/agent operations discoverable | 7 | Covered |
| **R10** | Retries/timeouts config-driven | 7 | Covered |
| | Structured logging | 7 | Covered |
| | Clean config for local/dev/test/prod | 7 | Covered |
| | Shared utilities in well-defined location | Already in `src/shared/` | Covered |

---

## 8. ESTIMATION

| Phase | Size | Files Create | Files Modify | Files Delete | Rationale |
|-------|------|-------------|-------------|-------------|-----------|
| 2 | **S** | 1 | 4 | 0 | Focused: TableName cleanup + backref switch |
| 3 | **XL** | ~40 | ~5 | ~30 | 5 entities × full MVCS (entity, repo, service, controller, schemas) + rcm removal |
| 4 | **L** | ~12 | ~5 | 0 | Auth stack (dependencies, providers, schemas, config, tests) |
| 5 | **L** | ~15 | ~8 | ~30 | Full test infra overhaul + seed data + integration tests + rcm test removal |
| 6 | **XL** | ~20 | ~8 | ~15 | AgentRun MVCS + BaseAgent + context builder + pipeline + TaskTriageAgent + agent tests + rcm planner removal |
| 7 | **M** | ~10 | ~5 | 0 | CLI restructure + reliability + logging + config + migrations |

**Total estimated**: ~100 files created, ~35 modified, ~75 deleted.

---

## 9. ACTION ITEMS BEFORE EXECUTION

### Blockers (must resolve)
1. **Add AppUser entities** to Phase 3 or Phase 4: `AppUserEntity`, `AppUserTenantRoleEntity`, `AppUserBuRoleEntity` + their MVCS stacks under `src/organization/`
2. **Remove TenantEntity/BuEntity relationship additions from Phase 3**: Rely on Phase 2's `backref` approach instead
3. **Make Label or Priority use `CRUDRouterFactory`** in Phase 3: R3 requires at least one consumer

### Important (should resolve)
4. **Fix Phase 6 module name**: Change all `project_management` → `project_mgmt`
5. **Add rcm-importing files to Phase 3 cleanup**: `migrations/env.py`, `db_session_manager.py`, `validate_orm.py`, `verify_seed.py`
6. **Resolve auth config location**: Pick `BaseConfig` (Phase 7) or `AuthConfig` (Phase 4), not both
7. **Unify agent registries**: Phase 7 CLI should use Phase 6's `_agent_registry`
8. **Align data values**: Fix Phase 5 fixture values to match Phase 3/4 definitions (TaskStatus, AgentRun prefix, Principal fields, router names)

### Nice to have
9. **Clarify AgentRun ownership**: Phase 6 owns it. Update Phase 5 pre-conditions.
10. **Phase 6 CLI**: Don't add CLI commands — just create runner module. Phase 7 does CLI.
11. **Add docs to Phase 7**: ARCHITECTURE.md walkthrough, tenancy swap guide, CLI help verification.
12. **Resolve TableName design**: Either project_mgmt entries go in module-level enum (Phase 2 pattern) or base TableName (Phase 3 approach) — be explicit.

---

## 10. RESOLUTIONS (Decisions Made)

| # | Issue | Decision | Rationale |
|---|-------|----------|-----------|
| B1 | AppUser entities missing | Add `AppUserEntity` + `AppUserTenantRoleEntity` to Phase 3 under `src/organization/`. One role table scoped to tenant. | AppUser always exists regardless of tenancy mode. It's organizational, not domain. |
| B2 | Phase 3 contradicts Phase 2 backref | Phase 3 does NOT touch TenantEntity/BuEntity. Backref from mixin handles reverse relationships. | Whole point of Phase 2 is decoupling. |
| B3 | CRUDRouterFactory zero consumers | Both Label AND Priority use `CRUDRouterFactory`. | Simple CRUD entities should use the factory — that's its purpose. |
| I4 | Module name mismatch | `project_mgmt` everywhere. Fix Phase 6. | Shorter, matches majority of plans. |
| I5 | Incomplete rcm removal | Defer ALL rcm/linkedout deletion to new **Phase 8**. Packhouse stays as reference through Phases 2-7. | Keeps working reference available throughout. |
| I6 | Auth config duplication | Composed config via multiple inheritance. `AuthConfig`, `LLMConfig`, `ReliabilityConfig` → `AppConfig`. | Scales better than flat 32-field class. More instructive for reference repo. |
| I7 | Dual agent registries | Single registry in Phase 6. Phase 7 CLI uses it. | One source of truth. |
| I8 | Data inconsistencies | All downstream phases conform to Phase 3/4 definitions. Router names plural (`labels_router`). | Phase 3/4 are source of truth. Existing codebase uses plural routers. |

### Additional Decisions
- **Skills updated**: `mvcs-compliance` skill updated to use `bu_id` instead of `workspace_id` (TenantBu is default mode).
- **Phase 8 added**: Dedicated rcm/linkedout cleanup phase after all new code is in place.
- **Skill/agent accuracy check**: Added as a step in Phase 7 — verify all skills and agents reference correct conventions, module names, and patterns after the codebase has been rebuilt.

### Updated Phase Sequence
```
Phase 2 (MVCS generalization)
  → Phase 3 (Example domain + AppUser + CRUDRouterFactory consumers)
    → Phase 4 (Auth) + Phase 5-basic (Testing without auth/agent)
      → Phase 5-complete (Auth mocking + agent tests after Phase 4/6)
      → Phase 6 (AI Agent infra)
        → Phase 7 (Ops, CLI, reliability, config, migrations, skill/agent check)
          → Phase 8 (Packhouse/linkedout deletion + final cleanup)
```
