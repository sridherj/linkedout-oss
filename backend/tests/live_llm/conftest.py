# SPDX-License-Identifier: Apache-2.0
"""Pytest configuration for live LLM tests.

These tests hit real LLM APIs and require API keys configured in .env.local.
They use the same PostgreSQL integration test infrastructure.
"""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Add src directory to Python path
src_path = Path(__file__).parent.parent.parent / 'src'
sys.path.insert(0, str(src_path))

# Load environment
env_path = Path(__file__).parent.parent.parent
load_dotenv(env_path / '.env', override=False)
load_dotenv(env_path / '.env.local', override=True)


def pytest_configure(config):
    config.addinivalue_line(
        'markers',
        'live_llm: mark test as requiring a live LLM API call'
    )
