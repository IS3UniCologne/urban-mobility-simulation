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
        start_now=True,
    )
    simulation.metrics.tracker.create_job(
        name="fleet_metrics",
        interval=1.0,
        tracked_classes=["FleetMetrics"],
        start_now=True,
    )

    # TODO: start_all_jobs, end all etc

    # Run the simulation
    simulation.run_simulation()

    # Stop periodic tracking
    simulation.metrics.tracker.stop_job("charging_station_metrics")
    simulation.metrics.tracker.stop_job("fleet_metrics")

    # Save tracked metrics to file
    simulation.metrics.tracker.export_all("tracked_metrics")

    simulation.metrics.to_log()


if __name__ == "__main__":
    main()
