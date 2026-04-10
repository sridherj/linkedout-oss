# Learnings

---

## 2026-04-09 | New OSS-Only Specs (Demo Mode + Seed Data) | subagent

**Learning:** Demo mode and seed data are two distinct but complementary systems: demo uses pg_dump/pg_restore into a separate database for complete data isolation (including profiles), while seed uses SQLite-to-PostgreSQL upserts for 6 company reference tables only. The demo setup flow (D1-D5) in `demo_offer.py` integrates into the setup orchestrator and also downloads the local embedding model + sets embedding_provider to "local" to avoid requiring OpenAI keys. The seed import uses `IS DISTINCT FROM` for null-safe change detection and `xmax = 0` to distinguish inserts from updates.

**Context:** Writing new specs for OSS-only features that have no internal counterpart. The demo and seed data systems share download patterns (GitHub Releases, manifest + SHA256 verification, tqdm progress) but diverge in restore mechanics (pg_restore vs SQLite upsert).

**Tags:** specs, documentation, oss, demo-mode, seed-data, database-isolation

---

## 2026-04-09 | Adapt Specs to OSS | spec-adaptation

**Learning:** When adapting specs from a private repo to OSS, the key differences are: path prefixes (backend/src/ vs src/), removed modules (Firebase, AppUserBuRole, prompt_manager CLI), and OSS-specific additions (per-component log file routing, correlation ID infrastructure). Always verify every behavior against actual code -- the OSS codebase may have evolved beyond the original spec.

**Context:** Applies when porting specs between LinkedOut private and LinkedOut OSS repos. The logging module in OSS has per-component file routing and correlation ID injection that weren't in the original spec.

**Tags:** specs, documentation, oss-adaptation, logging, database

---

## 2026-04-07 | TaskOS Run State Management | taskos-wrap-up

**Learning:** Status-transition endpoints should be idempotent and self-healing -- a "recheck" on a terminal state with incomplete data should re-process, not silently no-op.

**Context:** When an agent run was marked "completed" without its output.json populated, the recheck endpoint refused to process it (it only acts on non-terminal states). This required manual DB state reset before recheck would work. Applies to any system with async job completion and a reconciliation/recheck mechanism.

**Tags:** orchestration, idempotency, state-machine, taskos, error-recovery

---

## 2026-04-07 | Parent-Child Run Consistency | taskos-wrap-up

**Learning:** In parent-child async workflows, parent output can become stale when children complete after the parent writes its summary. Design for eventual consistency -- parent summaries should be lazily computed or re-derived on read.

**Context:** The parent exploration run wrote output.json containing error messages about a child that was still running. When the child later completed successfully, the parent's output remained stale. Required manual update of parent output.json and re-triggering recheck.

**Tags:** orchestration, eventual-consistency, parent-child, taskos

---

## 2026-04-08 | Demo Seed Requirements Refinement | taskos-refine-requirements

**Learning:** Database-level isolation (separate named database) is dramatically simpler than in-DB markers/cleanup for disposable demo data. Avoids CASCADE deletes, data_source markers, import hooks, and the entire class of "mixed data" bugs. The key insight: both databases can coexist, so transitioning doesn't require destructive DROP of the user's real DB.

**Context:** When designing demo/seed data that users will eventually discard, prefer infrastructure-level isolation (separate DB, separate schema, separate file) over application-level isolation (markers, cleanup triggers). This applies whenever data is explicitly temporary and has no migration path to production data.

**Tags:** architecture, demo-data, database-isolation, requirements

---

## 2026-04-08 | Demo Educational Value via Profile Explanation | taskos-refine-requirements

**Learning:** When a demo produces personalized/relative scores (affinity, recommendations, rankings), users cannot interpret the results unless they understand the reference point. A demo that shows scores without explaining the "you" behind them is opaque -- the user sees numbers but can't reason about why they're high or low.

**Context:** LinkedOut's affinity scores are relative to the user's own profile. The demo system user needs an explicit, visible identity so users understand the scoring. This principle applies to any demo of a personalization system: always make the persona visible and explain how it drives the output.

**Tags:** demo-data, ux, onboarding, requirements, personalization

---

## 2026-04-09 | Spec Adaptation for OSS | subagent

**Learning:** When adapting internal specs for OSS, verify every behavior against actual code -- the OSS fork may have RLS (not in the original "Not Included"), removed entities (AppUserBuRole), or different defaults (AUTH_ENABLED=false). The organization module and full auth stack were preserved in OSS despite being single-user default.

**Context:** Adapting multi_tenancy and authentication specs. RLS was added after the original spec was written. AppUserBuRole was already removed in the internal version. OSS preserves Firebase auth code but defaults to dev bypass.

**Tags:** specs, documentation, oss, multi-tenancy, authentication

---

## 2026-04-09 | MVCS + Indexing Spec Adaptation | subagent

**Learning:** OSS consolidates all migrations into a single `001_baseline.py`, so index inventory references to specific migration files from the internal repo must be replaced with section references within the baseline. The MVCS base stack is nearly identical between internal and OSS -- main differences are path prefixes (`backend/src/` vs `src/`) and additional files like `crud_schema_mixins.py` and `tenant_bu_mixin.py` that exist in OSS but weren't in the original spec.

**Context:** Adapting mvcs_base_stack and database_indexing specs. The MVCS code is functionally identical. The indexing strategy is the same but all indexes live in one file instead of 6+ migration files.

**Tags:** specs, documentation, oss, mvcs, indexing, migrations

---

## 2026-04-09 | Tracing + Funding Spec Adaptation | subagent

**Learning:** OSS tracing has a two-level toggle: global `LANGFUSE_ENABLED` (default False) in settings.py AND per-client `LLMConfig.enable_tracing` (default True). The guard module (`langfuse_guard.py`) handles the global toggle with lazy imports so the `langfuse` package is never loaded when disabled. The funding module has 5 endpoints per entity (not 6 -- no bulk create in the controllers), and uses hand-written controllers because shared entities don't fit CRUDRouterFactory's scoped-route pattern. No integration tests exist for funding.

**Context:** Adapting tracing and linkedout_funding specs. The tracing spec needed significant rewrite to document the guard pattern (OSS-specific). The funding spec was a low-touch adaptation -- paths and minor corrections to endpoint counts.

**Tags:** specs, documentation, oss, tracing, langfuse, funding, shared-entities

---

## 2026-04-09 | LLM Client + CRUD Spec Adaptation | subagent

**Learning:** OSS llm_manager has a dual embedding provider architecture (OpenAI + local nomic) not in the original spec -- the `EmbeddingProvider` ABC, `embedding_factory.py`, and `LocalEmbeddingProvider` are OSS additions. The `EmbeddingClient` uses the direct OpenAI SDK (not LangChain `OpenAIEmbeddings` as the original spec claimed). For CRUD: OSS replaced `SearchHistory` with `SearchSession` + `SearchTurn` (two entities in one module). Newer entities (RoleAlias, SearchSession, SearchTurn, SearchTag) use `CRUDRouterFactory` -- the original spec said "none use CRUDRouterFactory" which is outdated for OSS.

**Context:** Adapting llm_client and linkedout_crud specs. Always verify every behavior claim from the old spec against actual code -- the OSS fork has diverged significantly in embedding architecture and controller patterns.

**Tags:** specs, documentation, oss, llm, embedding, crud, search-session

---

## 2026-04-09 | Enrichment + Dashboard Spec Adaptation | subagent

**Learning:** OSS enrichment pipeline removed Procrastinate task queue -- enrichment runs synchronously with retry (3 attempts, exponential backoff) in the request handler. Key rotation changed from numbered env vars (APIFY_API_KEY_1-9) to comma-separated APIFY_API_KEYS. Post-enrichment has a two-phase design: PostEnrichmentService maps Apify JSON to profile columns, then delegates to ProfileEnrichmentService for structured rows + embedding + search_vector. The dashboard has 7 sections (not 8 as old spec claimed) -- the old spec counted 8 but the OSS code shows enrichment_status, industry_breakdown, seniority_distribution, location_top, top_companies, affinity_tier_distribution, and network_sources.

**Context:** Adapting enrichment_pipeline and dashboard specs. Key architectural difference: synchronous enrichment vs async task queue. Always count actual response fields in code rather than trusting the old spec's claims.

**Tags:** specs, documentation, oss, enrichment, dashboard, apify, task-queue

---

## 2026-04-09 | Data Model Spec Adaptation | subagent

**Learning:** The OSS data model has significant divergences from the internal spec: (1) `search_history` was replaced by `search_session` + `search_turn` + `search_tag` (3 tables instead of 1), (2) single `embedding` column became dual `embedding_openai`/`embedding_nomic` with metadata columns, (3) `connection.emails`/`phones`/`tags` are comma-separated Text not PostgreSQL ARRAY, (4) 8 new tables not in internal spec (search_session, search_turn, search_tag, agent_run, app_user_tenant_role, funding_round, growth_signal, startup_tracking), (5) RLS uses `app.current_user_id` session var with FORCE + write policies + profile-linked EXISTS subquery policies.

**Context:** Adapting the data model spec (largest spec, 25+ entities). The OSS schema is defined across entity files and the 001_baseline.py migration. Always cross-reference both sources -- entity files show SQLAlchemy types/defaults, while the migration shows the actual PostgreSQL DDL including raw SQL for HNSW indexes, trigram indexes, and RLS policies.

**Tags:** specs, documentation, oss, data-model, entities, rls, migrations, embeddings

---

## 2026-04-09 | Intelligence + Search Sessions Spec Adaptation | subagent

**Learning:** OSS intelligence module has key divergences from the internal spec: (1) SQL timeout is 10s not 5s (`_STATEMENT_TIMEOUT_MS = 10000`), (2) SSE streaming sends individual result events not batch, (3) SearchHistory entity fully removed -- replaced by SearchSession + SearchTurn, (4) query_history is JSONL file-based logging not a DB entity, (5) SearchSession has `is_saved`/`saved_name` fields for bookmarking (OSS addition), (6) best_hop_controller shares session infrastructure, (7) pg_trgm fuzzy matching is not implemented in any tool code (was prompt-level guidance only). The `get_network_stats` docstring claims `avg_affinity_score` but the implementation omits it.

**Context:** Adapting linkedout_intelligence and search_sessions specs. The intelligence module is the largest feature module with 14 tools, 9 tool files, and multiple controller endpoints. Always verify concrete values (timeouts, batch sizes, event types) against code constants.

**Tags:** specs, documentation, oss, intelligence, search-sessions, sse, tools

---

## 2026-04-09 | Import Pipeline + Affinity Scoring Spec Adaptation | subagent

**Learning:** OSS has three parallel import paths: (1) API pipeline (`import_pipeline/`) with 4-converter registry, cascading dedup, and ImportJob tracking, (2) CLI `import-connections` with batch URL-based matching (simpler, no ContactSource rows), (3) CLI `import-contacts` with cross-source dedup and email/name matching (destructive re-import). The affinity scorer is V3 (not V2 as in internal spec), uses dual embedding columns (`embedding_openai`/`embedding_nomic`) selected dynamically via `get_embedding_column_name()`, and all weights/thresholds are configurable via `ScoringConfig` in `settings.py` (not hardcoded constants). The `import-seed` command handles SQLite-to-PostgreSQL upserts for 6 reference tables with `IS DISTINCT FROM` null-safe comparison.

**Context:** Adapting import pipeline and affinity scoring specs. The import pipeline has significant OSS additions (seed import, CLI commands) beyond the API-based pipeline in the internal spec. The affinity scorer's embedding handling diverges from the internal spec's single-column assumption.

**Tags:** specs, documentation, oss, import-pipeline, affinity-scoring, embedding, seed-data, cli

---

## 2026-04-09 | Search Conversation Flow Spec Adaptation | subagent

**Learning:** The OSS extension sidepanel does NOT have a general search conversation UI (no SearchPageContent, useStreamingSearch, ConversationThread, FollowUpBar, SearchBar, ChatPanel, ResizeHandle, or session switcher). The old spec describes a standalone React app (linkedout-fe) that was never ported to OSS. What OSS has instead: (1) BestHopPanel component with a 5-phase linear state machine (idle/extracting/analyzing/done/error), (2) service worker SSE client (`streamBestHop()`) that parses SSE and relays as Chrome extension messages, (3) backend SSE endpoints for both best-hop and general search that persist sessions/turns. The backend general search endpoint (`POST /search`) streams individual result events (not batched) and includes conversation_state with facets/chips/actions, but no extension component consumes it.

**Context:** Adapting the search_conversation_flow spec. The original spec was entirely about frontend state management in a React app. The OSS adaptation had to be rewritten almost from scratch to document the Chrome extension message-based architecture. Backend SSE protocol is similar but with individual (not batched) result events.

**Tags:** specs, documentation, oss, search, sse, chrome-extension, best-hop, sidepanel

---

## 2026-04-09 | Chrome Extension Spec Adaptation | subagent

**Learning:** The OSS chrome extension is functionally identical to the internal version with these key differences: (1) WXT framework replaces raw Manifest V3 boilerplate, (2) runtime configuration via options page replaces hardcoded constants (backend URL, rate limits, staleness days, tenant/BU/user IDs all configurable), (3) mutual connection extraction uses Voyager search API (not HTML scraping) because LinkedIn search pages are client-rendered, (4) extraction speed control with 1/2/4/8x multiplier and auto-downshift on 429, (5) enrichment dedup guard via `enrichingIds` Set, (6) `tabs.onUpdated` fallback for SPA navigation detection. The parser extracts 12 entity types from Voyager responses (Profile, Position, Education, Skill, Geo, Industry, Company, Certification, Language, Project, VolunteerExperience, Course, Honor).

**Context:** Adapting the chrome_extension spec. The OSS extension is medium adaptation -- most behaviors match the old spec but with additional features (options page, extraction speed, Voyager-based mutual extraction) and architectural refinements (unified config module, legacy migration).

**Tags:** specs, documentation, oss, chrome-extension, wxt, voyager, sidepanel

---

## 2026-04-09 | CLI Commands Spec (OSS) | subagent

**Learning:** The OSS CLI is a complete rewrite from the internal dev-tools CLI. It uses a flat command namespace with category-grouped help (via custom `CategoryHelpGroup`) instead of nested Click groups. Key architectural patterns: lazy command registration to avoid heavy imports, `cli_logged` decorator for correlation ID tracking, `OperationReport` for consistent post-command reporting, and a demo-mode nudge via `result_callback`. The CLI has 24 commands (23 visible + 1 hidden `migrate`), not organized into Click subgroups except `config` which has `path` and `show` subcommands.

**Context:** Writing the CLI commands spec for OSS. The internal CLI had `db`, `test`, `prompt`, `agent`, `dev` groups -- none of these exist in OSS. The OSS CLI is user-facing (setup, import, demo) rather than developer-facing (seed, validate-orm, precommit-tests).

**Tags:** specs, documentation, oss, cli, commands

---

## 2026-04-09 | Skills System Spec | subagent

**Learning:** The LinkedOut skills system is a compile-time template pipeline, not a runtime framework. Skills are markdown instruction files that AI assistants read and follow -- the "routing" is a static catalog, not code-level dispatch. The build has two independent generators: `bin/generate-skills` (YAML + string processing, no backend deps) and `bin/generate-schema-ref` (requires SQLAlchemy model imports). Templates are authored for Claude Code as baseline; other hosts adapt via path rewrites, tool rewrites, and frontmatter filtering (Codex strips to name+description only via allowlist mode). The `/linkedout-dev` skill is the only static (non-templated) skill.

**Context:** Writing the skills_system spec from scratch for OSS. The architecture is straightforward once you understand it is compile-time generation, not runtime routing. Key insight: skills use CLI commands and psql as building blocks, never accessing the backend API directly.

**Tags:** specs, documentation, oss, skills, template-engine, multi-host

---

## 2026-04-09 | Unit & Integration Test Spec Adaptation | subagent

**Learning:** OSS unit tests have two key differences from the internal spec: (1) ARRAY->JSON SQLite compiler in addition to JSONB->JSON (needed for `connection.sources` column), (2) controller tests use FastAPI `dependency_overrides` injection instead of `unittest.mock.patch` -- the service factory function is overridden directly on the app. The seeding has a two-layer design: legacy `SeedDb` (backward compat) wrapping shared `BaseSeeder`/`EntityFactory` (17 entity types, no project_mgmt). Integration tests include pgvector-specific fixtures that ALTER columns within the same session transaction to avoid deadlock with ACCESS SHARE locks.

**Context:** Adapting unit_tests and integration_tests specs. The test infrastructure is mostly similar but with OSS-specific additions (ARRAY compiler, pgvector fixtures, additional marker types for live_llm/live_services/eval).

**Tags:** specs, documentation, oss, testing, unit-tests, integration-tests, fixtures

---

## 2026-04-10 | Pre-condition Guards Lost During DI Refactor | taskos-wrap-up

**Learning:** When replacing a global accessor (singleton/module-level function) with dependency injection, pre-condition guards that checked config validity *before* the accessor was invoked can silently disappear. The guard was part of the implicit contract, not the accessor's interface, so it doesn't transfer automatically.

**Context:** Applies to any refactor that changes how a dependency is obtained. Example: `health_checks.py` had `if not database_url: return fail` before calling `get_db_manager()`. When refactored to accept an injected manager, the empty-URL guard was dropped because the new code assumed a valid manager would always be provided. The test `test_returns_fail_when_no_database_url` caught this. Principle violated: Design by Contract -- preconditions must be preserved or explicitly moved to the new injection site.

**Tags:** refactoring, dependency-injection, design-by-contract, pre-conditions, regression

---

## 2026-04-10 | Permission Prompts Block Headless Agents | taskos-wrap-up

**Learning:** Interactive permission prompts are the most common failure mode for headless agent dispatch. Agents stall silently waiting for user input that never arrives. Diagnosis requires inspecting the agent's terminal (e.g., tmux capture-pane) rather than relying on status polling alone.

**Context:** Phase 4b of the DI refactor stalled for 45 minutes because the subphase runner hit a permission prompt when editing a file outside the expected scope. The 3-tier polling pattern (status check -> log inspection -> terminal capture) reliably diagnosed this. Fix: either pre-approve permissions or ensure agents only edit files within their declared scope.

**Tags:** orchestration, automation, headless-agents, failure-modes, tmux, taskos

---

## 2026-04-10 | Verify Artifacts Independently of Output Contracts | taskos-wrap-up

**Learning:** An agent's output contract (status file, output.json, completion signal) is a separate concern from the actual work performed. When the contract is missing or incomplete, verify the artifacts (files changed, tests passing, specs updated) directly rather than assuming nothing happened.

**Context:** Phase 5 (spec updates) completed its work correctly but never wrote the expected `.agent-*.output.json` file. If we had trusted only the output contract, we would have re-run the phase unnecessarily. Principle: observe effects, not just signals.

**Tags:** orchestration, observability, contracts, verification, taskos

---
