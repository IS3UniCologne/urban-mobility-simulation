"""Plot adapter for metrics from the charging stations."""

from simulation.metrics.metrics import MetricsDict


class ChargingStationMetricsPlotAdapter:
    """Adapter for plotting charging station metrics."""

    @property
    def utilization(self) -> dict:
        """Configuration for plotting the utilization of each charging station individually"""

        def transform(snapshot: MetricsDict) -> MetricsDict:
            return {
                location: metrics
                for location, metrics in snapshot.items()
                if location != "aggregate"
            }

        return {
            "title": "Charging Station Utilization",
            "metric_group": "charging_station",
            "metric_key": "utilization",
            "plot_type": "indexed_line",
            "transform": transform,
        }

    @property
    def aggregate_utilization(self) -> dict:
        """Configuration for plotting the aggregate utilization of all charging stations."""

        def transform(snapshot: MetricsDict) -> MetricsDict:
            """Only include the aggregate entry."""
            return {"average_utilization": snapshot["aggregate"]["average_utilization"]}

        return {
            "title": "Aggregate Charging Station Utilization",
            "metric_group": "charging_station",
            "metric_key": "_",  # ignored, see transform
            "plot_type": "line",
            "transform": transform,
        }

    @property
    def price_per_kWh(self) -> dict:
        """Configuration for plotting the current price per kWh of each charging station"""

        def transform(snapshot: MetricsDict) -> MetricsDict:
            """The aggregate entry has no price, skip it."""
            return {
                location: metrics
                for location, metrics in snapshot.items()
                if location != "aggregate"
            }

        return {
            "title": "Price per kWh by Charging Station",
            "metric_group": "charging_station",
            "metric_key": "price_per_kWh",
            "plot_type": "indexed_line",
            "transform": transform,
        }
