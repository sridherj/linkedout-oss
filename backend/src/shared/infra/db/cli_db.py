# SPDX-License-Identifier: Apache-2.0
"""CLI database helper — creates a DbSessionManager for CLI entry points."""
from sqlalchemy import create_engine

from shared.config import get_config
from shared.infra.db.db_session_manager import DbSessionManager


def cli_db_manager() -> DbSessionManager:
    """Create a DbSessionManager for CLI commands and scripts.

    Each CLI entry point calls this to get its own manager instance.
    """
    settings = get_config()
    engine = create_engine(settings.database_url, echo=settings.db_echo_log)
    return DbSessionManager(engine)
