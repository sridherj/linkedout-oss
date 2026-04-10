# SP02a: Wire Up Query Logging

## Context

Read `_shared_context.md` first for skill template conventions and CLI patterns.

`/linkedout-report` and `/linkedout-history` are dead skills without query data. The logging
module exists and is well-built (`backend/src/linkedout/query_history/query_logger.py`, 125 lines,
thread-safe with fcntl). It just needs to be called. Since the `/linkedout` skill uses raw `psql`,
there's no middleware hook — the skill itself must log via a clean CLI command.

## Depends On

None (independent of SP01).

## Tasks

### 2a-1. Add `linkedout log-query` CLI command

**New file:** `backend/src/linkedout/commands/query_log.py`

```python
@click.command('log-query')
@click.argument('query_text')
@click.option('--type', 'query_type', default='general',
              type=click.Choice(['company_lookup', 'person_search', 'semantic_search',
                                 'network_stats', 'general']))
@click.option('--results', 'result_count', default=0, type=int)
def log_query_command(query_text: str, query_type: str, result_count: int):
    """Log a query to history (called by skills after each query)."""
    from linkedout.query_history import log_query
    log_query(query_text=query_text, query_type=query_type, result_count=result_count)
```

**Important:** Check how `log_query()` is imported and what parameters it expects. Read
`backend/src/linkedout/query_history/query_logger.py` before implementing.

Register the command in the CLI group alongside other commands. Find where other commands are
registered (likely in `backend/src/linkedout/cli.py` or similar) and add `log_query_command`.

### 2a-2. Add query logging section to `/linkedout` skill template

**File:** `skills/linkedout/SKILL.md.tmpl`

Add a new section after "Output Formatting" (or wherever the post-query instructions are):

```markdown
## Query Logging

After executing any query and formatting results, log it for history and reporting:

\```bash
linkedout log-query "{{THE_USER_QUERY}}" --type {{QUERY_TYPE}} --results {{RESULT_COUNT}}
\```

Query types: company_lookup, person_search, semantic_search, network_stats, general.
If the command fails (not installed), skip silently — never let logging interrupt the user's query.
```

**Note:** Use the template variable syntax that matches existing templates. Read
`skills/linkedout/SKILL.md.tmpl` to understand the variable style before editing.

## Tests

### New file: `backend/tests/unit/linkedout/commands/test_query_log.py`
- `test_log_query_command_creates_jsonl` — invoke via Click test runner, verify JSONL file created
- `test_log_query_command_default_type` — omit --type, verify defaults to 'general'

## Verification

```bash
# CLI command works
linkedout log-query "who do I know at Stripe?" --type company_lookup --results 5

# JSONL file created
ls ~/linkedout-data/queries/

# Tests pass
cd backend && python -m pytest tests/unit/linkedout/commands/test_query_log.py -v
```
