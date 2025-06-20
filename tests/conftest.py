"""Global test configuration and shared fixtures for urban mobility simulation tests."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(scope="function", autouse=True)
def mock_logging(request: pytest.FixtureRequest) -> Generator[Mock, None, None]:
    """Mock logging functionality for all unit tests.

    This fixture automatically mocks the LogManager to avoid logging setup
    complexity in unit tests.

    For LogManager-specific tests, this fixture is skipped to allow direct
    testing of the LogManager functionality.

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object to get test information.

    Yields
    ------
    Mock
        A mock logger that can be used for assertions if needed.
    """
    # Check if this is a LogManager specific test by looking at the test file path
    # If it is, skip the automatic mocking to allow testing the actual LogManager
    test_file = str(request.fspath)
    if "log_manager" in test_file.lower() and "test" in test_file.lower():
        yield Mock()  # Return a basic mock but don't patch anything
        return

    mock_logger = Mock()
    mock_logger.info = Mock()
    mock_logger.debug = Mock()
    mock_logger.warning = Mock()
    mock_logger.error = Mock()
    mock_logger.critical = Mock()
    mock_logger.exception = Mock()

    # Mock the LogManager class methods to avoid initialization complexity
    with (
        patch(
            "simulation.helper.logging.log_manager.LogManager.setup_logging"
        ) as mock_setup,
        patch(
            "simulation.helper.logging.log_manager.LogManager.get_uid_logger"
        ) as mock_get_logger,
    ):
        mock_get_logger.return_value = mock_logger
        mock_setup.return_value = None

        yield mock_logger
