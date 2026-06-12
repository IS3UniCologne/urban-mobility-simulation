class FleetMetricsPlotAdapter:
    @property
    def avg_vehicle_soc(self) -> dict:
        """Configuration for plotting the avg SOC of all vehicles in a fleet."""
        return {
            "title": "Average Vehice SOC",
            "metric_group": "fleet",
            "metric_key": "avg_vehicle_soc",
            "plot_type": "indexed_line",
        }
