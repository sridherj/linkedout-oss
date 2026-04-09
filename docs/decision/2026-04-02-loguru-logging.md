# Decision: Switch from stdlib logging to loguru

**Date:** 2026-04-02
**Status:** Accepted
**Context:** LinkedOut backend observability / debugging infrastructure

## Question
Should we replace Python's stdlib logging with loguru for the LinkedOut backend?

## Key Findings
- stdlib logging was only writing to stdout -- no file output, making production debugging impossible
- The kraftx-aragent codebase already uses loguru, so this aligns the two codebases
- loguru provides rotating file handlers, colorized console output, and module-level log levels with minimal configuration
- stdlib `logging.getLogger()` calls can be intercepted and routed through loguru, so third-party libraries continue to work

## Decision
Adopt loguru with a backwards-compatible wrapper in `src/shared/utilities/logger.py`:
- Console handler: compact, colorized format
- File handler: rotating (`logs/app_run_{RUN_ID}.log`), 500MB rotation, 10-day retention
- Module-level overrides via `LOG_LEVEL_<MODULE>` env vars
- Existing API preserved: `get_logger`, `logger`, `set_level`, `setup_logging`
- Stdlib intercept handler so all `logging.getLogger()` calls route through loguru

## Implications
- All new code should use `from src.shared.utilities.logger import get_logger`
- Per-query and per-iteration timing logs are now available for SQL tool and search agent
- Log files enable post-mortem debugging of agent sessions without needing to reproduce
- Dependency added: `loguru`

## References
- `src/shared/utilities/logger.py`
- kraftx-aragent logging pattern (consistency target)
