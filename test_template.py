"""Template used for running integration tests of the simulation."""

import sys

from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation


def main() -> None:
    """Run the simulation with a given configuration file."""
    config = Configuration(sys.argv[1])

    simulation = Simulation(config)

    simulation.run_simulation()

    simulation.metrics.operator_metrics.to_log()


if __name__ == "__main__":
    main()
