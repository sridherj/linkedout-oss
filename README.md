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

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

**[linkedout-landing.vercel.app](https://linkedout-landing.vercel.app/)**

Query your LinkedIn network in plain English. Local-first, AI-native, your data stays on your machine.

> "Who do I know at Series B AI startups in SF?"
>
> "Compare my top 3 connections in data science for a founding engineer role"
>
> "Draft a warm intro to someone at Anthropic"

LinkedOut works as a skill inside **Claude Code**, **Codex**, or **Copilot**. You ask questions, the skill queries your local PostgreSQL database.

## Setup

### 1. Clone and install prerequisites

```bash
git clone https://github.com/sridherj/linkedout-oss.git
cd linkedout-oss
./setup            # checks Python 3.12+, PostgreSQL 18+, pgvector, installs skills
```

### 2. Run the setup wizard

Open Claude Code (or Codex/Copilot) in the repo and say:

> "set up LinkedOut"

This triggers `/linkedout-setup`, which walks you through everything: database creation, LinkedIn data import, seed data, embeddings, and affinity scoring.

**Want to try it first?** Accept the demo offer during setup to load 2,000 sample profiles with pre-computed everything. No API keys needed, takes ~2 minutes. You can switch to your real data anytime.

### 3. API keys

Setup will ask for two optional API keys. Here's what each one does and why:

**OpenAI API key** — for vector embeddings (semantic search)

LinkedOut converts every profile into a vector embedding so you can search by meaning, not just keywords. "ML engineers with startup experience" finds people even if their title says "Data Scientist at a Series A company."

- With OpenAI: faster, higher quality embeddings. ~$0.01 per 1,000 profiles.
- Without: uses free local model ([nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)), ~275 MB download, slower but zero cost.

Get a key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

**Apify API key** — for profile enrichment (full career details)

Your LinkedIn CSV export only includes name, URL, company, and title. Apify fetches the full profile: complete work history, education, skills, certifications. This is what powers affinity scoring ("career overlap with you") and deep queries ("who has both ML and product experience?").

- Cost: ~$4 per 1,000 profiles. Apify gives [$5 free credit/month](https://apify.com/pricing) — enough for ~1,250 profiles.
- Without: LinkedOut works, but with stub profiles (name + current company only). Search and affinity will be shallow.

Get a key at [console.apify.com/account/integrations](https://console.apify.com/account/integrations).

### Where keys are stored

Setup writes your keys to `~/linkedout-data/config/secrets.yaml` (chmod 600, never committed). You can also set them as environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export APIFY_API_TOKEN="apify_api_..."
```

## What You Get

- **Natural language network queries** — ask anything about your connections
- **Affinity scoring** — rank connections by relationship strength (career overlap, shared education, interaction signals)
- **Company intelligence** — pre-curated seed data on 47K+ companies with funding history
- **LinkedIn CSV import** — bring in your exported connection data
- **Google/iCloud contacts import** — merge your address book with LinkedIn connections
- **Chrome extension** (experimental) — crawl LinkedIn profiles as you browse for richer data. Not thoroughly tested yet — expect rough edges.

## Guides

- [Getting Started](docs/getting-started.md) — prerequisites, demo mode, full setup walkthrough
- [Querying Your Network](docs/querying.md) — example queries, affinity scores, tips
- [Chrome Extension](docs/extension.md) — optional LinkedIn profile crawling
- [Configuration Reference](docs/configuration.md) — all settings, env vars, config files
- [Upgrading](docs/upgrading.md) — how to update to newer versions
- [Troubleshooting](docs/troubleshooting.md) — common issues and solutions

## Architecture

```
You --> Claude Code / Codex / Copilot
          \--> /linkedout skill
                 |--> psql queries (structured lookups)
                 \--> linkedout CLI (import, embed, affinity)
                        \--> PostgreSQL (local)

[Optional] Chrome Extension --> Backend API (localhost:8001) --> same PostgreSQL
```

## CLI Reference

All commands live under the `linkedout` namespace. Run `linkedout --help` for the full list, or `linkedout <command> --help` for any specific command.

| Command | What it does |
|---------|-------------|
| `import-connections` | Import LinkedIn CSV export |
| `import-contacts` | Import Google/iCloud contacts |
| `compute-affinity` | Calculate relationship strength scores |
| `embed` | Generate vector embeddings for search |
| `status` | Quick health check |
| `diagnostics` | Full system diagnostic |

## Project Structure

```
linkedout-oss/
|-- backend/        Python/FastAPI backend + CLI
|-- extension/      Chrome extension (WXT/TypeScript)
|-- skills/         Cross-platform skill definitions
|-- seed-data/      Seed data scripts
\-- docs/           Documentation and specs
```

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0 — see [LICENSE](LICENSE).
