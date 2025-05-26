import glob
import itertools
import os
import subprocess
import sys

import pytest


def run_template_script(script_path, config_file):
    cmd = [sys.executable, script_path, config_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


templates = [
    "ridehailing_template.py",
    "shared_vehicle_fleet_template.py",
    "public_transport_template.py",
]

# Grab all *.toml files in the test/configurations directory
config_files_pattern = os.path.join("test", "configurations", "*.toml")
configs = sorted(glob.glob(config_files_pattern))


@pytest.mark.parametrize("script,config", itertools.product(templates, configs))
def test_templates(script, config):
    """We test each template in combination with each configuration file in the test directory.
    We check that the script runs without error and that a log file is generated properly.
    TODO: Check metrics once we have implemented them universally. Add more test configurations. (resolutions, etc.)
    """
    # Confirm that the file exists
    assert os.path.exists(script), f"{script} does not exist."
    assert os.path.exists(config), f"{config} does not exist."

    output_dir = "data/test_output"

    # Make sure the output log directory is empty
    if os.path.exists(f"{output_dir}/logs"):
        existing_logs = os.listdir(f"{output_dir}/logs")
    else:
        os.makedirs(f"{output_dir}/logs")
        existing_logs = []

    result = run_template_script(script, config)
    assert result.returncode == 0, (
        f"Script {script} using configuration {config} failed with error:\n{result.stderr}"
    )

    log_files = os.listdir(f"{output_dir}/logs")

    # get log file that is not in existing_logs
    new_log_files = [file for file in log_files if file not in existing_logs]
    assert len(new_log_files) == 1, (
        f"Expected exactly one new log file, found {len(new_log_files)}"
    )
    log_file = new_log_files[0]

    # TODO: These tests are "special" temporary tests. They should be replaced with proper metrics tests once we solve #20 and have unified metrics.
    with open(f"{output_dir}/logs/{log_file}") as f:
        log = f.read()
        assert "Ending Simulation" in log, "Simulation did not end properly."
        # if this is the ridehailing template, check the last entry with Total Revenue in the log
        if script == "ridehailing_template.py":
            assert (
                "Missed trip of User 554. Current Total Revenue: 824.9877006243544 - Total Trips: 75 - Missed Trips 178."
                in log
            ), "Total revenue not as expected."

        # if script == "shared_vehicle_fleet_template.py":
        #     assert (
        #         "Missed trip of User 555. Current Total Revenue: 575.7043348440625 - Total Trips: 68 - Missed Trips 473."
        #         in log
        #     ), "Total revenue not as expected."
        if script == "public_transport_template.py":
            assert (
                "Missed trip of User 561. Current Total Revenue: 0 - Total Trips: 0 - Missed Trips 1124."
                in log
            ), "Total revenue not as expected."
