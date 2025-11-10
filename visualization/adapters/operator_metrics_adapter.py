"""Plot adapter for metrics from the 'operator' group."""


class OperatorMetricsPlotAdapter:
    """Provides plot configurations for operator metrics."""

    @property
    def total_revenue(self) -> dict:
        """Configuration for plotting the total revenue of each operator."""
        return {
            "title": "Operator Revenue",
            "metric_group": "operator",
            "metric_key": "total_revenue",
            "plot_type": "indexed_line",
        }

    @property
    def total_fulfilled_trips(self) -> dict:
        """Configuration for plotting the fulfilled trips of each operator."""

        return {
            "title": "Fulfilled Trips by Operator",
            "metric_group": "operator",
            "metric_key": "total_fulfilled_trips",
            "plot_type": "indexed_line",
        }

    @property
    def trip_fulfillment_rate(self) -> dict:
        """Configuration for plotting the rate of fulfilled trips of each operator."""

        return {
            "title": "Rate of Fulfilled Trips by Operator",
            "metric_group": "operator",
            "metric_key": "trip_fulfillment_rate",
            "plot_type": "indexed_line",
        }

    @property
    def total_service_tasks_scheduled(self) -> dict:
        """Configuration for potting the total number of ServiceTasks of each each operator using IntegratedSharedMobilityOperations."""

        return {
            "title": "Total Scheduled ServiceTasks by Operator",
            "metric_group": "operator",
            "metric_key": "total_service_tasks_scheduled",
            "plot_type": "indexed_line",
        }

    @property
    def finished_service_tasks(self) -> dict:
        """Configuration for potting the total number of ServiceTasks with TaskState.FINISHED of each each operator using IntegratedSharedMobilityOperations."""

        return {
            "title": "Finished ServiceTasks by Operator",
            "metric_group": "operator",
            "metric_key": "finished_service_tasks",
            "plot_type": "indexed_line",
        }
