"""End-to-end tests for simulation using metrics classes."""

import json
import os
from pathlib import Path

import pytest

from tests.end_to_end.end_to_end_shared import run_simulation_and_extract_metrics

# Discover all configuration directories under tests/configurations
CONFIG_DIRS = sorted(
    str(p) for p in Path("tests", "configurations").iterdir() if p.is_dir()
)

EXPECTATIONS_FILE = Path(__file__).parent / "end_to_end_expectations.json"


@pytest.mark.end_to_end
@pytest.mark.parametrize("config_path", CONFIG_DIRS)
def test_simulation_end_to_end(config_path: str) -> None:
    """
    Run the simulation with the given configuration and verify metrics.

    Parameters
    ----------
    config_path : str
        Path to the configuration directory.
    """
    if not os.path.exists(config_path):
        pytest.skip(f"Configuration file {config_path} does not exist")

    # Run simulation and extract metrics
    try:
        actual_metrics = run_simulation_and_extract_metrics(config_path)
    except Exception as e:
        pytest.fail(f"Simulation failed with error: {e}")

    # Verify metrics
    _validate_metrics(actual_metrics, config_path)


def _validate_metrics(actual_metrics: dict, config_path: str) -> None:
    """
    Validate the metrics of the simulation.

    Parameters
    ----------
    actual_metrics : dict
        The metrics extracted from the simulation.
    config_path : str
        Path to the configuration directory used.
    """
    config_name = Path(config_path).name

    # Load expectations
    if not EXPECTATIONS_FILE.exists():
        pytest.fail(f"Expectations file {EXPECTATIONS_FILE} not found")

    with open(EXPECTATIONS_FILE) as f:
        expectations = json.load(f)

    if config_name not in expectations:
        pytest.fail(f"No expectations found for config {config_name}")

    expected = expectations[config_name]

    # Validate that actual metrics match expected metrics approximately
    assert actual_metrics["operator_metrics"] == pytest.approx(
        expected["operator_metrics"]
    )
    assert actual_metrics["user_metrics"] == pytest.approx(expected["user_metrics"])

    assert actual_metrics["fleet_metrics"].keys() == expected["fleet_metrics"].keys()
    for fleet_id, metrics in actual_metrics["fleet_metrics"].items():
        assert metrics == pytest.approx(expected["fleet_metrics"][fleet_id])
