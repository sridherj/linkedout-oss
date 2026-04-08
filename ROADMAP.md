# Roadmap

## Current Release (v0.1.0)

LinkedOut v0.1.0 delivers AI-native professional network intelligence via Claude Code, Codex, and Copilot skills.

What's included:

- **13 CLI commands** under the `linkedout` namespace — import, enrichment, affinity scoring, diagnostics, and more
- **Local-first architecture** — all data stored in `~/linkedout-data/`, no cloud dependency
- **Dual embedding support** — OpenAI text-embedding-3-small (fast, paid) or nomic-embed-text-v1.5 (free, local, ~275MB)
- **LinkedIn connections import** — bring in your exported CSV data
- **Google/iCloud contacts import** — merge your address book with LinkedIn connections
- **Pre-curated seed data** — thousands of companies with funding history, ready to download
- **Affinity scoring** — rank connections by relationship strength with Dunbar tier classification
- **Semantic search** — vector embeddings for natural language network queries
- **Optional Chrome extension** — crawl LinkedIn profiles for richer data as you browse
- **Comprehensive diagnostics** — `linkedout diagnostics` and `linkedout status` for system health
- **Cross-platform skill system** — works with Claude Code, Codex, and Copilot via SKILL.md manifest

## Up Next

Prioritized for the next release:

- **Chrome Web Store listing** — distribute the extension through Chrome Web Store instead of manual install
- **`linkedout export`** — export network data to CSV or JSON for use in other tools
- **`linkedout backup`** — backup and restore `~/linkedout-data/` with a single command
- **Cloud-hosted shared database** — optional remote PostgreSQL for teams or multi-device setups
- **`linkedout enrich-profiles`** — local enrichment pipeline to fill in missing profile data

## Future

Longer-term ideas under consideration:

- **Web dashboard** — read-only network visualization and analytics
- **Multi-user / team features** — shared network intelligence across teams
- **Additional AI platform support** — beyond Claude Code, Codex, and Copilot
- **Mobile companion app** — query your network on the go
- **Advanced analytics** — network growth tracking, connection recommendations
- **Plugin system** — extensible architecture for custom data sources and enrichment

## Community Requests

Have an idea? Open an issue with the `feature-request` label:

https://github.com/sridherj/linkedout-oss/issues/new?labels=feature-request&template=feature_request.md

We prioritize features based on community interest. Upvote existing requests or open a new one.
