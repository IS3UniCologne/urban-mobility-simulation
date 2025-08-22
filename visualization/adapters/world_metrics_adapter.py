"""Plot adapter for metrics from the 'world' group."""


class WorldMetricsPlotAdapter:
    """Provides plot configurations for world metrics."""

    @property
    def active_user_processes(self) -> dict:
        """Configuration for plotting the number of active user processes."""
        return {
            "title": "Active User Processes",
            "metric_group": "world",
            "metric_key": "active_user_processes",
            "plot_type": "line",
        }

    @property
    def total_vehicles(self) -> dict:
        """Configuration for plotting the total number of vehicles."""
        return {
            "title": "Total Vehicles",
            "metric_group": "world",
            "metric_key": "total_vehicles",
            "plot_type": "line",
        }

    @property
    def vehicle_state_distribution(self) -> dict:
        def transform(snapshot):
            return {
                k: {"number": v}
                for k, v in snapshot["vehicle_state_distribution"].items()
            }

        """Configuration for plotting vehicle state distribution as an indexed line chart."""
        return {
            "title": "Vehicle State Distribution (Line)",
            "metric_group": "world",
            "metric_key": "number",  # see above
            "plot_type": "indexed_line",
            "transform": transform,
        }
