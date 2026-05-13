"""Default template for running the simulation. Contains examples for some common tasks."""

import sys

from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation


def main() -> None:
    """Run the simulation."""
    # Load configuration from command line argument
    config = Configuration(sys.argv[1])

    simulation = Simulation(config)

    simulation.metrics.tracker.create_job(
        name="charging_station_metrics",
        interval=1.0,
        tracked_classes=["ChargingStationMetrics"],
    )
    simulation.metrics.tracker.create_job(
        name="fleet_metrics", interval=1.0, tracked_classes=["FleetMetrics"]
    )

    # Start periodic tracking
    simulation.metrics.tracker.start_all_jobs()

    # Run the simulation
    simulation.run_simulation()

    # Stop periodic tracking
    simulation.metrics.tracker.stop_all_jobs()

    # Save tracked metrics to file
    simulation.metrics.tracker.export_all_jobs("tracked_metrics")

    simulation.metrics.to_log()


if __name__ == "__main__":
    main()
