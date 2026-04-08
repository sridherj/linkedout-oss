# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for LinkedOut installation tests.

All fixtures create isolated resources. No test touches the real
``~/linkedout-data/`` directory or the ``linkedout`` database.
"""
from __future__ import annotations

import json
import subprocess
from unittest.mock import patch
from uuid import uuid4

import pytest

# ── Markers ───────────────────────────────────────────────────────


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (> 10 seconds)")
    config.addinivalue_line(
        "markers", "requires_postgres: skips when PostgreSQL is unavailable"
    )


# ── PostgreSQL availability ───────────────────────────────────────

_pg_available: bool | None = None


def _check_pg_available() -> bool:
    global _pg_available
    if _pg_available is not None:
        return _pg_available
    try:
        result = subprocess.run(
            ["pg_isready"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        _pg_available = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _pg_available = False
    return _pg_available


requires_postgres = pytest.mark.skipif(
    not _check_pg_available(),
    reason="PostgreSQL server is not available",
)

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def temp_data_dir(tmp_path):
    """Isolated data directory for each test.

    Creates the standard subdirectory layout that the setup flow
    expects to find under ``~/linkedout-data/``.
    """
    data_dir = tmp_path / f"linkedout-data-test-{uuid4().hex[:8]}"
    data_dir.mkdir()
    for subdir in ("config", "logs", "reports", "state", "uploads"):
        (data_dir / subdir).mkdir()
    yield data_dir
    # Cleanup handled by tmp_path


@pytest.fixture
def test_db():
    """Isolated PostgreSQL database.

    Creates a temporary database named ``linkedout_test_{uuid}`` and
    drops it after the test completes.  Skips if PostgreSQL is not
    available.
    """
    if not _check_pg_available():
        pytest.skip("PostgreSQL server is not available")

    db_name = f"linkedout_test_{uuid4().hex[:8]}"
    try:
        subprocess.run(["createdb", db_name], check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        pytest.skip(f"Cannot create test database: {exc}")

    db_url = f"postgresql://localhost/{db_name}"
    yield db_url, db_name

    # Cleanup: drop the test database
    subprocess.run(["dropdb", "--if-exists", db_name], check=False, capture_output=True)


@pytest.fixture
def mock_github_releases(tmp_path):
    """Serve seed data from local files (no network).

    Creates a minimal seed directory with a small test file and
    checksum. Tests can use this instead of downloading from GitHub.
    """
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()

    # Create a minimal test seed file
    seed_content = b'{"companies": [], "role_aliases": [], "profiles": []}'
    seed_file = seed_dir / "linkedout-seed-core.json"
    seed_file.write_bytes(seed_content)

    # Create matching checksum
    import hashlib

    sha256 = hashlib.sha256(seed_content).hexdigest()
    checksum_file = seed_dir / "CHECKSUM"
    checksum_file.write_text(f"{sha256}  linkedout-seed-core.json\n")

    yield seed_dir


@pytest.fixture
def mock_openai():
    """Validate key format without making a real API call."""
    with patch("linkedout.setup.api_keys.validate_openai_key") as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_subprocess_run():
    """Mock ``subprocess.run`` for tests that should not spawn processes."""
    with patch("subprocess.run") as mock:
        yield mock


@pytest.fixture
def env_override(temp_data_dir, monkeypatch):
    """Set environment variables to point at isolated test directories.

    This ensures that no setup module accidentally reads from or
    writes to the real ``~/linkedout-data/``.
    """
    monkeypatch.setenv("LINKEDOUT_DATA_DIR", str(temp_data_dir))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("APIFY_API_KEY", raising=False)
    yield temp_data_dir


@pytest.fixture
def sample_config_yaml(temp_data_dir):
    """Write a minimal ``config.yaml`` into the temp data dir."""
    config_dir = temp_data_dir / "config"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        "database_url: postgresql://linkedout:testpass@localhost:5432/linkedout_test\n"
        "data_dir: {data_dir}\n"
        "embedding_provider: local\n".format(data_dir=str(temp_data_dir)),
        encoding="utf-8",
    )
    return config_path


@pytest.fixture
def sample_secrets_yaml(temp_data_dir):
    """Write a minimal ``secrets.yaml`` into the temp data dir."""
    import stat

    config_dir = temp_data_dir / "config"
    config_dir.mkdir(exist_ok=True)
    secrets_path = config_dir / "secrets.yaml"
    secrets_path.write_text(
        "# LinkedOut Secrets\nopenai_api_key: sk-test-1234567890\n",
        encoding="utf-8",
    )
    secrets_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return secrets_path


@pytest.fixture
def setup_state_json(temp_data_dir):
    """Write a setup-state.json marking all steps as complete."""
    state_dir = temp_data_dir / "state"
    state_dir.mkdir(exist_ok=True)
    state_path = state_dir / "setup-state.json"

    state = {
        "steps_completed": {
            "prerequisites": "2026-04-07T10:00:00Z",
            "system_setup": "2026-04-07T10:01:00Z",
            "database": "2026-04-07T10:02:00Z",
            "python_env": "2026-04-07T10:03:00Z",
            "api_keys": "2026-04-07T10:04:00Z",
            "user_profile": "2026-04-07T10:05:00Z",
            "csv_import": "2026-04-07T10:06:00Z",
            "contacts_import": "2026-04-07T10:07:00Z",
            "seed_data": "2026-04-07T10:08:00Z",
            "embeddings": "2026-04-07T10:09:00Z",
            "affinity": "2026-04-07T10:10:00Z",
            "skills": "2026-04-07T10:11:00Z",
            "readiness": "2026-04-07T10:12:00Z",
            "auto_repair": "2026-04-07T10:13:00Z",
        },
        "setup_version": "0.1.0",
        "last_run": "2026-04-07T10:13:00Z",
    }
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state_path


@pytest.fixture
def sample_linkedin_csv(tmp_path):
    """Create a minimal LinkedIn Connections CSV for import testing."""
    csv_path = tmp_path / "Connections.csv"
    csv_path.write_text(
        "First Name,Last Name,Email Address,Company,Position,Connected On\n"
        "Jane,Doe,jane@example.com,Acme Corp,Engineer,01 Jan 2024\n"
        "John,Smith,john@example.com,BigCo,Manager,15 Mar 2024\n",
        encoding="utf-8",
    )
    return csv_path
