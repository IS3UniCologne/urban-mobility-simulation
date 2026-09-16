"""Plot adapter for metrics from the 'operator' group."""

from simulation.metrics.metrics_dict import MetricsDict

_FINANCIAL_KEYS = {"total_revenue": "revenue", "total_cost": "cost", "profit": "profit"}


class OperatorMetricsPlotAdapter:
    """Provides plot configurations for operator metrics."""

    @property
    def financials(self) -> dict:
        """Configuration for plotting revenue, cost and profit of each operator in one chart."""

        def transform(snapshot: MetricsDict) -> dict[str, dict[str, float]]:
            return {
                f"{uid} {label}": {"amount": operator_metrics[key]}
                for uid, operator_metrics in snapshot.items()
                if uid != "aggregate"
                for key, label in _FINANCIAL_KEYS.items()
            }

        return {
            "title": "Operator Revenue, Cost and Profit",
            "metric_group": "operator",
            "metric_key": "amount",  # see transform
            "plot_type": "indexed_line",
            "transform": transform,
        }

    @property
    def aggregate_financials(self) -> dict:
        """Configuration for plotting revenue, cost and profit summed over all operators."""

        def transform(snapshot: MetricsDict) -> dict[str, dict[str, float]]:
            aggregate = snapshot["aggregate"]
            return {
                label: {"amount": aggregate[key]}
                for key, label in _FINANCIAL_KEYS.items()
            }

        return {
            "title": "Total Revenue, Cost and Profit",
            "metric_group": "operator",
            "metric_key": "amount",  # see transform
            "plot_type": "indexed_line",
            "transform": transform,
        }

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
