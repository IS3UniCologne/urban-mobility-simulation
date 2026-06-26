"""
Generic live plotting components for the simulation.
"""

from __future__ import annotations

import itertools
import threading
import time
from typing import TYPE_CHECKING, Any

try:
    from bokeh.layouts import column
    from bokeh.models import ColumnDataSource
    from bokeh.palettes import Bokeh
    from bokeh.plotting import figure
    from bokeh.server.server import Server
except ImportError as e:
    raise ImportError(
        "Bokeh is required for live visualization. Install with: uv sync --extra viz"
    ) from e

if TYPE_CHECKING:
    from logging import Logger
    from queue import Queue

    from bokeh.document import Document
    from bokeh.models import Column

    from simulation.metrics.metrics_tracker import MetricsSnapshot, TrackingJob

# Sentinel returned when a plot config references a metric not tracked this run.
# (we cant return None because that could be a valid metric value)
_MISSING: Any = object()


class MetricsAdapter(threading.Thread):
    """Polls a TrackingJob and puts new snapshots into a queue."""

    def __init__(
        self, job: TrackingJob, queue: Queue, logger: Logger, poll_interval: float = 0.5
    ) -> None:
        super().__init__(daemon=True)
        self._job = job
        self._queue = queue
        self._poll_interval = poll_interval
        self._last_snapshot_count = 0
        self._logger = logger
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

    def __init__(self, queue: Queue, logger: Logger) -> None:
        self._queue = queue
        self._plot_configs: list[dict[str, Any]] = []
        self._server = None
        self.server_thread: threading.Thread | None = None
        self._color_cycler = itertools.cycle(Bokeh[8])
        self._logger = logger

    def add_plot(self, plot_config: dict) -> None:
        """Register a plot configuration to be displayed."""
        self._plot_configs.append(plot_config)

    def _make_app(self, doc: Document) -> None:
        """Bokeh document factory; lazily renders a panel per tracked metric."""
        layout = column(sizing_mode="stretch_width")
        states: dict[int, dict[str, Any]] = {}

        def update() -> None:
            """Callback to render queued snapshots into this document."""
            while not self._queue.empty():
                snapshot: MetricsSnapshot = self._queue.get()
                for config in self._plot_configs:
                    self._render_config(snapshot, config, states, layout)

        doc.add_periodic_callback(update, 200)
        doc.add_root(layout)
        doc.title = "Live Simulation Metrics"

    def _render_config(
        self,
        snapshot: MetricsSnapshot,
        config: dict[str, Any],
        states: dict[int, dict[str, Any]],
        layout: Column,
    ) -> None:
        """Render one config into the session's layout, building it lazily."""
        if config.get("disabled"):
            return
        metrics = self._extract_metric(snapshot, config)
        if metrics is _MISSING:
            return  # _extract_metric has disabled + warned

        state = states.get(id(config))
        if state is None:
            state = self._build_render_state(config)
            states[id(config)] = state
            layout.children.append(state["plot"])

        plot_type = config["plot_type"]
        if plot_type == "line":
            self._update_line_plot(snapshot.timestamp, metrics, config, state)
        elif plot_type == "indexed_line":
            self._update_indexed_line_plot(snapshot.timestamp, metrics, state)
        elif plot_type == "vbar":
            self._update_vbar_plot(metrics, state)

    def _extract_metric(
        self, snapshot: MetricsSnapshot, config: dict[str, Any]
    ) -> object:
        """Pull the configured metric from a snapshot, or disable+warn if absent."""
        try:
            metrics_group = snapshot.metrics[config["metric_group"]]
            transform = config.get("transform", None)
            if transform:
                metrics_group = transform(metrics_group)
            if config["plot_type"] == "indexed_line":
                return {k: v[config["metric_key"]] for k, v in metrics_group.items()}
            return metrics_group[config["metric_key"]]
        except KeyError:
            config["disabled"] = True
            self._logger.error(
                "Visualization: no tracked metric '%s.%s' for plot %r; disabling it. "
                "Remove the matching viz.add_plot() call in your run.py to remove this error.",
                config["metric_group"],
                config["metric_key"],
                config["title"],
            )
            return _MISSING

    def _build_render_state(self, config: dict[str, Any]) -> dict[str, Any]:
        """Create a fresh figure and per-session source/color stores for a config."""
        if config.get("plot_type") == "vbar":
            plot = figure(
                height=300,
                title=config["title"],
                sizing_mode="stretch_width",
                x_range=[],
            )
        else:
            plot = figure(
                height=300, title=config["title"], sizing_mode="stretch_width"
            )
        plot.xaxis.axis_label = "Time"
        return {"plot": plot, "sources": {}, "colors": {}}

    def _update_line_plot(
        self, x: float, y: object, config: dict, state: dict[str, Any]
    ) -> None:
        plot = state["plot"]
        sources = state["sources"]
        key = "main"
        if key not in sources:
            sources[key] = ColumnDataSource(data=dict(x=[], y=[]))
            plot.line(x="x", y="y", source=sources[key], legend_label=config["title"])

        if y is not None:
            sources[key].stream({"x": [x], "y": [y]}, 1000)

    def _update_indexed_line_plot(
        self, x: float, y_data: object, state: dict[str, Any]
    ) -> None:
        plot = state["plot"]
        sources = state["sources"]
        colors = state["colors"]

        if not isinstance(y_data, dict):
            return

        # Identify new keys that are not yet in the sources
        new_keys = [key for key in y_data if key not in sources]

        # Create new sources and renderers for all new keys, initialized with the first data point
        for new_key in new_keys:
            if (value := y_data.get(new_key)) is not None:
                color = next(self._color_cycler)
                colors[new_key] = color
                sources[new_key] = ColumnDataSource(data=dict(x=[x], y=[value]))
                plot.line(
                    x="x",
                    y="y",
                    source=sources[new_key],
                    legend_label=new_key,
                    color=color,
                )

        # Stream data to existing sources for all subsequent points
        for index_key, value in y_data.items():
            if value is not None:
                sources[index_key].stream({"x": [x], "y": [value]}, 1000)

    def _update_vbar_plot(self, data: object, state: dict[str, Any]) -> None:
        # TODO: this should probably be a "live-updating" bar plot, but what about a growing, stacked barplot
        plot = state["plot"]
        sources = state["sources"]
        key = "main"

        if not isinstance(data, dict):
            return

        categories = list(data.keys())
        counts = list(data.values())

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
