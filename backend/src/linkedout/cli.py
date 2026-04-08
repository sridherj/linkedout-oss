# SPDX-License-Identifier: Apache-2.0
"""LinkedOut CLI — flat command namespace for the ``linkedout`` tool.

Entry point: ``linkedout = "linkedout.cli:cli"`` in pyproject.toml.

Commands are lazily imported to avoid heavy startup costs from SQLAlchemy,
embedding providers, etc.
"""
import click

from linkedout.cli_helpers import CategoryHelpGroup


class _LazyLinkedOutCLI(CategoryHelpGroup):
    """Click group that lazily registers commands to avoid circular imports."""

    _registered = False

    def _lazy_register(self):
        if self._registered:
            return
        self._registered = True

        # --- Data Import ---
        from linkedout.commands.import_connections import import_connections_command
        from linkedout.commands.import_contacts import import_contacts_command
        from linkedout.commands.download_seed import download_seed_command
        from linkedout.commands.import_seed import import_seed_command

        self.add_command(import_connections_command)
        self.add_command(import_contacts_command)
        self.add_command(download_seed_command)
        self.add_command(import_seed_command)

        # --- Processing ---
        from linkedout.commands.compute_affinity import compute_affinity_command
        from linkedout.commands.embed import embed_command

        self.add_command(compute_affinity_command)
        self.add_command(embed_command)

        # --- Server ---
        from linkedout.commands.start_backend import start_backend_command
        from linkedout.commands.stop_backend import stop_backend_command

        self.add_command(start_backend_command)
        self.add_command(stop_backend_command)

        # --- Diagnostics ---
        from linkedout.commands.diagnostics import diagnostics_command
        from linkedout.commands.status import status_command
        from linkedout.commands.config import config_group
        from linkedout.commands.report_issue import report_issue_command

        self.add_command(diagnostics_command)
        self.add_command(status_command)
        self.add_command(config_group)
        self.add_command(report_issue_command)

        # --- Setup ---
        from linkedout.commands.setup import setup_command

        self.add_command(setup_command)

        # --- Upgrade ---
        from linkedout.commands.upgrade import upgrade_command

        self.add_command(upgrade_command)

        # --- Demo ---
        from linkedout.commands.download_demo import download_demo_command
        from linkedout.commands.restore_demo import restore_demo_command
        from linkedout.commands.reset_demo import reset_demo_command
        from linkedout.commands.use_real_db import use_real_db_command
        from linkedout.commands.demo_help import demo_help_command

        self.add_command(download_demo_command)
        self.add_command(restore_demo_command)
        self.add_command(reset_demo_command)
        self.add_command(use_real_db_command)
        self.add_command(demo_help_command)

        # --- Meta ---
        from linkedout.commands.version import version_command
        from linkedout.commands.reset_db import reset_db_command
        from linkedout.commands.migrate import migrate_command

        self.add_command(version_command)
        self.add_command(reset_db_command)
        self.add_command(migrate_command)

    def list_commands(self, ctx):
        self._lazy_register()
        return super().list_commands(ctx)

    def get_command(self, ctx, cmd_name):
        self._lazy_register()
        return super().get_command(ctx, cmd_name)


@click.group(cls=_LazyLinkedOutCLI)
@click.pass_context
def cli(ctx):
    """LinkedOut -- your professional network, locally."""
    ctx.ensure_object(dict)


@cli.result_callback()
@click.pass_context
def _append_demo_nudge(ctx, *args, **kwargs):
    """Append a one-line nudge after every command when demo mode is active."""
    try:
        from linkedout.demo import is_demo_mode

        if is_demo_mode():
            click.echo("\nDemo mode \u00b7 linkedout setup to use your own data")
    except Exception:
        pass
