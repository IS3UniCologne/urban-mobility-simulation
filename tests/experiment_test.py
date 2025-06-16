import glob
import itertools
import os
import subprocess
import sys

import pytest

# pytestmark = pytest.mark.skip(
#     reason="This runs all experiments, which is slow and not needed for every test."
# )


def run_template_script(script_path, config_file):  # noqa: ANN001, ANN201
    # make sure they run in the base directory of the repo
    # Find the repository root directory (parent of the test directory)
    test_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(test_dir)

    # Change to the repository root directory
    os.chdir(repo_root)

    # Set up environment with PYTHONPATH to include the repository root
    env = os.environ.copy()
    env["PYTHONPATH"] = repo_root

    cmd = [sys.executable, script_path, config_file]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result


# Grab all *.toml files in the test/configurations directory
config_files_pattern = os.path.join("test", "configurations", "*.toml")
configs = sorted(glob.glob(config_files_pattern))

# Grab all experiments in the resources/scripts/experiments directory
templates = glob.glob("resources/scripts/experiments/*.py")


@pytest.mark.parametrize("script,config", itertools.product(templates, configs))
def test_experiments(script, config):  # noqa: ANN001, ANN201
    """We test each template in combination with each configuration file in the test directory.
    We check that the script runs without error and that a log file is generated properly.
    TODO: Check metrics once we have implemented them universally. Add more test configurations. (resolutions, etc.)
    """
    # Confirm that the file exists
    assert os.path.exists(script), f"{script} does not exist."
    assert os.path.exists(config), f"{config} does not exist."

    result = run_template_script(script, config)
    assert result.returncode == 0, (
        f"Script {script} using configuration {config} failed with error:\n{result.stderr}"
    )
