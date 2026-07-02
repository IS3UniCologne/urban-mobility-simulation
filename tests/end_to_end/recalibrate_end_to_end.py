"""Script to recalibrate end-to-end test expectations.

Use this script whenever there are intentional changes to the simulation that
affect the overall metrics. It runs the simulations for all configurations under
tests/configurations and updates the expectations file with the new metrics.

The updated expectations are saved in tests/end_to_end_expectations.json.

Usage:
    python tests/end_to_end/recalibrate_end_to_end.py

Note:
    Please use this script responsibly, as it will overwrite existing expectations :)"""

import json
import logging
import os
import sys
from pathlib import Path

# Add the project root to the python path
sys.path.append(os.getcwd())

from tests.end_to_end.end_to_end_shared import (
    build_e2e_datasets,
    run_simulation_and_extract_metrics,
)

# Discover all configuration directories under tests/configurations
CONFIG_DIRS = sorted(
    str(p)
    for p in Path("tests", "configurations").iterdir()
    if p.is_dir() and (p / "config.toml").exists()
)

EXPECTATIONS_FILE = Path("tests/end_to_end/end_to_end_expectations.json")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def recalibrate() -> None:
    """Rebuild scenario datasets, run simulations, and update expectations."""
    logger.info("Rebuilding scenario datasets...")
    build_e2e_datasets()

    expectations = {}

    for config_path in CONFIG_DIRS:
        config_name = Path(config_path).name
        logger.info("Running simulation for %s...", config_name)

        expectations[config_name] = run_simulation_and_extract_metrics(config_path)

    logger.info("Updating expectations in %s...", EXPECTATIONS_FILE)
    with open(EXPECTATIONS_FILE, "w") as f:
        json.dump(expectations, f, indent=2)
        f.write("\n")
    logger.info("Done.")


if __name__ == "__main__":
    recalibrate()
