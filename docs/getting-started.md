# Getting Started

## Prerequisites

Before setting up LinkedOut, make sure you have:

- **Operating system:** macOS or Ubuntu/Debian Linux
- **Python 3.11+** (3.12 recommended)
- **PostgreSQL 16+** with the [pgvector](https://github.com/pgvector/pgvector) extension
- **~1 GB free disk space** (for seed data, embeddings model, and database)
- **An AI coding assistant:** [Claude Code](https://claude.ai/claude-code), [Codex](https://openai.com/index/codex/), or [GitHub Copilot](https://github.com/features/copilot) — LinkedOut's primary interface is an AI skill

Optional:
- **OpenAI API key** — for faster, higher-quality embeddings (~$0.02 per 1,000 connections). Without it, LinkedOut uses the free local `nomic-embed-text-v1.5` model (~275 MB download, slower but no cost).

---

## Clone & Setup

```bash
git clone https://github.com/sridherj/linkedout-oss.git
cd linkedout-oss
```

Then invoke the `/linkedout-setup` skill in your AI assistant. It handles the entire setup:

1. **Checks prerequisites** — verifies Python, PostgreSQL, and pgvector versions
2. **Creates the database** — sets up a `linkedout` PostgreSQL database with pgvector enabled
3. **Installs dependencies** — runs `uv pip install -e .` to install the Python package
4. **Generates config** — creates `~/linkedout-data/config/config.yaml` and `~/linkedout-data/config/secrets.yaml`
5. **Imports your LinkedIn data** — parses your exported CSV file
6. **Downloads seed data** — fetches pre-curated company intelligence (~50 MB)
7. **Imports seed data** — loads companies, funding rounds, role aliases into your database
8. **Generates embeddings** — creates vector embeddings for semantic search
9. **Computes affinity** — calculates relationship strength scores and Dunbar tiers
10. **Runs readiness check** — verifies everything is working

Setup typically takes 5-15 minutes depending on network speed and whether you use local or OpenAI embeddings.

### What "done" looks like

When setup completes, you'll see a readiness report:

```
LinkedOut v0.1.0 | 4,012 profiles | 23,456 companies | embeddings: 98.2% | affinity: computed | extension: not connected
```

---

## Your First Query

Once setup is complete, use the `/linkedout` skill in your AI assistant:

> "Who do I know at Stripe?"

The skill queries your local PostgreSQL database and returns structured results:

```
Found 3 connections at Stripe:

1. Jane Smith — Senior Engineer (affinity: 0.82, inner circle)
   Connected since 2023. Shared 2 years at Acme Corp.

2. Alex Chen — Product Manager (affinity: 0.45, active)
   Stanford CS '18. 3 mutual skills: distributed systems, ML, Python.

3. Pat Johnson — Data Scientist (affinity: 0.31, familiar)
   Connected via Google contacts import.
```

Try other queries:
- "Who do I know at Series B AI startups?"
- "Find people who went to Stanford and work in ML"
- "What companies do my connections work at most?"

See the [Querying Guide](querying.md) for more examples.

---

## What's in Your Data

All LinkedOut data lives in `~/linkedout-data/`. Override this location with the `LINKEDOUT_DATA_DIR` environment variable.

```
~/linkedout-data/
├── config/
│   ├── config.yaml            # Main configuration (database URL, embedding provider, etc.)
│   ├── secrets.yaml           # API keys (chmod 600 — owner-read only)
│   └── agent-context.env      # Auto-generated DB connection info for AI skills
├── logs/                      # Per-component log files (backend, cli, import, etc.)
├── metrics/                   # JSONL daily metrics (append-only)
├── reports/                   # Operation reports from CLI commands (JSON)
├── seed/                      # Downloaded seed data (SQLite files)
├── state/                     # Embedding progress, sync state
├── crawled/                   # LinkedIn profile data from Chrome extension
├── uploads/                   # User-uploaded CSVs, VCFs
└── queries/                   # Query history (YYYY-MM-DD.jsonl)
```

**Clean slate:** To start over, delete `~/linkedout-data/` and re-run `/linkedout-setup`.

---

## Next Steps

- [Querying Your Network](querying.md) — example queries and tips for better results
- [Chrome Extension](extension.md) — optional LinkedIn profile crawling for richer data
- [Configuration Reference](configuration.md) — all settings, env vars, and config files
- [Upgrading](upgrading.md) — how to update to newer versions
- [Troubleshooting](troubleshooting.md) — common issues and solutions
