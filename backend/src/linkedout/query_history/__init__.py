# SPDX-License-Identifier: Apache-2.0
"""Query history module for logging skill-driven queries and managing sessions."""

from linkedout.query_history.query_logger import log_query
from linkedout.query_history.session_manager import get_or_create_session, start_new_session

__all__ = ['log_query', 'get_or_create_session', 'start_new_session']
