# SPDX-License-Identifier: Apache-2.0
"""Main harness for LinkedOut installation integration test.

Drives the 3-phase test flow (demo, full, verify) inside a Docker sandbox
using the tmux harness and session log reader.

Usage:
    linkedout-integration-test                    # burnish mode, all phases
    linkedout-integration-test --mode regression  # clean clone, pass/fail
    linkedout-integration-test --phase demo       # only Phase I
"""
import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import click
from loguru import logger

from dev_tools.log_reader import SessionLogReader
from dev_tools.tmux_harness import TmuxHarness
from dev_tools.verdict import FullVerdict, evaluate_structural, write_verdict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FIXTURES_DIR = REPO_ROOT / 'tests' / 'e2e' / 'fixtures'
LINKEDIN_CSV = FIXTURES_DIR / 'linkedin-connections-subset.csv'
GMAIL_CONTACTS_DIR = FIXTURES_DIR / 'gmail-contacts'

# Paths inside the container (fixtures are docker-cp'd after launch)
CONTAINER_FIXTURES = '/tmp/test-fixtures'
CONTAINER_LINKEDIN_CSV = f'{CONTAINER_FIXTURES}/linkedin-connections-subset.csv'
CONTAINER_GMAIL_DIR = f'{CONTAINER_FIXTURES}/gmail-contacts'
STATE_FILE = Path('/tmp/linkedout-oss/test-state.json')
ENV_LOCAL = Path.home() / 'workspace' / 'linkedout' / '.env.local'


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TestState:
    """Tracks progress across the 3-phase test flow. Persisted for resume."""

    phase: str = 'not_started'
    phase_i_passed: bool = False
    phase_ii_passed: bool = False
    phase_iii_passed: bool = False
    errors: list[dict] = field(default_factory=list)
    burnish_fixes: list[dict] = field(default_factory=list)
    container_id: str = ''
    mode: str = 'burnish'
    started_at: str = ''

    def save(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> 'TestState':
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            known = set(cls.__dataclass_fields__)
            return cls(**{k: v for k, v in data.items() if k in known})
        return cls()


@dataclass
class PhaseResult:
    """Result of a single test phase."""

    status: str  # 'pass' or 'fail'
    errors: list[str] = field(default_factory=list)
    duration_s: float = 0.0


@dataclass
class TestVerdict:
    """Final verdict after all phases complete."""

    mode: str
    phases: dict[str, dict]
    overall: str  # 'pass' or 'fail'
    burnish_fixes: int = 0
    advisory_score: int = 0
    advisory_notes: str = ''


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_env_keys(path: Path = ENV_LOCAL) -> dict[str, str]:
    """Read key=value pairs from an env file. Skips comments and blanks."""
    env: dict[str, str] = {}
    if not path.exists():
        logger.warning('Env file not found: {}', path)
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, _, value = line.partition('=')
            env[key.strip()] = value.strip().strip('\'"')
    return env


def _launch_sandbox(dev: bool = False) -> str:
    """Launch a detached sandbox container, return container ID."""
    cmd = ['linkedout-sandbox', '--detach']
    if dev:
        cmd.append('--dev')
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600)
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    container_id = lines[-1].strip()
    logger.info('Launched sandbox container: {}', container_id[:12])

    # Copy test fixtures into the container
    if FIXTURES_DIR.exists():
        subprocess.run(
            ['docker', 'cp', str(FIXTURES_DIR), f'{container_id}:{CONTAINER_FIXTURES}'],
            check=False, timeout=30,
        )
        logger.info('Copied test fixtures to {}', CONTAINER_FIXTURES)

    return container_id


def _stop_container(container_id: str) -> None:
    """Stop a container."""
    subprocess.run(
        ['docker', 'stop', container_id], capture_output=True, check=False, timeout=30,
    )
    logger.info('Stopped container: {}', container_id[:12])


def _output_has_positive_count(output: str) -> bool:
    """Check if pane output contains a numeric count > 0."""
    for line in output.splitlines():
        for n in re.findall(r'\b(\d+)\b', line):
            if int(n) > 0:
                return True
    return False


def _parse_query_results(pane_output: str) -> list[dict]:
    """Extract structured results from Claude's pane output.

    Heuristic: looks for pipe-delimited table rows, numbered items, or bullets.
    """
    results: list[dict] = []
    for line in pane_output.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('>') or set(line) <= {'-', '|', '+', ' ', '='}:
            continue
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                results.append({'raw': line, 'fields': parts})
        elif re.match(r'^(\d+[.)]\s|[-*]\s)', line):
            results.append({'raw': line, 'fields': [line]})
    return results


def _assert_query_results(pane_output: str, min_results: int = 1) -> dict:
    """Check structural assertions on query output.

    Returns dict: passed (bool), result_count (int), errors (list[str]).
    """
    results = _parse_query_results(pane_output)
    errors: list[str] = []
    if len(results) < min_results:
        errors.append(f'Expected at least {min_results} results, got {len(results)}')
    return {'passed': len(errors) == 0, 'result_count': len(results), 'errors': errors}


# ---------------------------------------------------------------------------
# Phase I — Demo setup + sample queries
# ---------------------------------------------------------------------------

def _run_phase_i_demo(
    harness: TmuxHarness, log_reader: SessionLogReader, state: TestState,
) -> PhaseResult:
    """Phase I: Run demo setup then execute sample queries."""
    start = time.monotonic()
    errors: list[str] = []
    state.phase = 'demo'
    state.save()

    # 1. Run ./setup --auto (prerequisite script, auto-install missing deps)
    logger.info('Phase I: Running ./setup --auto')
    harness.send_keys('cd /linkedout-oss && ./setup --auto')
    if not harness.wait_for_idle(idle_seconds=15, timeout=600):
        errors.append('./setup timed out after 600s')
        return PhaseResult(status='fail', errors=errors, duration_s=time.monotonic() - start)

    setup_errors = log_reader.detect_errors()
    if setup_errors:
        for e in setup_errors:
            errors.append(f'setup error: {e["line"]}')
        return PhaseResult(status='fail', errors=errors, duration_s=time.monotonic() - start)

    # 2. Start Claude Code
    logger.info('Phase I: Starting Claude Code')
    harness.send_keys('claude --dangerously-skip-permissions')

    # Trust dialog is pre-accepted via .claude.json (hasTrustDialogAccepted).
    # If it still appears (e.g. config mismatch), accept it.
    trust = harness.wait_for_pattern(r'trust this folder|Yes.*trust', timeout=10)
    if trust:
        logger.info('Phase I: Accepting workspace trust dialog')
        harness.send_keys('', enter=True)

    # Wait for the Claude Code prompt — look for the bypass permissions
    # indicator which only appears on the real input line.
    if not harness.wait_for_pattern(r'bypass permissions', timeout=60):
        errors.append('Claude Code prompt not detected within 60s')
        return PhaseResult(status='fail', errors=errors, duration_s=time.monotonic() - start)

    # 3. Send /linkedout-setup and wait for demo/full question
    logger.info('Phase I: Sending /linkedout-setup')
    harness.send_keys('/linkedout-setup')
    if not harness.wait_for_pattern(r'Quick start|quick start|sample data', timeout=300):
        errors.append('Demo/full question not detected within 300s')
        return PhaseResult(status='fail', errors=errors, duration_s=time.monotonic() - start)

    # 4. Select demo path and wait for completion
    logger.info('Phase I: Selecting Quick start')
    if not harness.send_to_claude('Quick start', idle_timeout=900):
        errors.append('Demo setup timed out after 900s')
        return PhaseResult(status='fail', errors=errors, duration_s=time.monotonic() - start)

    # 5. Sample queries with structural assertions
    logger.info('Phase I: Running sample queries')

    harness.send_to_claude('who do I know at Google', idle_timeout=120)
    check = _assert_query_results(harness.capture_pane())
    if not check['passed']:
        errors.extend(f"Query 'Google': {e}" for e in check['errors'])

    harness.send_to_claude('find engineers in SF', idle_timeout=120)
    check = _assert_query_results(harness.capture_pane())
    if not check['passed']:
        errors.extend(f"Query 'engineers SF': {e}" for e in check['errors'])

    duration = time.monotonic() - start
    status = 'pass' if not errors else 'fail'
    state.phase_i_passed = status == 'pass'
    state.save()
    logger.info('Phase I {}: {:.0f}s', status.upper(), duration)
    return PhaseResult(status=status, errors=errors, duration_s=duration)


# ---------------------------------------------------------------------------
# Phase II — Full setup with curated test data
# ---------------------------------------------------------------------------

def _run_phase_ii_full(
    harness: TmuxHarness, log_reader: SessionLogReader, state: TestState,
) -> PhaseResult:
    """Phase II: Transition to full setup, provide inputs, wait for completion."""
    start = time.monotonic()
    errors: list[str] = []
    state.phase = 'full'
    state.save()

    # 1. Trigger full setup (same Claude session, skill detects demo-active)
    logger.info('Phase II: Triggering full setup')
    harness.send_keys('/linkedout-setup')
    if not harness.wait_for_pattern(r'Quick start|Full setup|full setup', timeout=120):
        errors.append('Setup question not detected within 120s')
        return PhaseResult(status='fail', errors=errors, duration_s=time.monotonic() - start)

    harness.send_keys('Full setup')

    # Read API keys from host env file for prompt responses
    env_keys = _read_env_keys()

    # 2. Respond to prompts as they appear
    # API key (OpenAI)
    if harness.wait_for_pattern(r'API key|OPENAI|openai', timeout=300):
        key = env_keys.get('OPENAI_API_KEY', '')
        if key:
            logger.info('Phase II: Providing OpenAI API key')
            harness.send_keys(key)
            harness.wait_for_idle(idle_seconds=10, timeout=60)
        else:
            errors.append('OPENAI_API_KEY not found in env file')

    # Profile URL
    if harness.wait_for_pattern(r'LinkedIn.*profile|profile.*URL', timeout=300):
        logger.info('Phase II: Providing profile URL')
        harness.send_keys('https://www.linkedin.com/in/sridher-jeyachandran/')
        harness.wait_for_idle(idle_seconds=10, timeout=60)

    # LinkedIn CSV
    if harness.wait_for_pattern(r'LinkedIn|connections|CSV|csv', timeout=300):
        logger.info('Phase II: Providing LinkedIn CSV path')
        harness.send_keys(CONTAINER_LINKEDIN_CSV)
        harness.wait_for_idle(idle_seconds=10, timeout=60)

    # Gmail contacts (directory with 3 optional CSVs)
    if harness.wait_for_pattern(r'Gmail|contacts|Google Contacts', timeout=300):
        logger.info('Phase II: Providing Gmail contacts directory')
        harness.send_keys(CONTAINER_GMAIL_DIR)
        harness.wait_for_idle(idle_seconds=10, timeout=60)

    # 3. Wait for enrichment + embedding + affinity to complete
    logger.info('Phase II: Waiting for full setup to complete')
    if not harness.wait_for_idle(idle_seconds=30, timeout=1800):
        errors.append('Full setup timed out after 1800s')
        return PhaseResult(status='fail', errors=errors, duration_s=time.monotonic() - start)

    # 4. Verify readiness
    output = harness.capture_pane()
    if 'PASSED' not in output and 'readiness' not in output.lower():
        harness.send_to_claude('linkedout status', idle_timeout=60)

    setup_errors = [
        e for e in log_reader.detect_errors()
        if e['type'] in ('python_traceback', 'setup_failure')
    ]
    if setup_errors:
        for e in setup_errors:
            errors.append(f'full setup error: {e["line"]}')

    duration = time.monotonic() - start
    status = 'pass' if not errors else 'fail'
    state.phase_ii_passed = status == 'pass'
    state.save()
    logger.info('Phase II {}: {:.0f}s', status.upper(), duration)
    return PhaseResult(status=status, errors=errors, duration_s=duration)


# ---------------------------------------------------------------------------
# Phase III — Verification + enriched queries
# ---------------------------------------------------------------------------

def _run_phase_iii_verify(
    harness: TmuxHarness, log_reader: SessionLogReader, state: TestState,
) -> PhaseResult:
    """Phase III: Verify database state, run enriched queries."""
    start = time.monotonic()
    errors: list[str] = []
    state.phase = 'verify'
    state.save()

    try:
        # 1. Database verification — embeddings
        logger.info('Phase III: Verifying database state')
        harness.send_to_claude(
            'Run this SQL and show the result: '
            'SELECT count(*) FROM crawled_profile WHERE embedding IS NOT NULL',
            idle_timeout=60,
        )
        if not _output_has_positive_count(harness.capture_pane()):
            errors.append('No profiles with embeddings found')

        # Database verification — affinity scores
        harness.send_to_claude(
            'Run this SQL and show the result: SELECT count(*) FROM affinity_score',
            idle_timeout=60,
        )
        if not _output_has_positive_count(harness.capture_pane()):
            errors.append('No affinity scores found')

        # 2. Enriched queries
        logger.info('Phase III: Running enriched queries')

        harness.send_to_claude('who do I know at Anthropic', idle_timeout=120)
        check = _assert_query_results(harness.capture_pane())
        if not check['passed']:
            errors.extend(f"Query 'Anthropic': {e}" for e in check['errors'])

        harness.send_to_claude('find engineering managers in my network', idle_timeout=120)
        check = _assert_query_results(harness.capture_pane())
        if not check['passed']:
            errors.extend(f"Query 'eng managers': {e}" for e in check['errors'])

    except RuntimeError as e:
        logger.error('Phase III: tmux session lost: {}', e)
        errors.append(f'tmux session died: {e}')

    # 3. Check session log for errors during verification
    verify_errors = [
        e for e in log_reader.detect_errors()
        if e['type'] == 'python_traceback'
    ]
    if verify_errors:
        for e in verify_errors:
            errors.append(f'verify error: {e["line"]}')

    # Advisory quality evaluation placeholder (implemented in SP-E).
    # The parent Claude reviews output quality — produces commentary,
    # not a pass/fail gate.

    duration = time.monotonic() - start
    status = 'pass' if not errors else 'fail'
    state.phase_iii_passed = status == 'pass'
    state.save()
    logger.info('Phase III {}: {:.0f}s', status.upper(), duration)
    return PhaseResult(status=status, errors=errors, duration_s=duration)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_integration_test(mode: str = 'burnish', phase: str = 'all') -> TestVerdict:
    """Run the integration test.

    Args:
        mode: 'burnish' (self-healing via volume mount) or 'regression' (clean clone).
        phase: 'all', 'demo', 'full', or 'verify'.

    Returns:
        TestVerdict with pass/fail per phase.
    """
    state = TestState(mode=mode, started_at=datetime.now(timezone.utc).isoformat())
    dev = mode == 'burnish'

    harness = TmuxHarness('linkedout-test')
    log_reader = SessionLogReader()
    results: dict[str, dict] = {}

    try:
        # Launch sandbox
        logger.info('Launching sandbox (mode={}, dev={})', mode, dev)
        container_id = _launch_sandbox(dev=dev)
        state.container_id = container_id
        state.save()

        # Create tmux session attached to container
        harness.create_session(container_id)

        phases_to_run = [phase] if phase != 'all' else ['demo', 'full', 'verify']

        # Phase I
        if 'demo' in phases_to_run:
            try:
                result = _run_phase_i_demo(harness, log_reader, state)
            except RuntimeError as e:
                logger.error('Phase I: session lost: {}', e)
                result = PhaseResult(status='fail', errors=[str(e)])
            results['demo'] = asdict(result)
            if result.status == 'fail' and phase == 'all':
                logger.error('Phase I failed — stopping')

        # Phase II (requires Phase I passed when running all)
        if 'full' in phases_to_run and (phase != 'all' or state.phase_i_passed):
            try:
                result = _run_phase_ii_full(harness, log_reader, state)
            except RuntimeError as e:
                logger.error('Phase II: session lost: {}', e)
                result = PhaseResult(status='fail', errors=[str(e)])
            results['full'] = asdict(result)
            if result.status == 'fail' and phase == 'all':
                logger.error('Phase II failed — stopping')

        # Phase III (requires Phase II passed when running all)
        if 'verify' in phases_to_run and (phase != 'all' or state.phase_ii_passed):
            try:
                result = _run_phase_iii_verify(harness, log_reader, state)
            except RuntimeError as e:
                logger.error('Phase III: session lost: {}', e)
                result = PhaseResult(status='fail', errors=[str(e)])
            results['verify'] = asdict(result)

    finally:
        harness.kill_session()
        if state.container_id:
            _stop_container(state.container_id)

    state.phase = 'complete'
    state.save()

    # Evaluate via verdict.py (structural hard gate + advisory quality)
    log_errors = log_reader.detect_errors()
    phase_verdicts = evaluate_structural(results, log_errors)
    full_verdict = FullVerdict.from_results(
        mode=mode,
        phase_verdicts=phase_verdicts,
        session_log_path=str(harness.log_path or log_reader.latest_log() or ''),
        burnish_fixes=len(state.burnish_fixes),
    )
    verdict_path = write_verdict(full_verdict)
    logger.info('Overall: {}', 'PASS' if full_verdict.overall_passed else 'FAIL')

    # Also keep simple TestVerdict for CLI JSON output
    verdict = TestVerdict(
        mode=mode,
        phases=results,
        overall='pass' if full_verdict.overall_passed else 'fail',
        burnish_fixes=len(state.burnish_fixes),
    )
    return verdict


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    '--mode', type=click.Choice(['burnish', 'regression']), default='burnish',
    help='burnish = self-healing via volume mount; regression = clean clone, pass/fail.',
)
@click.option(
    '--phase', type=click.Choice(['all', 'demo', 'full', 'verify']), default='all',
    help='Which phase(s) to run.',
)
def integration_test(mode: str, phase: str):
    """Run the LinkedOut installation integration test."""
    verdict = run_integration_test(mode, phase)
    click.echo(json.dumps(asdict(verdict), indent=2))
    raise SystemExit(0 if verdict.overall == 'pass' else 1)
