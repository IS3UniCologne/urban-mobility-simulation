"""Global test configuration and shared fixtures for urban mobility simulation tests."""

import sys
from collections.abc import Generator
from pathlib import Path

import pytest

from simulation.environment.geodesic_position import GeodesicPosition


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


@pytest.fixture
def sample_positions() -> dict[str, "GeodesicPosition"]:
    """Provide sample geodesic positions for testing.

    Returns
    -------
    dict
        Dictionary containing sample positions for Berlin area.
    """
    from simulation.environment.geodesic_position import GeodesicPosition

    return {
        "berlin_center": GeodesicPosition(52.5200, 13.4050),
        "brandenburg_gate": GeodesicPosition(52.5170, 13.3888),
        "museum_island": GeodesicPosition(52.5243, 13.4105),
        "potsdamer_platz": GeodesicPosition(52.5096, 13.3764),
    }


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test outputs.

    Parameters
    ----------
    tmp_path : Path
        Pytest's temporary directory fixture.

    Returns
    -------
    Path
        Path to temporary output directory.
    """
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    (output_dir / "logs").mkdir()
    return output_dir
