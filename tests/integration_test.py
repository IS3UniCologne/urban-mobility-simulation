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


TEMPLATES = [
    "ridehailing_template.py",
    "shared_vehicle_fleet_template.py",
    "public_transport_template.py",
]

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
    _validate_simulation_log(log_path, script)


def _validate_simulation_log(log_path: Path, script: str) -> None:
    """Validate the content of a simulation log file.

    Parameters
    ----------
    log_path : Path
        Path to the log file to validate.
    script : str
        Name of the template script that generated the log.
    """
    with open(log_path, encoding="utf-8") as f:
        log_content = f.read()

    # Check for simulation completion
    if "Ending Simulation" not in log_content:
        pytest.fail(
            "Simulation did not end properly - 'Ending Simulation' not found in log"
        )

    # Template-specific validations
    if script == "ridehailing_template.py":
        expected_entry = (
            "Missed trip of User 554. Current Total Revenue: 824.9877006243544 - "
            "Total Trips: 75 - Missed Trips 178."
        )
        if expected_entry not in log_content:
            pytest.fail("Total revenue not as expected in ridehailing template")

    elif script == "public_transport_template.py":
        expected_entry = (
            "Missed trip of User 561. Current Total Revenue: 0 - "
            "Total Trips: 0 - Missed Trips 1124."
        )
        if expected_entry not in log_content:
            pytest.fail("Total revenue not as expected in public transport template")

    # Note: shared_vehicle_fleet_template validation is commented out in original
    logging.info(
        "Successfully validated log file %s for template %s",
        log_path.name,
        script,
        extra={"clazz": "integration_test", "oid": ""},
    )
