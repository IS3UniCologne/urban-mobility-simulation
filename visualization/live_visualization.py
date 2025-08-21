"""
Live, web-based plotting for simulation metrics using Bokeh.

This module provides components to run a Bokeh server in a background thread
to visualize metrics from a running simulation without blocking it.
"""

import itertools
import logging
import threading
import time
from queue import Queue
from typing import Any

from bokeh.layouts import column
from bokeh.models import ColumnDataSource
from bokeh.palettes import Category10_10
from bokeh.plotting import figure
from bokeh.server.server import Server

from simulation.metrics.metrics_tracker import MetricsSnapshot, MetricsTracker


class MetricsAdapter(threading.Thread):
    """Polls the MetricsTracker and puts new snapshots into a queue."""

    def __init__(
        self,
        tracker: MetricsTracker,
        job_name: str,
        queue: Queue,
        poll_interval: float = 0.5,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self._tracker = tracker
        self._job_name = job_name
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
                # NOTE: Accessing a protected member is a pragmatic choice here
                # as this class is tightly coupled with the MetricsTracker.
                job = self._tracker._require_job(self._job_name)  # noqa: SLF001
                new_snapshots = job.snapshots[self._last_snapshot_count :]
                if new_snapshots:
                    for snapshot in new_snapshots:
                        self._queue.put(snapshot)
                    self._last_snapshot_count = len(job.snapshots)
            except ValueError:
                # Job may not be registered yet, wait patiently.
                pass
            except Exception as e:
                self._logger.error("MetricsAdapter thread error: %s", e)

            time.sleep(self._poll_interval)

    def stop(self) -> None:
        """Signal the thread to stop."""
        self.running = False


class BokehPlotter:
    """Manages the Bokeh server and application for live plotting."""

    def __init__(self, queue: Queue):
        self._queue = queue
        self._plot_configs: list[dict[str, Any]] = []
        self._server = None
        self.server_thread: threading.Thread | None = None
        # Prepare a color cycler for indexed plots
        self._color_cycler = itertools.cycle(Category10_10)
        self._indexed_colors: dict[str, str] = {}

    def plot_simple_metric(
        self, metric_group: str, metric_key: str, title: str | None = None
    ) -> None:
        """Configure a new subplot for a single, non-indexed metric."""
        config = {
            "title": title or metric_key.replace("_", " ").title(),
            "metric_group": metric_group,
            "metric_key": metric_key,
            "indexed": False,
        }
        self._plot_configs.append(config)

    def plot_indexed_metric(
        self, metric_group: str, metric_key: str, title: str | None = None
    ) -> None:
        """Configure a new subplot for an indexed metric (e.g., per-operator)."""
        config = {
            "title": title or metric_key.replace("_", " ").title(),
            "metric_group": metric_group,
            "metric_key": metric_key,
            "indexed": True,
        }
        self._plot_configs.append(config)

    def _make_app(self, doc) -> None:
        """Factory function to create the Bokeh application instance."""
        plots = []
        for config in self._plot_configs:
            p = figure(
                height=300,
                # width is controlled by sizing_mode
                title=config["title"],
                sizing_mode="stretch_width",
            )
            p.xaxis.axis_label = "Time"
            if config["indexed"]:
                p.legend.location = "top_left"
                p.legend.click_policy = "hide"
            config["plot"] = p
            config["sources"] = {}
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
        """Update the ColumnDataSources for a given plot configuration."""
        metrics_group_data = snapshot.metrics.get(config["metric_group"])
        if not isinstance(metrics_group_data, dict):
            return

        plot = config["plot"]
        sources = config["sources"]

        if not config.get("indexed", False):
            key = "main"
            if key not in sources:
                sources[key] = ColumnDataSource(data=dict(x=[], y=[]))
                plot.line(
                    x="x",
                    y="y",
                    source=sources[key],
                    legend_label=config["metric_key"].replace("_", " ").title(),
                )

            value = metrics_group_data.get(config["metric_key"])
            if value is not None:
                new_data = {"x": [snapshot.timestamp], "y": [value]}
                sources[key].stream(new_data, rollover=1000)

        else:  # Indexed plot
            for index_key, item_metrics in metrics_group_data.items():
                if isinstance(item_metrics, dict):
                    value = item_metrics.get(config["metric_key"])
                    if value is not None:
                        if index_key not in sources:
                            # Assign a persistent color to each new indexed key
                            if index_key not in self._indexed_colors:
                                self._indexed_colors[index_key] = next(
                                    self._color_cycler
                                )
                            color = self._indexed_colors[index_key]

                            sources[index_key] = ColumnDataSource(data=dict(x=[], y=[]))
                            plot.line(
                                x="x",
                                y="y",
                                source=sources[index_key],
                                legend_label=index_key,
                                color=color,
                            )

                        new_data = {"x": [snapshot.timestamp], "y": [value]}
                        sources[index_key].stream(new_data, rollover=1000)

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
