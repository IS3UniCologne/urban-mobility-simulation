"""Default template for running the simulation. Contains examples for some common tasks."""

import sys

from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation


def main() -> None:
    """Run the simulation."""
    # Load configuration from command line argument
    config = Configuration(sys.argv[1])

    simulation = Simulation(config)

    # Run the simulation
    simulation.run_simulation()

    simulation.metrics.user_metrics.to_log()


if __name__ == "__main__":
    main()
