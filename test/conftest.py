import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():  # noqa: ANN201
    """Set up the test environment for all tests."""
    # Store original arguments
    original_argv = sys.argv.copy()

    # Set the configuration file path
    sys.argv = [sys.argv[0], "resources/configurations/config_template.toml"]

    # Add any other global test setup here

    yield

    # Restore original arguments after tests complete
    sys.argv = original_argv
