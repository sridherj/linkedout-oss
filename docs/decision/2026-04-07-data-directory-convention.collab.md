# Decision: Use ~/linkedout-data/ as Default Data Directory

**Date:** 2026-04-07
**Status:** Accepted
**Context:** LinkedOut OSS -- choosing where user data lives on disk

## Question
Where should LinkedOut store its local database and user data?

## Key Findings
- XDG Base Directory spec (~/.local/share/linkedout/) is standards-compliant but unfamiliar to many users
- ~/linkedout-data/ is immediately discoverable and self-explanatory
- Power users expect env var overrides for data directory
- Similar tools (Monica HQ, etc.) use either dotfiles or explicit data dirs

## Decision
Default to ~/linkedout-data/ for user-friendliness. Support LINKEDOUT_DATA_DIR environment variable for power users who want custom locations.

## Implications
- Easy for users to find, back up, and delete their data
- Non-standard location (not XDG), but discoverability wins for a CLI/local-first tool
- Must document the env var override in README and --help output
- Migration path needed if we ever change the default

## References
- Web research report: .taskos/exploration/web_research_report.md
