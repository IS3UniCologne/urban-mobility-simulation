"""Default template for running the simulation. Contains examples for some common tasks."""

import sys

from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation


def main() -> None:
    """Run the simulation."""
    # Load configuration from command line argument
    config = Configuration(sys.argv[1])

    simulation = Simulation(config)

    # Set up time-series metrics tracking
    # Periodic tracking of World Metrics every 60 simulation time units
    simulation.metrics.tracker.create_job(
        name="world_metrics",
        interval=60.0,
        tracked_classes=["WorldMetrics"],
        start_now=True,
    )

    # Run the simulation
    simulation.run_simulation()

    # Stop periodic tracking
    simulation.metrics.tracker.stop_job("world_metrics")

    # Save tracked metrics to file

    # Log final metrics example
    # This will log all operator metrics
    simulation.metrics.operator_metrics.to_log()
    # Log only specific operator metrics
    # simulation.metrics.operator_metrics["RideHailingOperator_1"].to_log()
    # Log world metrics
    simulation.metrics.world_metrics.to_log()
    # Save world metrics to csv file
    # simulation.metrics.world_metrics.to_dict().to_file("world_metrics", "csv")


if __name__ == "__main__":
    main()
