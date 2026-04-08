# Decision: Follow Agent Skills Standard (SKILL.md) for Distribution

**Date:** 2026-04-07
**Status:** Accepted
**Context:** LinkedOut OSS -- how to distribute AI-native CLI tool/agent skills

## Question
How should LinkedOut be packaged and distributed as an AI-native tool?

## Key Findings
- Agent Skills standard (SKILL.md manifest) has 32+ platform adoption
- gstack pioneered the git-clone + setup script pattern for agent-installable tools
- Users expect `git clone` + single setup command
- SKILL.md provides structured metadata for agent discovery and installation

## Decision
Adopt the Agent Skills standard with SKILL.md manifest. Follow gstack's git-clone + setup script pattern for installation.

## Implications
- Need a SKILL.md in repo root describing capabilities, setup, and usage
- Setup script must be idempotent and handle all dependencies
- Compatible with emerging agent ecosystem for tool discovery
- Lowers friction for AI agents to install and use LinkedOut

## References
- Web research report: .taskos/exploration/web_research_report.md
