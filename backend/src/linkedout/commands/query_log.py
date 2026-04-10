# SPDX-License-Identifier: Apache-2.0
"""``linkedout log-query`` — record a query to the daily JSONL history file.

Called by skills after each query to enable /linkedout-history and /linkedout-report.
"""
import click

from linkedout.cli_helpers import cli_logged


@click.command('log-query')
@click.argument('query_text')
@click.option('--type', 'query_type', default='general',
              type=click.Choice(['company_lookup', 'person_search', 'semantic_search',
                                 'network_stats', 'general']))
@click.option('--results', 'result_count', default=0, type=int)
@cli_logged("log-query")
def log_query_command(query_text: str, query_type: str, result_count: int):
    """Log a query to history (called by skills after each query)."""
    from linkedout.query_history import log_query

    query_id = log_query(query_text=query_text, query_type=query_type, result_count=result_count)
    click.echo(query_id)
