"""Global test configuration and shared fixtures for urban mobility simulation tests."""

import sys
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment() -> Generator[None, None, None]:
    """Set up the test environment for all tests.

    This fixture automatically configures the test environment by setting
    the configuration file path and performs cleanup after tests complete.

    Yields
    ------
    None
        Control is yielded to the test execution.
    """
    # Store original arguments
    original_argv = sys.argv.copy()

    # Set the configuration file path for testing
    config_path = Path("tests/configurations/testing_config_res7.toml")
    if config_path.exists():
        sys.argv = [sys.argv[0], str(config_path)]
    else:
        # Fallback to template config
        sys.argv = [sys.argv[0], "resources/configurations/config_template.toml"]

    yield

    # Restore original arguments after tests complete
    sys.argv = original_argv
