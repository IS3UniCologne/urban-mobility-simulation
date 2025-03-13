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

# Grab all *.toml files in the configurations directory
config_pattern = os.path.join("test", "configurations", "*.toml")
configs = sorted(glob.glob(config_pattern))


@pytest.mark.parametrize("script,config", itertools.product(templates, configs))
def test_template_execution(script, config):
    # Confirm that the file exists
    assert os.path.exists(script), f"{script} does not exist."
    assert os.path.exists(config), f"{config} does not exist."

    result = run_template_script(script, config)
    assert result.returncode == 0, (
        f"Script {script} using configuration {config} failed with error:\n{result.stderr}"
    )

    # check log file
    assert os.path.exists("report.log"), "Log file not generated."
    with open("report.log", "r") as f:
        log = f.read()
        assert "Ending Simulation" in log, (
            f"Simulation did not end properly. Log:\n{log}"
        )
