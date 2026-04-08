# SPDX-License-Identifier: Apache-2.0
"""``linkedout demo-help`` — display the demo user profile and sample queries."""
import click

from linkedout.demo.sample_queries import format_demo_profile, format_sample_queries


@click.command("demo-help")
def demo_help_command():
    """Show the demo user profile and sample queries."""
    click.echo()
    click.echo(format_demo_profile())
    click.echo(format_sample_queries())
    click.echo()
