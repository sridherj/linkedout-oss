# Plan: Post-Demo Sandbox Fixes

## Context

After testing the LinkedOut first-time setup flow in a Docker sandbox, three issues were identified that need fixing. These were discussed and decided interactively with the user.

## Changes

### 1. Uncomment `sentence-transformers` in requirements.txt

**File:** `backend/requirements.txt:33-36`

Uncomment `sentence-transformers>=3.0.0` and `onnxruntime>=1.18.0`. Remove the "Optional" / "Install if using" comments — these are now standard dependencies.

**Why:** Demo mode uses the local nomic embedding provider which requires `sentence-transformers`. Without it, D2 (model download) fails with `ModuleNotFoundError` and users can't run search queries in demo mode.

### 2. Install pgvector in `template1` instead of just `linkedout` DB

**File:** `setup` (repo root), lines 419-428

Change the `CREATE EXTENSION IF NOT EXISTS vector` from targeting `-d linkedout` to targeting `-d template1`. This way every new database (including `linkedout_demo`) inherits pgvector automatically.

Current:
```bash
sudo -u postgres psql -d linkedout -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Change to install in **both** `template1` (for future databases) and `linkedout` (for the current database):
```bash
# template1 — all future databases inherit pgvector
sudo -u postgres psql -d template1 -c "CREATE EXTENSION IF NOT EXISTS vector;"
# linkedout — the main DB (may have been created before the template change)
sudo -u postgres psql -d linkedout -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Both are idempotent (`IF NOT EXISTS`). This covers:
- Fresh installs: `template1` gets the extension, `linkedout` gets it explicitly too
- Existing installs re-running `./setup`: `linkedout` already has it, `template1` gets it now
- Future `CREATE DATABASE linkedout_demo`: inherits from `template1` automatically

**Why:** `create_demo_database()` in `db_utils.py` creates `linkedout_demo` and tries to enable pgvector as the `linkedout` user, which fails with "permission denied." Installing in `template1` means all future databases get the extension automatically.

**Also:** Update the `CREATE EXTENSION` fallback in `db_utils.py:create_demo_database()` (lines 69-78). Keep the call (it's idempotent and harmless when the extension is inherited), but change the failure path: instead of a vague `logger.warning`, raise an error with a clear, user-actionable message:
```
pgvector extension not available in demo database.
This requires superuser privileges that the application cannot use directly.
Run: sudo -u postgres psql -d template1 -c "CREATE EXTENSION IF NOT EXISTS vector;"
Then retry.
```
This ensures neither Claude nor the user tries to `sudo` from application code — they see exactly what to run manually and why.

### 3. Add `linkedout embed-query` CLI command

**New file:** `backend/src/linkedout/commands/embed_query.py`

A simple CLI command that takes a text string and outputs its embedding vector to stdout.

```
Usage: linkedout embed-query [OPTIONS] TEXT

Options:
  --provider {openai,local}  Embedding provider (default: from config)
  --format {json,raw}        Output format (default: json)
```

Implementation:
- Use `get_embedding_provider()` from `backend/src/utilities/llm_manager/embedding_factory.py`
- Call `provider.embed_single(text)` — already exists on both LocalEmbeddingProvider and OpenAIEmbeddingProvider
- Do NOT add any `search_query:` prefix — existing document embeddings were generated without prefixes, so query embeddings must match
- Output the vector as JSON array to stdout
- Register in the CLI group (same pattern as other commands — `self.add_command()` in `cli.py` near line 40)

**Why:** Claude Code needs to generate query embeddings for search SQL. The existing `linkedout embed` command is for bulk profile embedding. Without `embed-query`, Claude falls back to raw Python with `model.encode()`.

**Key files to reference:**
- `backend/src/linkedout/commands/embed.py` — existing embed command pattern
- `backend/src/utilities/llm_manager/embedding_factory.py` — `get_embedding_provider()`
- `backend/src/utilities/llm_manager/local_embedding_provider.py` — `embed_single()`, nomic `search_query:` prefix
- `backend/src/utilities/llm_manager/embedding_provider.py` — base class with `embed_single(text: str) -> list[float]`
- CLI registration: check how `embed_command` is added to the CLI group

### 4. Update specs

**File:** `docs/specs/cli_commands.collab.md`
- Add `embed-query` command entry with usage, options, output format
- Bump version

**File:** `docs/specs/onboarding-experience.md`
- Document `--demo`/`--full` flags on `linkedout setup`
- Note that the `/linkedout-setup` skill asks the user conversationally before running setup with the flag
- Note pgvector is now installed in `template1`
- Bump version

### 5. Tests for `embed-query`

**New file:** `backend/tests/unit/cli/test_embed_query_command.py`

Follow the same pattern as `test_embed_command.py`:
- Use `click.testing.CliRunner`
- Mock `get_embedding_provider` to return a provider with `embed_single()` returning a known vector
- Test classes: flag recognition, help text, JSON output format, provider choice, error handling
- Verify the command outputs a valid JSON array of floats to stdout
- Verify `--provider` choice constraint (openai/local only)

## Verification

1. `uv pip install -r requirements.txt` — succeeds, `sentence-transformers` installs
2. `linkedout embed-query "distributed systems engineer"` — outputs JSON vector array
3. In a fresh DB: `createdb test_pgvector && psql -d test_pgvector -c "SELECT 'vector'::regtype;"` — succeeds (inherited from template1)
4. `linkedout setup --demo` in sandbox — D2 model download succeeds, D3 restore succeeds without pgvector permission error
5. `pytest backend/tests/unit/cli/test_embed_query_command.py` — all tests pass
