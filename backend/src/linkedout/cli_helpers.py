# SPDX-License-Identifier: Apache-2.0
"""Shared CLI utilities for the ``linkedout`` command namespace.

Provides:
- ``cli_logged`` decorator for correlation ID tracking and entry/exit logging
- ``dry_run_option`` shared Click option for write commands
- Category-grouped help text formatter
"""
import functools
import time

import click

from shared.utilities.correlation import generate_correlation_id, set_correlation_id
from shared.utilities.logger import get_logger


def cli_logged(command_name: str):
    """Decorator for CLI commands that adds correlation ID and entry/exit logging."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cid = generate_correlation_id(f"cli_{command_name}")
            set_correlation_id(cid)
            log = get_logger(__name__, component="cli", operation=command_name)
            log.info(f"Starting {command_name}")
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start) * 1000
                log.info(f"Completed {command_name} in {duration_ms:.0f}ms")
                return result
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                log.error(
                    f"Failed {command_name} after {duration_ms:.0f}ms: "
                    f"{type(e).__name__}: {e}"
                )
                raise
        return wrapper
    return decorator


dry_run_option = click.option(
    '--dry-run', is_flag=True, help='Preview what would happen without making changes'
)


# ---------------------------------------------------------------------------
# Category-grouped help formatter
# ---------------------------------------------------------------------------

LINKEDOUT_HELP_TEXT = """\
 _     _       _            _
| |   (_)_ __ | | _____  __| |
| |   | | '_ \\| |/ / _ \\/ _` |
| |___| | | | |   <  __/ (_| |
|_____|_|_| |_|_|\\_\\___|\\__,_|
                            \\
                             \u2588\u2580\u2580\u2588 \u2588  \u2588 \u2580\u2588\u2580
                             \u2588  \u2588 \u2588  \u2588  \u2588
                             \u2588\u2584\u2584\u2588 \u2580\u2584\u2584\u2580  \u2588

AI-native professional network intelligence

Commands:
  Import:       import-connections, import-contacts, import-seed
  Seed Data:    download-seed
  Intelligence: compute-affinity, embed
  System:       status, diagnostics, version, config, report-issue
  Server:       start-backend
  Database:     reset-db

Run 'linkedout <command> --help' for details on any command.
"""


class CategoryHelpGroup(click.Group):
    """Click group that displays category-grouped help text."""

    def format_help(self, ctx, formatter):
        formatter.write(LINKEDOUT_HELP_TEXT)
