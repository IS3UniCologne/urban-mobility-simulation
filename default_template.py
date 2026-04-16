"""
Default template for running the simulation.

Contains examples for some common tasks, including metrics output and live web-based visualization.
"""

import sys

from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation
from visualization.manager import VisualizationManager


def main() -> None:
    """Run the simulation."""
    # Load configuration from command line argument
    config = Configuration(sys.argv[1])

    simulation = Simulation(config)

    # Periodic tracking of World Metrics every 60 simulation time units
    simulation.metrics.tracker.create_job(
        name="world_metrics",
        interval=60.0,
        tracked_classes=["WorldMetrics"],
        start_now=True,
    )

    # Periodic tracking of Operator Metrics every 10 simulation time units
    simulation.metrics.tracker.create_job(
        name="operator_metrics",
        interval=10.0,
        tracked_classes=["OperatorMetrics"],
        start_now=True,
    )

    # Live Visualization
    viz = VisualizationManager(simulation=simulation, interval=10)

    # 2. Declaratively add the plots you want to see
    viz.add_plot(
        viz.world.active_user_processes
    )  # Example for simple metric value line plot
    viz.add_plot(
        viz.operators.total_revenue
    )  # Example for indexed metric plot (one line per operator + aggregate)
    viz.add_plot(
        viz.world.vehicle_state_distribution
    )  # Example for custom indexed metric plot
    viz.add_plot(
        viz.world.wall_time_per_metric_evaluation
    )  # Example for runtime performance monitoring

    # Don't forget to start the visualization server, optionally set timeout and port
    viz.start()

    # Start simulation
    simulation.run_simulation()

    # Log and save final metrics example
    simulation.metrics.operator_metrics.to_log()  # headline aggregate metrics
    simulation.metrics.tracker.export_job(
        name="operator_metrics", file_name="operator_metrics.csv"
    )  # timestamped DataFrame

    # Cleanup
    simulation.metrics.tracker.stop_all_jobs()  # stop all metrics tracking jobs
    viz.stop()  # Gracefully stop the visualization components


if __name__ == "__main__":
    main()
