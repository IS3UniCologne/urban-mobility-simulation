"""Plot adapter for metrics from the 'world' group."""

from simulation.metrics.metrics_dict import MetricsDict


class WorldMetricsPlotAdapter:
    """Provides plot configurations for world metrics."""

    @property
    def wall_time_per_metric_evaluation(self) -> dict:
        """Configuration for plotting how long has elapsed (in seconds) since the last metric evaluation"""
        return {
            "title": "Time per Evaluation",
            "metric_group": "world",
            "metric_key": "wall_time_per_metric_evaluation",
            "plot_type": "line",
        }

    @property
    def active_user_processes(self) -> dict:
        """Configuration for plotting the number of active user processes."""
        return {
            "title": "Active User Processes",
            "metric_group": "world",
            "metric_key": "active_users",
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
        def transform(snapshot: MetricsDict) -> dict[str, dict[str, int]]:
            return {
                k: {"number": v}
                for k, v in snapshot["vehicle_state_distribution"].items()
            }

        """Configuration for plotting vehicle state distribution as an indexed line chart."""
        return {
            "title": "Vehicle State Distribution",
            "metric_group": "world",
            "metric_key": "number",  # see above
            "plot_type": "indexed_line",
            "transform": transform,
        }
