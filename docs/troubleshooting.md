# Troubleshooting

## Setup Problems

### PostgreSQL won't install or isn't running

**Symptom:** Setup fails with "PostgreSQL not found" or "connection refused"

**Fix (macOS):**
```bash
brew install postgresql@16
brew services start postgresql@16
```

**Fix (Ubuntu/Debian):**
```bash
sudo apt install postgresql-16
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

Verify it's running:
```bash
pg_isready
```

### pgvector extension missing

**Symptom:** `CREATE EXTENSION vector` fails or embeddings don't work

**Fix (macOS):**
```bash
brew install pgvector
```

**Fix (Ubuntu/Debian):**
```bash
sudo apt install postgresql-16-pgvector
```

Then in PostgreSQL:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Python version too old

**Symptom:** Setup fails with syntax errors or missing standard library features

**Fix:** LinkedOut requires Python 3.11+. Check your version:
```bash
python3 --version
```

Install a newer version via your system package manager, [pyenv](https://github.com/pyenv/pyenv), or from [python.org](https://www.python.org/downloads/).

### Permission errors on `~/linkedout-data/`

**Symptom:** "Permission denied" when LinkedOut tries to write config or log files

**Fix:**
```bash
chmod -R u+rw ~/linkedout-data/
```

If the directory was created by a different user (e.g., root during a sudo install), change ownership:
```bash
sudo chown -R $(whoami) ~/linkedout-data/
```

### `secrets.yaml` permission issues

**Symptom:** Warning about secrets file permissions being too open

**Fix:** The secrets file should be readable only by your user:
```bash
chmod 600 ~/linkedout-data/config/secrets.yaml
```

---

## Import Problems

### CSV format not recognized

**Symptom:** "Unrecognized CSV format" or zero profiles imported

**Fix:** LinkedOut expects the CSV format from LinkedIn's data export. To get the right file:

1. Go to LinkedIn Settings > Data Privacy > Get a copy of your data
2. Select "Connections" and request the archive
3. Download and extract — use the `Connections.csv` file

The `--format` flag can force a specific format if auto-detection fails:
```bash
linkedout import-connections ~/Downloads/Connections.csv --format linkedin
```

### Duplicate profiles on re-import

**Not a problem.** Imports are idempotent by design. Re-importing the same CSV updates existing profiles rather than creating duplicates. The import summary shows "skipped" counts for profiles already in the database.

### Missing company data

**Symptom:** Queries about companies return few results

**Fix:** Import seed data to add pre-curated company intelligence:
```bash
linkedout download-seed
linkedout import-seed
```

For even more companies, download the full dataset:
```bash
linkedout download-seed --full
```

---

## Embedding Problems

### nomic model download fails

**Symptom:** "Failed to download model" or timeout during embedding generation

**Fix:**
- Check you have ~275 MB of free disk space for the `nomic-embed-text-v1.5` model
- Check your internet connection
- Retry — transient download failures are common with large model files:
  ```bash
  linkedout embed
  ```
  The command is resumable and picks up where it left off.

### OpenAI key invalid or rate limited

**Symptom:** "Invalid API key" or "Rate limit exceeded" when using OpenAI embeddings

**Fix:**
- Verify your API key is set correctly in `~/linkedout-data/config/secrets.yaml`:
  ```yaml
  openai_api_key: sk-...
  ```
- Or set it as an environment variable:
  ```bash
  export OPENAI_API_KEY=sk-...
  ```
- If rate limited, wait a few minutes and retry. The `linkedout embed` command is resumable.

### Embeddings taking too long

**Symptom:** Local nomic embedding is running but very slow

This is expected — local embedding with `nomic-embed-text-v1.5` is CPU-intensive. For ~4,000 profiles, expect:
- **Local (nomic):** 15-30 minutes depending on CPU
- **OpenAI:** 1-2 minutes (~$0.02 per 1,000 connections)

To switch to OpenAI for faster embeddings:
```yaml
# ~/linkedout-data/config/config.yaml
embedding:
  provider: openai
```

Then re-embed:
```bash
linkedout embed --force
```

---

## Query Problems

### Zero results

**Symptom:** Queries return nothing

**Checklist:**
1. **Data imported?** Run `linkedout status` to check profile count
2. **Embeddings generated?** Check embedding coverage percentage in status output
3. **Affinity computed?** Status shows whether affinity scoring has run

If any of these are missing:
```bash
linkedout import-connections ~/Downloads/Connections.csv   # if no profiles
linkedout enrich                                           # fetch full profiles + generate embeddings
linkedout embed                                            # backfill embeddings if some were missed
linkedout compute-affinity                                 # if affinity not computed
```

### Slow queries

**Symptom:** Queries take several seconds to return

**Fix:**
- Run `linkedout diagnostics` to check for missing HNSW indexes
- Large databases benefit from PostgreSQL tuning (shared_buffers, work_mem)
- Check that `pgvector` indexes exist on the embedding columns

---

## Extension Problems

### Backend not running

**Symptom:** "Backend is unreachable" in the extension side panel

**Fix:**
```bash
linkedout start-backend
```

The backend must be running on `http://localhost:8001` whenever you use the extension.

### Extension not connecting

**Symptom:** Extension loads but can't reach the backend

**Fix:**
- Verify the backend is running: `curl http://localhost:8001/health`
- Check the port — default is 8001. If you changed it, update the extension's options page
- Check CORS settings if you changed the backend host

### Voyager API errors

**Symptom:** "Voyager returned 400" or empty profile data

LinkedIn's internal Voyager API changes without notice. When this happens:
- The extension logs the error in the side panel activity log
- Core LinkedOut functionality (queries, affinity, imports) is unaffected
- [File a GitHub issue](https://github.com/sridherj/linkedout-oss/issues) with the error details — maintainers will update the parser

See [Extension documentation](extension.md#voyager-api-fragility) for more details.

### Side panel not appearing

**Symptom:** Clicking the LinkedOut extension icon doesn't open the side panel

**Fix:**
- Make sure you're on a LinkedIn page (`linkedin.com/in/...`)
- Try reloading the extension: go to `chrome://extensions`, find LinkedOut, click the reload icon
- Check that Developer mode is enabled in `chrome://extensions`
- Reinstall: remove the extension and re-sideload via `/linkedout-extension-setup`

### Extension not loading

**Symptom:** Extension doesn't appear in Chrome

**Fix:**
1. Go to `chrome://extensions`
2. Confirm **Developer mode** is enabled (toggle in top-right)
3. Click **Load unpacked** and select the extension directory
4. Check for manifest errors shown in red on the extension card

---

## Getting Help

### Automated diagnostics

Run a comprehensive health check:
```bash
linkedout diagnostics
```

This generates a detailed report covering your system, config, database, and health checks. The report is saved to `~/linkedout-data/reports/` and can be shared in bug reports.

To auto-fix common issues:
```bash
linkedout diagnostics --repair
```

### File an issue

Use the built-in issue reporter:
```bash
linkedout report-issue
```

This runs diagnostics, redacts private information (names, emails, API keys, LinkedIn URLs), shows you the redacted report for approval, and files a GitHub issue. Requires the `gh` CLI to be authenticated.

Or file manually at [github.com/sridherj/linkedout-oss/issues](https://github.com/sridherj/linkedout-oss/issues). Include:
- The output of `linkedout diagnostics`
- Steps to reproduce the problem
- What you expected to happen vs. what actually happened
