# SP02b: Implement `linkedout config show`

## Context

Read `_shared_context.md` first.

The `/linkedout` skill references `linkedout config show` (line ~491) but the command is a stub
that prints "Not yet implemented." This sub-phase replaces the stub with a real implementation.

## Depends On

None (independent of SP01).

## Tasks

### 2b-1. Implement `config show` command

**File:** `backend/src/linkedout/commands/config.py`

Current state: Lines ~23-27, stub that prints "Not yet implemented" and exits.

Replace the stub with:

```python
@config_group.command('show')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def config_show(output_json: bool):
    """Show current config with secrets redacted."""
    import json as json_mod
    from shared.config import get_config

    settings = get_config()

    data = {
        'embedding_provider': settings.embedding.provider,
        'embedding_model': settings.embedding.model,
        'database_url': '***' if settings.database_url else 'not configured',
        'data_dir': str(settings.data_dir),
        'demo_mode': settings.demo_mode,
        'backend_port': settings.backend_port,
        'api_keys': {
            'openai': 'configured' if settings.openai_api_key else 'not configured',
            'apify': 'configured' if settings.apify_api_key else 'not configured',
        },
    }

    if output_json:
        click.echo(json_mod.dumps(data, indent=2))
    else:
        for key, value in data.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    click.echo(f'{key}.{k}: {v}')
            else:
                click.echo(f'{key}: {value}')
```

**Important:** Before implementing, read `backend/src/linkedout/commands/config.py` to understand
the existing stub structure, and read `backend/src/shared/config.py` (or wherever `get_config` lives)
to verify the attribute names (`embedding.provider`, `embedding.model`, `database_url`, `data_dir`,
`demo_mode`, `backend_port`, `openai_api_key`, `apify_api_key`). Adjust attribute names to match
what actually exists.

No CLI registration change needed — `config_group` is already registered and `show` subcommand
exists (just stubbed).

## Tests

### New file: `backend/tests/unit/linkedout/commands/test_config.py`
- `test_config_show_text_output` — invoke via Click test runner, verify key=value lines
- `test_config_show_json_output` — invoke with `--json`, verify valid JSON with expected keys
- `test_config_show_redacts_database_url` — verify `***` not actual URL
- `test_config_show_api_key_status` — verify "configured"/"not configured" not actual keys

## Verification

```bash
# Text output
linkedout config show

# JSON output
linkedout config show --json

# Redaction check
linkedout config show --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['database_url'] == '***', 'URL not redacted!'; print('OK: URL redacted')"

# Tests
cd backend && python -m pytest tests/unit/linkedout/commands/test_config.py -v
```
