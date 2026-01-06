"""Pytest collection helpers for backend test runs.

This file is intentionally at the backend/ directory root so pytest can use
it early during collection to skip non-test runtime artifact directories
(such as `uploads`) that may contain test-like filenames but are not test
code. This prevents pytest from attempting to open arbitrary binary files
under those runtime directories.
"""
from pathlib import Path
import pytest

from app.core.config import settings
from app.core.rate_limit_config import rate_limit_settings

import pytest

@pytest.fixture(scope="session", autouse=True)
def force_testing_mode():
    """Force TESTING=True early in the test session so imports can read it."""
    settings.TESTING = True


def pytest_collection_modifyitems(items):
    """Treat legacy pytest.mark.asyncio as anyio-compatible so tests run under pytest-anyio.

    This makes async tests that use the old marker continue to work when pytest-asyncio
    is not installed and pytest-anyio is the chosen plugin.
    """
    for item in items:
        if 'asyncio' in getattr(item, 'keywords', {}):
            # Add anyio marker so pytest-anyio will run the coroutine
            item.add_marker(pytest.mark.anyio)



def pytest_ignore_collect(path, config):
    """Ignore collection for any path that is inside an `uploads` directory.

    This is a defensive guard to ensure runtime artifact directories never
    get collected as tests (some artifacts may be named like test_* and can
    confuse collectors or plugins). Returning True tells pytest to skip
    collecting that path.
    """
    try:
        p = Path(str(path))
        if "uploads" in p.parts:
            return True
    except Exception:
        # If anything odd happens, do not block collection for other paths
        return False
    return False


@pytest.fixture(scope="session", autouse=True)
def disable_rate_limiting_for_tests():
    """Ensure rate limiting is disabled during test runs to avoid 429 flakiness.

    Sets both `settings.TESTING` and the rate limit global flag to false so
    middleware and dependencies short-circuit where appropriate.
    """
    settings.TESTING = True
    # Also disable global rate limiter regardless of env var
    rate_limit_settings.ENABLED = False


@pytest.fixture(scope="session")
def anyio_backend():
    # Some tests expect 'asyncio' as the anyio backend; provide it here to avoid ScopeMismatch
    return "asyncio"

