```
 _     _       _            _
| |   (_)_ __ | | _____  __| |
| |   | | '_ \| |/ / _ \/ _` |
| |___| | | | |   <  __/ (_| |
|_____|_|_| |_|_|\_\___|\__,_|
                            \
                             █▀▀█ █  █ ▀█▀
                             █  █ █  █  █
                             █▄▄█ ▀▄▄▀  █
```

# LinkedOut

[![CI](https://github.com/sridherj/linkedout-oss/actions/workflows/ci.yml/badge.svg)](https://github.com/sridherj/linkedout-oss/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

AI-native professional network intelligence.

## What is LinkedOut?

LinkedOut is a local-first tool for querying your LinkedIn network using natural language. It works as a skill inside Claude Code, Codex, or Copilot — you ask questions about your network in plain English, and the skill queries your local PostgreSQL database to find answers.

Your data stays on your machine. No cloud service, no subscription, no tracking.

## Architecture

```
User
  |-- Claude Code / Codex / Copilot
  |     \-- /linkedout skill
  |           |-- Direct psql queries (structured lookups)
  |           \-- CLI commands (import, enrichment, affinity, etc.)
  |                \-- PostgreSQL (local, ~/linkedout-data/db/)
  |
  \-- [Optional] Chrome Extension
        \-- Backend API (localhost:8001, only when extension active)
              \-- PostgreSQL (same DB)
```

The primary interface is the `/linkedout` skill — natural language in, structured answers out. The CLI provides the deterministic building blocks that skills invoke under the hood.

## Quickstart

```bash
git clone https://github.com/sridherj/linkedout-oss.git
cd linkedout-oss
```

Then invoke the `/linkedout-setup` skill in Claude Code. It handles everything: prerequisites, database creation, LinkedIn data import, seed data, and embedding generation.

**Try with demo data first?** During setup, accept the demo offer to load 2,000 sample profiles with pre-computed affinity scores and embeddings. No LinkedIn export needed — start querying in 2 minutes. See [Getting Started — Quick Demo](docs/getting-started.md#quick-demo-2-minutes) for details.

## What You Get

- **Natural language network queries** — "Who do I know at Series B AI startups in SF?"
- **Affinity scoring and Dunbar tier classification** — rank your connections by relationship strength
- **Company intelligence** — pre-curated seed data on thousands of companies with funding history
- **LinkedIn connections import** — bring in your exported LinkedIn data
- **Google/iCloud contacts import** — merge your address book with LinkedIn connections
- **Optional Chrome extension** — crawl LinkedIn profiles for richer data

## CLI Commands

All commands use the `linkedout` namespace. Flat, verb-first, no subgroups.

| Category | Command | Description |
|----------|---------|-------------|
| **Import** | `import-connections` | Import LinkedIn or Google Contacts CSV |
| | `import-contacts` | Import Google/iCloud address book contacts |
| | `import-seed` | Import downloaded seed data into PostgreSQL |
| **Seed Data** | `download-seed` | Download pre-curated company/profile seed data |
| **Intelligence** | `compute-affinity` | Calculate affinity scores and Dunbar tiers |
| | `embed` | Generate vector embeddings for semantic search |
| **System** | `status` | Quick health check and stats |
| | `diagnostics` | Comprehensive system diagnostic report |
| | `version` | Print version, environment info, ASCII logo |
| | `config` | View current configuration |
| | `report-issue` | File a GitHub issue with redacted diagnostics |
| **Server** | `start-backend` | Start backend API for Chrome extension |
| **Demo** | `download-demo` | Download demo database dump (~375 MB) |
| | `restore-demo` | Restore demo into `linkedout_demo` database |
| | `reset-demo` | Reset demo database to original state |
| | `use-real-db` | Switch from demo mode to real database |
| | `demo-help` | Show demo user profile and sample queries |
| **Database** | `reset-db` | Reset the database (truncate or full recreate) |

Run `linkedout <command> --help` for details on any command.

## Chrome Extension (Optional)

The Chrome extension captures LinkedIn profile data as you browse — when you visit a profile, it reads the data via LinkedIn's Voyager API and saves it to your local database. This gives you richer profile data (full experience, education, skills) than a CSV export alone.

The extension is **optional** — LinkedOut works fully without it for data already in the database (imported CSVs, seed data, contacts).

- [Full extension documentation](docs/extension.md) — architecture, Voyager API fragility notes, rate limits, troubleshooting, configuration
- To install, run the `/linkedout-extension-setup` skill in Claude Code

## Guides

- [Getting Started](docs/getting-started.md) — prerequisites, setup, your first query
- [Querying Your Network](docs/querying.md) — example queries, affinity scores, tips
- [Chrome Extension](docs/extension.md) — optional LinkedIn profile crawling
- [Configuration Reference](docs/configuration.md) — all settings, env vars, config files
- [Upgrading](docs/upgrading.md) — how to update to newer versions
- [Troubleshooting](docs/troubleshooting.md) — common issues and solutions

## Project Structure

```
linkedout-oss/
|-- backend/        Python/FastAPI backend + CLI
|-- extension/      Chrome extension (WXT/TypeScript)
|-- skills/         Cross-platform skill definitions
|-- seed-data/      Seed data download scripts
\-- docs/           Documentation and decision records
```

## Roadmap

See [ROADMAP.md](ROADMAP.md) for what's shipped, what's next, and longer-term plans.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, branch naming, PR process, and testing.

## License

Apache 2.0 -- see [LICENSE](LICENSE) for details.

## Acknowledgements

Built with [FastAPI](https://fastapi.tiangolo.com/), [pgvector](https://github.com/pgvector/pgvector), [loguru](https://github.com/Delgan/loguru), [nomic-embed-text](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5), [WXT](https://wxt.dev/), [Click](https://click.palletsprojects.com/), and [pydantic](https://docs.pydantic.dev/).
