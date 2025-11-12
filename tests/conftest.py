"""
Pytest Configuration and Shared Fixtures
=======================================

Provides shared fixtures and configuration for all tests.

Author: Nicolas Angougeard
"""

import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests"
    )
    config.addinivalue_line(
        "markers", "api: API tests"
    )
    config.addinivalue_line(
        "markers", "ml: Machine learning tests"
    )
