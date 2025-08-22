"""
Generic live plotting components for the simulation.
"""

from __future__ import annotations

import itertools
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Protocol

from bokeh.layouts import column
from bokeh.models import ColumnDataSource, LayoutDOM
from bokeh.palettes import Category10_10
from bokeh.plotting import figure
from bokeh.server.server import Server

if TYPE_CHECKING:
    from queue import Queue

    from bokeh.document import Document

    from simulation.metrics.metrics_tracker import MetricsSnapshot, TrackingJob


class PlotAdapter(Protocol):
    """A protocol for plot adapter classes."""

    def update(self, snapshot: MetricsSnapshot) -> None:
        """Update the plot's data source with a new snapshot."""

    def get_layout(self) -> LayoutDOM:
        """Return the Bokeh layout for this plot."""


class MetricsAdapter(threading.Thread):
    """Polls a TrackingJob and puts new snapshots into a queue."""

    def __init__(
        self,
        job: TrackingJob,
        queue: Queue,
        poll_interval: float = 0.5,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self._job = job
        self._queue = queue
        self._poll_interval = poll_interval
        self._last_snapshot_count = 0
        self._logger = logger or logging.getLogger(__name__)
        if not logger:
            self._logger.disabled = True
        self.running = True

    def run(self) -> None:
        """Poll for new data until stopped."""
        while self.running:
            try:
                new_snapshots = self._job.snapshots[self._last_snapshot_count :]
                if new_snapshots:
                    for snapshot in new_snapshots:
                        self._queue.put(snapshot)
                    self._last_snapshot_count = len(self._job.snapshots)
            except ValueError as e:
                self._logger.error("MetricsAdapter thread error: %s", e)

            time.sleep(self._poll_interval)

    def stop(self) -> None:
        """Signal the thread to stop."""
        self.running = False


class LivePlotter:
    """Manages the Bokeh server and a layout of registered plot configs."""

    def __init__(self, queue: Queue) -> None:
        self._queue = queue
        self._plot_configs: list[dict[str, Any]] = []
        self._server = None
        self.server_thread: threading.Thread | None = None
        self._color_cycler = itertools.cycle(Category10_10)

    def add_plot(self, plot_config: dict) -> None:
        """Register a plot configuration to be displayed."""
        # Augment the config with runtime objects it will need
        plot_config["sources"] = {}
        plot_config["indexed_colors"] = {}
        self._plot_configs.append(plot_config)

    def _make_app(self, doc: Document) -> None:
        """Factory function to create the Bokeh application instance."""
        plots = []
        for config in self._plot_configs:
            # Create the plot based on its type
            plot_type = config.get("plot_type", "line")
            if plot_type == "vbar":
                # Special setup for bar charts
                p = figure(
                    height=300,
                    title=config["title"],
                    sizing_mode="stretch_width",
                    x_range=[],  # Start with empty categorical range
                )
            else:
                # Default setup for line charts
                p = figure(
                    height=300, title=config["title"], sizing_mode="stretch_width"
                )
            p.xaxis.axis_label = "Time"
            config["plot"] = p
            plots.append(p)

        def update() -> None:
            """Callback to update plot data from the queue."""
            while not self._queue.empty():
                snapshot: MetricsSnapshot = self._queue.get()
                for config in self._plot_configs:
                    self._update_plot_data(snapshot, config)

        doc.add_periodic_callback(update, 200)
        doc.add_root(column(*plots, sizing_mode="stretch_width"))
        doc.title = "Live Simulation Metrics"

    def _update_plot_data(
        self, snapshot: MetricsSnapshot, config: dict[str, Any]
    ) -> None:
        """Dispatches to the correct update function based on plot type."""
        plot_type = config.get("plot_type", "line")
        if plot_type == "line":
            self._update_line_plot(snapshot, config)
        elif plot_type == "indexed_line":
            self._update_indexed_line_plot(snapshot, config)
        elif plot_type == "vbar":
            self._update_vbar_plot(snapshot, config)

    def _update_line_plot(self, snapshot: MetricsSnapshot, config: dict) -> None:
        plot = config["plot"]
        sources = config["sources"]
        key = "main"
        if key not in sources:
            sources[key] = ColumnDataSource(data=dict(x=[], y=[]))
            plot.line(x="x", y="y", source=sources[key], legend_label=config["title"])

        metrics_group = snapshot.metrics.get(config["metric_group"], {})
        value = metrics_group.get(config["metric_key"])
        if value is not None:
            sources[key].stream({"x": [snapshot.timestamp], "y": [value]}, 1000)

    def _update_indexed_line_plot(
        self, snapshot: MetricsSnapshot, config: dict
    ) -> None:
        plot = config["plot"]
        sources = config["sources"]
        colors = config["indexed_colors"]
        metrics_group = snapshot.metrics.get(config["metric_group"], {})

        for index_key, item_metrics in metrics_group.items():
            if isinstance(item_metrics, dict):
                value = item_metrics.get(config["metric_key"])
                if value is not None:
                    if index_key not in sources:
                        color = next(self._color_cycler)
                        colors[index_key] = color
                        sources[index_key] = ColumnDataSource(data=dict(x=[], y=[]))
                        plot.line(
                            x="x",
                            y="y",
                            source=sources[index_key],
                            legend_label=index_key,
                            color=color,
                        )
                    sources[index_key].stream(
                        {"x": [snapshot.timestamp], "y": [value]}, 1000
                    )

    def _update_vbar_plot(self, snapshot: MetricsSnapshot, config: dict) -> None:
        plot = config["plot"]
        sources = config["sources"]
        key = "main"
        metrics_group = snapshot.metrics.get(config["metric_group"], {})
        data_dict = metrics_group.get(config["metric_key"])

        if not isinstance(data_dict, dict):
            return

        categories = list(data_dict.keys())
        counts = list(data_dict.values())

        if key not in sources:
            plot.x_range.factors = categories
            sources[key] = ColumnDataSource(data=dict(x=categories, top=counts))
            plot.vbar(x="x", top="top", width=0.8, source=sources[key])
        else:
            # For bar charts, we replace the data, not stream
            plot.x_range.factors = categories
            sources[key].data = dict(x=categories, top=counts)

    def start(self, port: int = 5006) -> Server:
        """Start the Bokeh server in a background thread."""
        self._server = Server(
            {"/": self._make_app},
            num_procs=1,
            port=port,
            allow_websocket_origin=[f"localhost:{port}"],
        )
        self.server_thread = threading.Thread(target=self._server.io_loop.start)
        self.server_thread.daemon = True
        self.server_thread.start()
        return self._server
