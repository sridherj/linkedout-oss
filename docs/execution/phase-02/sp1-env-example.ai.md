# SP1: `.env.example` Reference File

**Sub-phase:** 1 of 7
**Tasks covered:** 2A
**Size:** S
**Dependencies:** None (can run first or in parallel with SP2)
**Estimated effort:** 10-15 minutes

---

## Objective

Create `backend/.env.example` with all env vars documented, grouped by category. This is a copy from the approved decision doc — no design decisions needed.

---

## Steps

### 1. Create `backend/.env.example`

Copy the `.env.example` template verbatim from `docs/decision/env-config-design.md` (section "`.env.example` Template"). The content is already approved.

**File:** `backend/.env.example`

**Content source:** `docs/decision/env-config-design.md` — search for "`.env.example` Template"

### 2. Verify `.gitignore` Coverage

Check that the project `.gitignore` (or `backend/.gitignore`) includes:
- `.env` (ignored)
- `.env.*` (ignored — catches `.env.local`, `.env.test`, `.env.prod`)
- `.env.example` is NOT ignored (it should be committed)

If `.gitignore` doesn't exist yet (Phase 1 may not have run), note it but don't create it — Phase 1 owns `.gitignore`.

### 3. Verify Content Completeness

Cross-reference the `.env.example` against the "Complete Environment Variable Table" in `docs/decision/env-config-design.md`. Every env var from that table should appear in `.env.example`.

Groups to verify:
- Core: `DATABASE_URL`, `LINKEDOUT_DATA_DIR`, `LINKEDOUT_DEBUG`, `LINKEDOUT_ENVIRONMENT`
- Server: `LINKEDOUT_BACKEND_HOST`, `LINKEDOUT_BACKEND_PORT`
- Embeddings: `LINKEDOUT_EMBEDDING_PROVIDER`, `LINKEDOUT_EMBEDDING_MODEL`
- LLM: `LINKEDOUT_LLM_PROVIDER`, `LINKEDOUT_LLM_MODEL`
- API Keys: `OPENAI_API_KEY`, `APIFY_API_KEY`
- Logging: `LINKEDOUT_LOG_LEVEL`, `LINKEDOUT_LOG_FORMAT`, `LINKEDOUT_LOG_DIR`, `LINKEDOUT_DEBUG`
- Langfuse: `LANGFUSE_ENABLED`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- Extension Tuning: `LINKEDOUT_RATE_LIMIT_HOURLY`, `LINKEDOUT_RATE_LIMIT_DAILY`, `LINKEDOUT_STALENESS_DAYS`, `LINKEDOUT_ENRICHMENT_CACHE_TTL_DAYS`

---

## Verification

```bash
# File exists
test -f backend/.env.example && echo "PASS" || echo "FAIL"

# Contains DATABASE_URL
grep -q "DATABASE_URL" backend/.env.example && echo "PASS" || echo "FAIL"

# Contains all groups
for group in "Database" "Directories" "Embeddings" "API Keys" "LLM" "Server" "Logging" "Extension" "Observability"; do
  grep -qi "$group" backend/.env.example && echo "PASS: $group" || echo "FAIL: $group"
done

# Header mentions config.yaml preference
grep -q "config.yaml" backend/.env.example && echo "PASS: mentions config.yaml" || echo "FAIL"
```

---

## Acceptance Criteria

- [ ] File exists at `backend/.env.example`
- [ ] Every env var from the decision doc's "Complete Environment Variable Table" is listed
- [ ] Groups match: Core, Server, Embeddings, LLM, API Keys, Logging, Langfuse, Extension Runtime
- [ ] Comments explain each var's purpose and default
- [ ] Header notes that `config.yaml` + `secrets.yaml` is the preferred approach
