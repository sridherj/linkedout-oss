# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] — 2026-04-13

### Fixed
- Enrichment pipeline was sending non-LinkedIn URLs (e.g. `stub://gmail-...` from contact imports) to Apify, wasting ~$15 in failed API calls
- Added `ApifyInvalidUrlError` guard in Apify client as defense-in-depth — raises before any HTTP call if the URL isn't a valid LinkedIn profile
- Fixed both CLI (`linkedout enrich`) and API enrichment trigger to filter by `linkedin.com/` instead of just `IS NOT NULL`

## [0.2.0] — 2026-04-12

### Added
- Update notification banner after every CLI command when a newer version is available
- `linkedout version --check` flag for explicit update checks (supports `--json`)
- `linkedout upgrade --snooze` flag to dismiss update notifications with escalating backoff (24h → 48h → 1 week)
- Version check in `/linkedout` skill preamble — notifies during AI-assisted queries too

### Changed
- `/linkedout-upgrade` skill now delegates to `linkedout upgrade --verbose` instead of manual git/pip steps
- Renamed internal `_append_demo_nudge` to `_post_command_hooks` to reflect dual purpose
- Update checker supports `force`, `skip_snooze`, and `timeout` parameters
- Passive banner uses 3s HTTP timeout (vs 10s for explicit `--check`) for fast failure

### Removed
- `try_auto_upgrade()` — dead code that was never wired into any call path
- `auto_upgrade` config field — removed alongside the auto-upgrade code
- Section 7 (Auto-Upgrade Flow) from UX design doc — too risky for a single-user tool

## [0.1.0] — 2026-04-08

### Highlights
- First public release of LinkedOut OSS
- AI-native professional network intelligence via Claude Code / Codex / Copilot skills
- Local-first: all data stays on your machine in ~/linkedout-data/
- 13 CLI commands under the `linkedout` namespace
- Dual embedding support: OpenAI (fast) or nomic-embed-text-v1.5 (free, local)
- Optional Chrome extension for LinkedIn profile crawling
- Comprehensive diagnostics and readiness reporting

### Features
- `/linkedout-setup` — AI-guided installation and configuration
- `/linkedout` — Natural language network queries
- `/linkedout-upgrade` — One-command updates
- Import from LinkedIn CSV and Google/iCloud contacts
- Affinity scoring with Dunbar tier classification
- Seed data: ~5K companies (core) or ~50-100K companies (full)
- Query history and usage reporting
- Structured operation reports for every command

### Technical
- PostgreSQL with pgvector for semantic search
- Loguru-based logging with per-component files
- Three-layer config: env vars > config.yaml > secrets.yaml
- Apache 2.0 license
- CI: lint + type check + unit tests + integration tests + nightly installation tests
- Chrome extension built with WXT (TypeScript/React)
