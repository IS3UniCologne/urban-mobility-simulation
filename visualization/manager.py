"""The main entry point for the live visualization system."""

import threading
import webbrowser
from queue import Queue

from simulation.context.simulation_context import SimulationContext
from visualization.adapters.operator_metrics_adapter import OperatorMetricsPlotAdapter
from visualization.adapters.world_metrics_adapter import WorldMetricsPlotAdapter
from visualization.live_plotter import LivePlotter, MetricsAdapter


class VisualizationManager:
    """A high-level manager for the live visualization system."""

    def __init__(self, simulation: SimulationContext, interval: float = 10.0) -> None:
        self._job = simulation.metrics.tracker.create_job(
            name="visualization", interval=interval, start_now=True, replace=True
        )
        self._logger = simulation.sim.log_manager.get_class_logger("Visualization")

        # Internal setup of the visualization pipeline
        self._queue = Queue()
        self._metrics_adapter = MetricsAdapter(
            self._job, self._queue, logger=self._logger
        )
        self._plotter = LivePlotter(self._queue)

        # Expose the plot adapters to the user
        self.world = WorldMetricsPlotAdapter()
        self.operators = OperatorMetricsPlotAdapter()

    def add_plot(self, plot_config: dict) -> None:
        """Register a plot configuration to be displayed."""
        self._plotter.add_plot(plot_config)

    def start(self, timeout: float = 1.5, port: int = 5006) -> None:
        """Start the visualization system and open the browser."""
        self._metrics_adapter.start()
        server = self._plotter.start(port)

        def open_browser() -> None:
            webbrowser.open(f"http://localhost:{server.port}/")

        threading.Timer(timeout, open_browser).start()
        self._logger.info(
            "Visualization server started. View at http://localhost:%s/", server.port
        )

    def stop(self) -> None:
        """Signal the visualization components to shut down gracefully."""
        self._metrics_adapter.stop()
        self._metrics_adapter.join(timeout=1)
        self._logger.info("Visualization stopped.")
