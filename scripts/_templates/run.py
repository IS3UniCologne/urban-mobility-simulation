"""Run script for this project."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PROJECT_DIR.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation


def main() -> None:
    """Prepare and run the simulation."""
    ### --- PRE-RUN SETUP --- ###
    config = Configuration(str(_PROJECT_DIR))

    ### --- RUN --- ###
    simulation = Simulation(config)
    simulation.run_simulation()

    ### --- POST-RUN --- ###
    simulation.metrics.user_metrics.to_log()


if __name__ == "__main__":
    main()
