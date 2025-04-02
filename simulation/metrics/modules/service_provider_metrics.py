class ServiceProviderMetrics:
    def __init__(self, transactions):
        __slots__ = ("_transactions")
        self._transactions = transactions

    def get_revenue(self):
        return self._transactions["price"].sum()

    def get_fleet_utilization(self, number_of_vehicles: dict):
        self._transactions["hour"] = self._transactions["time_start"] // 60
        grouped_df = self._transactions.groupby(
            ["selected_vehicle_mode", "vehicle_id", "hour"]
        ).size()
        vehicles_per_hour = (
            grouped_df.groupby(["selected_vehicle_mode", "hour"])
            .size()
            .reset_index(name="num_vehicles_per_hour")
        )
        vehicles_per_hour["capacity"] = vehicles_per_hour["selected_vehicle_mode"].map(
            number_of_vehicles
        )
        vehicles_per_hour["util_per_hour"] = (
            vehicles_per_hour["num_vehicles_per_hour"] / vehicles_per_hour["capacity"]
        )
        total_capacity_per_hour = vehicles_per_hour.groupby("hour")[
            "num_vehicles_per_hour"
        ].sum()
        total_capacity_per_hour.name = "overall_util_per_hour"

        total_capacity_per_hour = total_capacity_per_hour / sum(
            number_of_vehicles.values()
        )

        # print(vehicles_per_hour)
        # print(total_capacity_per_hour)

        return total_capacity_per_hour

    def get_avg_fleet_utilization(self, number_of_vehicles: dict):
        return self.get_fleet_utilization(number_of_vehicles).mean()

    def get_fleet_cost(self, cost_per_vehicle_km):
        self._transactions["trip_costs"] = self._transactions[
            "distance"
        ] * self._transactions["selected_vehicle_mode"].map(cost_per_vehicle_km)

        return self._transactions.groupby("selected_vehicle_mode")["trip_costs"].sum()

    def get_fleet_profit(self, cost_per_vehicle_km: dict):
        revenue_by_vehicle = self._transactions.groupby("selected_vehicle_mode")[
            "price"
        ].sum()

        return revenue_by_vehicle - self.get_fleet_cost(cost_per_vehicle_km)

    def print_summary(self, number_of_vehicles: dict, cost_per_vehicle_km: dict):
        print("")
        print("#--------Service Provider Metrics--------")
        print(" ")
        print(
            f"#  Avg. Fleet. Utilization: {self.get_avg_fleet_utilization(number_of_vehicles)} "
        )
        print(f"#  Fleet Profit: {self.get_fleet_profit(cost_per_vehicle_km).sum()} ")
        print(" ")
        print("-" * 40)
