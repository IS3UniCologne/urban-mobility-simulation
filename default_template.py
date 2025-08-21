"""
Default template for running the simulation.

Contains examples for some common tasks, including live web-based visualization.
"""

import sys
import threading
import webbrowser
from queue import Queue

from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation
from visualization.live_visualization import BokehPlotter, MetricsAdapter


def main() -> None:
    """Run the simulation."""
    # Load configuration from command line argument
    config = Configuration(sys.argv[1])

    simulation = Simulation(config)

    # Set up time-series metrics tracking. A shorter interval is better for live plotting.
    simulation.metrics.tracker.create_job(
        name="live_metrics",
        interval=10.0,
        tracked_classes=["WorldMetrics", "OperatorMetrics"],
        start_now=True,
    )

    # --- Live Visualization Setup ---
    # 1. Create the communication queue
    data_queue = Queue()

    # 2. Get a logger for the visualization components
    logger = simulation.sim.log_manager.get_class_logger("visualization")

    # 3. Start the adapter thread to listen for metrics
    adapter = MetricsAdapter(
        simulation.metrics.tracker, "live_metrics", data_queue, logger=logger
    )
    adapter.start()

    # 4. Configure and start the Bokeh server using the builder pattern
    plotter = BokehPlotter(data_queue)
    plotter.plot_simple_metric(
        "world", "active_user_processes", title="Active User Processes"
    )
    plotter.plot_indexed_metric("operator", "total_revenue", title="Operator Revenue")
    server = plotter.start()

    # 4. Open a browser window to the plot
    def open_browser() -> None:
        webbrowser.open(f"http://localhost:{server.port}/")

    # Give the server a moment to start, then open the browser
    threading.Timer(1.5, open_browser).start()

    # --- Run Simulation ---
    # Manually capture initial state at t=0
    simulation.metrics.tracker.capture("live_metrics")

    simulation.run_simulation()

    # Manually capture final state
    simulation.metrics.tracker.capture("live_metrics")

    # --- Shutdown ---
    simulation.metrics.tracker.stop_job("live_metrics")
    adapter.stop()
    adapter.join(timeout=2)  # Wait for the adapter to finish

    # The Bokeh server thread is a daemon, so it will exit automatically.
    # For a more robust application, you might add plotter.stop() and handle the IOLoop shutdown.

    # Log final metrics example
    simulation.metrics.operator_metrics.to_log()
    simulation.metrics.world_metrics.to_log()


if __name__ == "__main__":
    main()
