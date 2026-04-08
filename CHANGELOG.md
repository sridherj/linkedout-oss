# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
