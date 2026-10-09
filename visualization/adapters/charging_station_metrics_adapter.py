"""Plot adapter for metrics from the charging stations."""

from simulation.metrics.metrics import MetricsDict


class ChargingStationMetricsPlotAdapter:
    """Adapter for plotting charging station metrics."""

    @property
    def cost_per_kWh(self) -> dict:
        """Configuration for plotting the current price per kWh of each charging station"""

        def trasform(snapshot: MetricsDict) -> MetricsDict:
            """The aggregate entry has no price, skip it."""
            return {
                location: metrics
                for location, metrics in snapshot.items()
                if location != "aggregate"
            }

        return {
            "title": "Price per kWh by Charging Station",
            "metric_group": "charging_station",
            "metric_key": "cost_per_kWh",
            "plot_type": "indexed_line",
            "transform": trasform,
        }
