# SPDX-License-Identifier: Apache-2.0
"""SQL query execution tool for SearchAgent — user-scoped, SELECT-only."""
import re
import time

from shared.utilities.langfuse_guard import observe
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

_MAX_ROWS = 100
_STATEMENT_TIMEOUT_MS = 10000

_AVAILABLE_TABLES = [
    'crawled_profile', 'connection', 'experience', 'education', 'company',
    'company_alias', 'profile_skill',
    'funding_round', 'startup_tracking',
]


def _is_select_only(query: str) -> bool:
    """Check that the query is a SELECT statement (not INSERT, UPDATE, DELETE, DROP, etc.)."""
    stripped = query.strip().rstrip(';').strip()
    # Remove leading CTEs (WITH ... AS (...)) to get to the core statement
    cte_pattern = re.compile(r'^\s*WITH\s+.+?\)\s*', re.IGNORECASE | re.DOTALL)
    core = cte_pattern.sub('', stripped).strip()
    return core.upper().startswith('SELECT')


def _inject_limit(query: str, max_rows: int = _MAX_ROWS) -> str:
    """Add LIMIT clause if not already present."""
    stripped = query.strip().rstrip(';')
    if re.search(r'\bLIMIT\s+\d+', stripped, re.IGNORECASE):
        return stripped
    return f"{stripped}\nLIMIT {max_rows}"


def _get_table_columns(session: Session, table_name: str) -> list[str]:
    """Get column names for a table via information_schema."""
    try:
        result = session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :table_name ORDER BY ordinal_position"
            ),
            {"table_name": table_name},
        )
        return [row[0] for row in result]
    except Exception:
        return []


def _build_error_hint(session: Session, error_msg: str) -> str:
    """Generate helpful hints from SQL errors."""
    hints = []
    error_lower = error_msg.lower()

    # Column not found
    col_match = re.search(r'column "?(\w+)"? (?:does not exist|of relation "?(\w+)"?)', error_lower)
    if col_match:
        table = col_match.group(2) if col_match.group(2) else None
        if table:
            cols = _get_table_columns(session, table)
            if cols:
                hints.append(f"Available columns in '{table}': {', '.join(cols)}")

    # Table not found
    if 'relation' in error_lower and 'does not exist' in error_lower:
        hints.append(f"Available tables: {', '.join(_AVAILABLE_TABLES)}")

    return "; ".join(hints) if hints else ""


@observe(name="sql_execution")
def execute_sql(query: str, session: Session) -> dict:
    """Execute a SQL query against an RLS-scoped session. Returns {columns, rows, row_count}.

    The session must already have app.current_user_id set (via
    ``get_session(app_user_id=...)``). RLS policies enforce tenant
    isolation at the database level — no app_user_id binding needed.

    Safety guardrails:
    - SELECT-only (rejects mutations)
    - Auto-injects LIMIT if missing
    - 10-second statement timeout
    """
    if not _is_select_only(query):
        return {"error": "Only SELECT queries are allowed.", "columns": [], "rows": [], "row_count": 0}

    query = _inject_limit(query)

    t0 = time.perf_counter()
    query_preview = query[:200].replace('\n', ' ')

    try:
        # Use a savepoint so errors don't nuke the transaction-scoped RLS
        # context (app.current_user_id set by get_session).
        nested = session.begin_nested()
        try:
            session.execute(text(f"SET LOCAL statement_timeout = '{_STATEMENT_TIMEOUT_MS}'"))

            result = session.execute(text(query))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]

            nested.commit()
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            logger.info(f"SQL OK in {elapsed_ms}ms ({len(rows)} rows): {query_preview}")
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            error_msg = str(e)
            # Rollback only the savepoint — preserves the outer transaction
            # and its RLS session variable (app.current_user_id).
            nested.rollback()
            hint = _build_error_hint(session, error_msg)
            response = {"error": error_msg, "columns": [], "rows": [], "row_count": 0}
            if hint:
                response["hint"] = hint
            logger.error(f"SQL FAILED in {elapsed_ms}ms: {error_msg[:200]} | query: {query_preview}")
            return response
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        error_msg = str(e)
        session.rollback()
        logger.error(f"SQL FAILED (savepoint) in {elapsed_ms}ms: {error_msg[:200]}")
        return {"error": error_msg, "columns": [], "rows": [], "row_count": 0}
