# SPDX-License-Identifier: Apache-2.0
"""Frontend developer setup script.

Automates the process of getting a FE developer from git clone to a running
backend server with seeded data. Run via: uv run fe-setup
"""

import os
import shutil
import subprocess
import sys
import time


# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


def _print_step(n, total, msg):
    print(f'\n{CYAN}{BOLD}[{n}/{total}]{RESET} {msg}')


def _ok(msg='Done'):
    print(f'  {GREEN}OK{RESET} {msg}')


def _warn(msg):
    print(f'  {YELLOW}WARN{RESET} {msg}')


def _fail(msg):
    print(f'  {RED}FAIL{RESET} {msg}')


def _run(cmd, capture=True, check=True, timeout=120):
    """Run a shell command and return CompletedProcess."""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=capture,
        text=True,
        check=check,
        timeout=timeout,
    )


def _find_project_root():
    """Walk up from this file to find the project root (where pyproject.toml is)."""
    path = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.exists(os.path.join(path, 'pyproject.toml')):
            return path
        path = os.path.dirname(path)
    return None


TOTAL_STEPS = 6


def check_prerequisites():
    """Step 1: Check Python, uv, and PostgreSQL."""
    _print_step(1, TOTAL_STEPS, 'Checking prerequisites...')

    # Python 3.11+
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 11):
        _fail(f'Python 3.11+ required (found {v.major}.{v.minor}.{v.micro})')
        sys.exit(1)
    _ok(f'Python {v.major}.{v.minor}.{v.micro}')

    # uv
    if not shutil.which('uv'):
        _fail('uv not found. Install it:')
        print(f'  curl -LsSf https://astral.sh/uv/install.sh | sh')
        sys.exit(1)
    _ok('uv installed')

    # PostgreSQL
    if shutil.which('pg_isready'):
        result = _run('pg_isready', check=False)
        if result.returncode == 0:
            _ok('PostgreSQL is running')
        else:
            _warn('pg_isready failed - make sure PostgreSQL is running on localhost:5432')
    else:
        _warn('pg_isready not found - cannot verify PostgreSQL. Make sure it is running.')


def install_deps(root):
    """Step 2: Create venv and install dependencies."""
    _print_step(2, TOTAL_STEPS, 'Installing dependencies...')

    venv_path = os.path.join(root, '.venv')
    if not os.path.isdir(venv_path):
        print('  Creating virtual environment...')
        _run(f'cd "{root}" && uv venv')
        _ok('Virtual environment created')
    else:
        _ok('Virtual environment already exists')

    print('  Installing packages (this may take a minute)...')
    _run(f'cd "{root}" && uv pip install -r requirements.txt', timeout=300)
    _ok('Dependencies installed')


def setup_env(root):
    """Step 3: Ensure .env exists."""
    _print_step(3, TOTAL_STEPS, 'Checking environment...')

    env_path = os.path.join(root, '.env')
    if os.path.exists(env_path):
        _ok('.env file exists')
    else:
        _warn('.env file not found. You need to create one with your database credentials.')
        print('  Minimum required variables:')
        print(f'    DATABASE_URL=postgresql://user:pass@localhost:5432/dbname')
        print(f'    ENVIRONMENT=dev')
        sys.exit(1)

    print(f'  {YELLOW}TIP{RESET} If you want to run agents with real LLMs, check .env for API keys.')


def reset_and_seed(root):
    """Step 4: Reset database and seed with test data."""
    _print_step(4, TOTAL_STEPS, 'Resetting database and seeding data...')

    print('  Running: uv run reset-db -m reset -s -y')
    print('  (This drops all tables, runs migrations, and seeds test data)')
    result = _run(f'cd "{root}" && uv run reset-db -m reset -s -y', timeout=120, check=False)
    if result.returncode != 0:
        _fail('Database reset failed:')
        if result.stderr:
            for line in result.stderr.strip().split('\n')[-5:]:
                print(f'    {line}')
        sys.exit(1)
    _ok('Database reset and seeded')


def push_prompts(root):
    """Step 5: Push all prompts to Langfuse."""
    _print_step(5, TOTAL_STEPS, 'Pushing prompts to Langfuse...')

    print('  Running: uv run pm push --all')
    result = _run(f'cd "{root}" && uv run pm push --all', timeout=120, check=False)
    if result.returncode != 0:
        _fail('Prompt push failed:')
        if result.stderr:
            for line in result.stderr.strip().split('\n')[-5:]:
                print(f'    {line}')
        sys.exit(1)
    _ok('All prompts pushed to Langfuse')


def verify_server(root):
    """Step 6: Start server briefly and verify health."""
    _print_step(6, TOTAL_STEPS, 'Verifying server can start...')

    # Start server in background
    proc = subprocess.Popen(
        [sys.executable, 'main.py'],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Wait for server to start
        for _ in range(10):
            time.sleep(1)
            try:
                result = _run('curl -s http://localhost:8001/health', check=False, timeout=5)
                if result.returncode == 0 and 'ok' in result.stdout:
                    _ok('Health check passed')
                    break
            except Exception:
                pass
        else:
            _warn('Could not verify health endpoint (server may need more time to start)')
            return

        # Verify seed data
        result = _run('curl -s http://localhost:8001/tenants', check=False, timeout=5)
        if result.returncode == 0 and 'tenant-test-001' in result.stdout:
            _ok('Seed data verified (tenant-test-001 found)')
        else:
            _warn('Could not verify seed data via /tenants')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def print_summary():
    """Print success message and next steps."""
    print(f'\n{GREEN}{BOLD}{"=" * 50}{RESET}')
    print(f'{GREEN}{BOLD}  Setup complete!{RESET}')
    print(f'{GREEN}{BOLD}{"=" * 50}{RESET}\n')

    print(f'{BOLD}Next steps:{RESET}')
    print(f'  1. Start the server:  {CYAN}python main.py{RESET}')
    print(f'  2. Swagger docs:      {CYAN}http://localhost:8001/docs{RESET}')
    print(f'  3. API reference:     {CYAN}docs/frontend/FE_README.html{RESET} (open in browser)')
    print()
    print(f'{BOLD}Useful commands:{RESET}')
    print(f'  linkedout status               Show system status')
    print(f'  linkedout reset-db --yes       Reset database')
    print(f'  linkedout start-backend        Start API server')
    print()


def main():
    """Entry point for fe-setup CLI command."""
    print(f'\n{BOLD}Reference Code V2 - Frontend Developer Setup{RESET}')
    print('=' * 44)

    root = _find_project_root()
    if not root:
        _fail('Could not find project root (no pyproject.toml found)')
        sys.exit(1)

    check_prerequisites()
    install_deps(root)
    setup_env(root)
    reset_and_seed(root)
    push_prompts(root)
    verify_server(root)
    print_summary()


if __name__ == '__main__':
    main()
