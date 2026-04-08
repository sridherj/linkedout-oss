# SPDX-License-Identifier: Apache-2.0
"""Pytest configuration for live service tests.

These tests call external services (Apify, etc.) and require real API keys
configured in .env.local. They are excluded from the default test run.
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
        'live_services: mark test as calling external services (Apify, etc.) — requires real API keys'
    )
