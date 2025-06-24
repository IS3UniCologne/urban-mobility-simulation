"""Integration tests for simulation templates."""

import glob
import itertools
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_template_script(
    script_path: str, config_file: str
) -> subprocess.CompletedProcess[str]:
    """Run a template script with the given configuration file.

    Parameters
    ----------
    script_path : str
        Path to the template script to execute.
    config_file : str
        Path to the configuration file to use.

    Returns
    -------
    subprocess.CompletedProcess
        The result of the subprocess execution.
    """
    cmd = [sys.executable, script_path, config_file]
    logging.info(
        "Running template script: %s with config: %s",
        script_path,
        config_file,
        extra={"clazz": "integration_test", "oid": ""},
    )
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result


TEMPLATES = ["test_template.py"]

# Get all *.toml files in the tests/configurations directory
CONFIG_FILES_PATTERN = os.path.join("tests", "configurations", "*.toml")
CONFIGS = sorted(glob.glob(CONFIG_FILES_PATTERN))


@pytest.mark.integration
@pytest.mark.parametrize("script,config", itertools.product(TEMPLATES, CONFIGS))
def test_templates(script: str, config: str) -> None:
    """Test each template in combination with each configuration file.

    We check that the script runs without error and that a log file is generated
    properly with expected simulation results.

    Parameters
    ----------
    script : str
        Name of the template script to test.
    config : str
        Path to the configuration file to use.

    Notes
    -----
    TODO: Check metrics once we have implemented them universally.
    Add more test configurations (resolutions, etc.).
    """
    # Confirm that the files exist
    if not os.path.exists(script):
        pytest.skip(f"Template script {script} does not exist")
    if not os.path.exists(config):
        pytest.skip(f"Configuration file {config} does not exist")

    output_dir = Path("data/test_output")
    log_dir = output_dir / "logs"

    # Ensure log directory exists and track existing logs
    log_dir.mkdir(parents=True, exist_ok=True)
    existing_logs = os.listdir(log_dir) if log_dir.exists() else []

    # Run the template script
    try:
        result = run_template_script(script, config)
    except subprocess.TimeoutExpired:
        pytest.fail(f"Script {script} with config {config} timed out after 300 seconds")

    # Check for successful execution
    if result.returncode != 0:
        logging.error(
            "Script %s failed with config %s. stderr: %s",
            script,
            config,
            result.stderr,
            extra={"clazz": "integration_test", "oid": ""},
        )
        pytest.fail(
            f"Script {script} using configuration {config} failed with error:\n{result.stderr}"
        )

    # Verify exactly one new log file was created
    log_files = os.listdir(log_dir)
    new_log_files = [file for file in log_files if file not in existing_logs]

    if len(new_log_files) != 1:
        pytest.fail(
            f"Expected exactly one new log file, found {len(new_log_files)}: {new_log_files}"
        )

    log_file = new_log_files[0]
    log_path = log_dir / log_file

    # Validate log content
    _validate_simulation_log(log_path, config)


def _validate_simulation_log(log_path: Path, config: str) -> None:
    """Validate the content of a simulation log file.

    Parameters
    ----------
    log_path : Path
        Path to the log file to validate.
    config : str
        Path to the configuration file used for the simulation.
    """
    with open(log_path, encoding="utf-8") as f:
        log_content = f.read()

    # Check for simulation completion
    if "Ending Simulation" not in log_content:
        pytest.fail(
            "Simulation did not end properly - 'Ending Simulation' not found in log"
        )

    # Template-specific validations
    if config == "tests/configurations/rh_test.toml":
        # Check for new metrics table entries in the log
        expected_metrics = [
            "|              total_revenue | 883.64     |",
            "|      total_fulfilled_trips | 65         |",
            "|         total_missed_trips | 0          |",
            "|       total_missed_revenue | 0.00       |",
            "|        total_trip_duration | 1,506.11   |",
            "|      average_trip_duration | 23.17      |",
            "|        total_trip_distance | 239,472.13 |",
            "|      average_trip_distance | 3,684.19   |",
            "|         average_trip_price | 13.59      |",
            "|      trip_fulfillment_rate | 0.26       |",
            "|   total_energy_consumption | 76.85      |",
            "| average_energy_consumption | 1.18       |",
            "|              total_revenue | 883.89     |",
            "|      total_fulfilled_trips | 73         |",
            "|         total_missed_trips | 0          |",
            "|       total_missed_revenue | 0.00       |",
            "|        total_trip_duration | 1,457.33   |",
            "|      average_trip_duration | 19.96      |",
            "|        total_trip_distance | 231,715.81 |",
            "|      average_trip_distance | 3,174.19   |",
            "|         average_trip_price | 12.11      |",
            "|      trip_fulfillment_rate | 0.29       |",
            "|   total_energy_consumption | 81.13      |",
            "| average_energy_consumption | 1.11       |",
            "|            total_revenue | 1,767.53   |",
            "|    total_fulfilled_trips | 138        |",
            "|       total_missed_trips | 0          |",
            "|     total_missed_revenue | 0.00       |",
            "|      total_trip_duration | 2,963.45   |",
            "|      total_trip_distance | 471,187.94 |",
            "| total_energy_consumption | 157.98     |",
        ]
        for expected in expected_metrics:
            assert expected in log_content, (
                f"Expected metric '{expected}' not found in ridehailing template log"
            )

    elif config == "tests/configurations/public_transport_test.toml":
        expected_revenue = "Total Revenue: 0.0"
        assert expected_revenue in log_content, (
            "Total revenue not as expected in public transport template"
        )
        expected_total_trips = "Total Fulfilled Trips: 0"
        assert expected_total_trips in log_content, (
            "Total fulfilled trips not as expected in public transport template"
        )
        expected_total_missed_trips = "Total Missed Trips: 562"
        assert expected_total_missed_trips in log_content, (
            "Total missed trips not as expected in public transport template"
        )
        # extra check
        assert (
            "[Time     143.93] [                   TransitUser 561]: Transport request of user 561 has been withdrawn due to lack of vehicles."
            in log_content
        ), (
            "Expected withdrawal message for user 561 not found in public transport template log"
        )

    if config == "tests/configurations/sv_test.toml":
        # Check for new metrics table entries in the log
        expected_metrics = [
            "|              total_revenue | 418.80     |",
            "|    total_transaction_count | 569        |",
            "|      total_fulfilled_trips | 63         |",
            "|         total_missed_trips | 506        |",
            "|       total_missed_revenue | 0.00       |",
            "|        total_trip_duration | 1,572.37   |",
            "|      average_trip_duration | 24.96      |",
            "|        total_trip_distance | 198,128.36 |",
            "|      average_trip_distance | 3,144.89   |",
            "|         average_trip_price | 6.65       |",
            "|      trip_fulfillment_rate | 0.11       |",
            "|   total_energy_consumption | 26.59      |",
            "| average_energy_consumption | 0.42       |",
            "|            total_revenue | 418.80     |",
            "|  total_transaction_count | 569        |",
            "|    total_fulfilled_trips | 63         |",
            "|       total_missed_trips | 506        |",
            "|     total_missed_revenue | 0.00       |",
            "|      total_trip_duration | 1,572.37   |",
            "|      total_trip_distance | 198,128.36 |",
            "| total_energy_consumption | 26.59      |",
        ]
        for expected in expected_metrics:
            assert expected in log_content, (
                f"Expected metric '{expected}' not found in shared vehicle template log"
            )

    logging.info(
        "Successfully validated log file %s for configuration %s",
        log_path.name,
        config,
        extra={"clazz": "integration_test", "oid": ""},
    )
