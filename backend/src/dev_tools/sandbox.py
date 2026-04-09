# SPDX-License-Identifier: Apache-2.0
"""Launch a fresh-install Docker sandbox for testing the setup flow.

Builds and runs a Docker container with minimal deps (Python, git, curl,
Claude Code) and the repo already cloned. Claude credentials are baked
into the image at build time — rebuild when they expire.

Usage:
    linkedout-sandbox              # build + run
    linkedout-sandbox --no-build   # skip build, reuse existing image
    linkedout-sandbox --no-claude  # build without Claude credentials
"""
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

import click

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DOCKERFILE = REPO_ROOT / 'Dockerfile.sandbox'
IMAGE_NAME = 'linkedout-sandbox'
CLAUDE_CREDENTIALS = Path.home() / '.claude' / '.credentials.json'


@click.command()
@click.option('--no-build', is_flag=True, help='Skip Docker build, reuse existing image.')
@click.option('--no-claude', is_flag=True, help='Build without Claude Code credentials.')
def sandbox(no_build: bool, no_claude: bool):
    """Launch a fresh-install Docker sandbox."""
    if not DOCKERFILE.exists():
        click.echo(f'Dockerfile not found: {DOCKERFILE}', err=True)
        raise SystemExit(1)

    # Build
    if not no_build:
        # Ensure buildx is available
        bx_check = subprocess.run(
            ['docker', 'buildx', 'version'], capture_output=True, check=False,
        )
        if bx_check.returncode != 0:
            click.echo(
                'docker buildx not found. Install it: sudo apt-get install docker-buildx',
                err=True,
            )
            raise SystemExit(1)

        click.echo(f'Building {IMAGE_NAME}...')

        build_cmd = ['docker', 'buildx', 'build',
                     '-f', str(DOCKERFILE), '-t', IMAGE_NAME, '--load']

        # Bake credentials into the image
        if not no_claude and CLAUDE_CREDENTIALS.exists():
            creds = CLAUDE_CREDENTIALS.read_text().strip()
            build_cmd += ['--build-arg', f'CLAUDE_CREDENTIALS_JSON={creds}']
        elif not no_claude:
            click.echo(
                f'Warning: {CLAUDE_CREDENTIALS} not found — '
                'Claude Code will require login inside the container.',
            )

        # Cache-bust so git clone always pulls fresh code
        build_cmd += ['--build-arg', f'CACHE_BUST={datetime.now().isoformat()}']

        # Build context with just the setup script (keeps context small)
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as ctx:
            setup_script = REPO_ROOT / 'setup'
            if setup_script.exists():
                shutil.copy2(str(setup_script), os.path.join(ctx, 'setup'))
            result = subprocess.run(build_cmd + [ctx], check=False)
        if result.returncode != 0:
            click.echo('Docker build failed.', err=True)
            raise SystemExit(result.returncode)

    # Run — wrap with script to capture the full session log
    log_dir = Path('/tmp/linkedout-oss')
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    logfile = log_dir / f'session-{timestamp}.log'

    docker_cmd = f'docker run -it --rm {IMAGE_NAME}'

    click.echo('Launching sandbox...')
    click.echo(f'Session log: {logfile}')
    click.echo('')

    # macOS and Linux have different script(1) syntax
    if platform.system() == 'Darwin':
        os.execvp('script', ['script', '-a', '-q', str(logfile), 'bash', '-c', docker_cmd])
    else:
        os.execvp('script', ['script', '-a', '-q', str(logfile), '-c', docker_cmd])
