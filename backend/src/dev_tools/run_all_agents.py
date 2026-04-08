# SPDX-License-Identifier: Apache-2.0
"""
Run All Agents

Placeholder for running all agents. The rcm planner agents have been removed.
Project management agents can be triggered via the API.

Usage:
    uv run run-all-agents
    uv run python -m dev_tools.run_all_agents
"""

from shared.utilities.logger import get_logger

logger = get_logger(__name__)


def main():
    """Main entry point."""
    logger.info('Agent runner: Use the API to trigger project management agents.')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
