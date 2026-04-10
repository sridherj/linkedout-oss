# Sub-Phase 4: Configuration Collection (API Keys + User Profile)

**Phase:** 9 — AI-Native Setup Flow
**Plan tasks:** 9F (API Key Collection), 9G (User Profile Setup)
**Dependencies:** sp3 (database + python env must be set up)
**Blocks:** sp5
**Can run in parallel with:** —

## Objective
Build the modules that collect user configuration: API key selection/validation and user profile setup. These are grouped because they're both "ask the user for input and store it" steps that run after the system is set up but before data import begins.

## Context
- Read shared context: `docs/execution/phase-09/_shared_context.md`
- Read plan (9F + 9G sections): `docs/plan/phase-09-setup-flow.md`
- Read UX design doc: `docs/design/setup-flow-ux.md` (use exact prompt wording)
- Read config design: `docs/decision/env-config-design.md`
- Read embedding model decision: `docs/decision/2026-04-07-embedding-model-selection.md`

## Deliverables

### 1. `backend/src/linkedout/setup/api_keys.py` (NEW)

API key collection and validation logic.

**Embedding provider choice:**
- Present two options with clear cost/speed tradeoffs:
  - **OpenAI** (recommended for speed): Batch API, ~$0.02 per 1K profiles, ~minutes for 4K profiles. Requires `OPENAI_API_KEY`.
  - **Local nomic** (free, slower): nomic-embed-text-v1.5, ~275MB model download, ~N hours for 4K profiles on CPU. No API key needed.
- Write choice to `~/linkedout-data/config/config.yaml` as `embedding_provider: openai|local`

**OpenAI API key (if openai chosen):**
- Prompt for key
- Validate: make a test embedding call with a short string using Phase 5 `OpenAIEmbeddingProvider`
- On success: write to `~/linkedout-data/config/secrets.yaml`
- On failure: show error, offer retry or switch to local

**Apify API key (optional):**
- Explain: only needed for Chrome extension LinkedIn crawling
- Explain cost: $5 per 1000 profiles, first 5000 free on Apify
- If provided: write to `~/linkedout-data/config/secrets.yaml`
- If skipped: note that extension enrichment won't work without it

**Secrets file permissions:**
- `chmod 600 ~/linkedout-data/config/secrets.yaml`
- Warn if file has open permissions

**Key functions:**
- `prompt_embedding_provider() -> str` — returns "openai" or "local"
- `collect_openai_key() -> str | None` — prompt, validate, return key or None
- `validate_openai_key(key: str) -> bool` — test embedding call
- `collect_apify_key() -> str | None` — prompt, return key or None
- `write_secrets_yaml(secrets: dict, data_dir: Path)`
- `update_config_yaml(updates: dict, data_dir: Path)`
- `collect_api_keys(data_dir: Path) -> OperationReport` — full orchestration

**Idempotency:**
- Detect existing keys and offer to keep or replace
- Detect existing embedding provider choice and offer to change

**Security:**
- API keys NEVER logged (not even at DEBUG level)
- `secrets.yaml` always `chmod 600`
- Use `getpass`-style input for API keys (no echo)

### 2. `backend/src/linkedout/setup/user_profile.py` (NEW)

User profile setup — LinkedIn URL → profile record → affinity anchor.

**Implementation:**

1. **Accept LinkedIn URL:**
   - Prompt for LinkedIn profile URL (e.g., `https://linkedin.com/in/username`)
   - Validate URL format: must match `https://(www\.)?linkedin\.com/in/[\w-]+/?`
   - Extract LinkedIn public ID from URL

2. **Create/update user's profile in DB:**
   - Create a `crawled_profile` record for the user
   - Mark as the owner profile (used for affinity calculation base)
   - Store LinkedIn URL and public ID

3. **Explain affinity scoring:**
   - Brief explanation per UX design doc wording
   - Explain user's profile is the anchor for all affinity calculations

4. **Enrichment note:**
   - If Apify key configured: mention option to enrich via Apify later
   - If no Apify key: explain manual data entry or CSV import provides base data

**Key functions:**
- `prompt_linkedin_url() -> str`
- `validate_linkedin_url(url: str) -> str | None` — returns public ID or None
- `create_user_profile(public_id: str, linkedin_url: str, db_url: str) -> int` — returns profile ID
- `setup_user_profile(data_dir: Path, db_url: str) -> OperationReport` — full orchestration

**Idempotency:**
- Detect existing user profile and offer to update or keep

### 3. Unit Tests

**`backend/tests/linkedout/setup/test_api_keys.py`** (NEW)
- `prompt_embedding_provider()` returns "openai" or "local" (mock input)
- `validate_openai_key()` returns True for valid key format (mock API call)
- `validate_openai_key()` returns False for invalid key (mock API error)
- `write_secrets_yaml()` creates file with correct permissions (0o600)
- `write_secrets_yaml()` never contains API keys in any log output (capture logs)
- Existing keys detected on re-run (mock file read)

**`backend/tests/linkedout/setup/test_user_profile.py`** (NEW)
- `validate_linkedin_url("https://linkedin.com/in/johndoe")` returns `"johndoe"`
- `validate_linkedin_url("https://www.linkedin.com/in/john-doe/")` returns `"john-doe"`
- `validate_linkedin_url("not-a-url")` returns None
- `validate_linkedin_url("https://linkedin.com/company/acme")` returns None (not a profile URL)
- `create_user_profile()` creates a record in the database (mock DB)

## Verification
1. `python -c "from linkedout.setup.api_keys import collect_api_keys"` imports without error
2. `python -c "from linkedout.setup.user_profile import validate_linkedin_url; print(validate_linkedin_url('https://linkedin.com/in/test'))"` prints `test`
3. `pytest backend/tests/linkedout/setup/test_api_keys.py -v` passes
4. `pytest backend/tests/linkedout/setup/test_user_profile.py -v` passes

## Notes
- Use exact prompt wording from the UX design doc (sp1).
- OpenAI key validation should use Phase 5 `OpenAIEmbeddingProvider` — don't build a separate API client.
- The user profile setup is deliberately simple. Full enrichment happens later (or not at all if no Apify key).
- LinkedIn URL validation should be lenient on trailing slashes and www prefix, strict on path format.
- Never store raw API key values in logs, error messages, or diagnostic files.
