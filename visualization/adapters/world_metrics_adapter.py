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
        """Configuration for plotting vehicle state distribution as a bar chart."""
        return {
            "title": "Vehicle State Distribution",
            "metric_group": "world",
            "metric_key": "vehicle_state_distribution",
            "plot_type": "vbar",  # Specify a vertical bar chart
        }
