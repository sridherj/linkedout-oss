# SPDX-License-Identifier: Apache-2.0
"""``linkedout embed-query`` — generate a single embedding vector for a query string.

Takes a text string and outputs its embedding vector to stdout as JSON.
Useful for generating query embeddings for similarity search SQL.
"""
import json

import click

from linkedout.cli_helpers import cli_logged
from utilities.llm_manager.embedding_factory import get_embedding_provider


@click.command("embed-query")
@click.argument("text")
@click.option(
    "--provider",
    "provider_name",
    type=click.Choice(["openai", "local"]),
    default=None,
    help="Embedding provider (default: from config)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "raw"]),
    default="json",
    help="Output format (default: json)",
)
@cli_logged("embed-query")
def embed_query_command(text: str, provider_name: str | None, output_format: str):
    """Generate an embedding vector for a query string."""
    provider = get_embedding_provider(provider=provider_name)
    vector = provider.embed_single(text)

    if output_format == "raw":
        click.echo(" ".join(str(v) for v in vector))
    else:
        click.echo(json.dumps(vector))
