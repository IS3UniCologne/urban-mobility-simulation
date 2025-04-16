class CustomerMetrics:
    __slots__ = ("_transactions",)

    def __init__(self, transactions):
        self._transactions = transactions

    def get_travel_time(self):
        return self._transactions["duration"].sum()

    def get_cost(self):
        return self._transactions["price"].sum()

    def get_avg_waiting_time(self):
        wait_time_by_vehicle = self._transactions.groupby("selected_vehicle_mode")[
            "wait_time"
        ].mean()

        return wait_time_by_vehicle.mean()

    def get_overall_waiting_time(self):
        wait_time_by_vehicle = self._transactions.groupby("selected_vehicle_mode")[
            "wait_time"
        ].sum()

        return wait_time_by_vehicle.sum()

    def __str__(self):
        return self.print_summary()

    def print_summary(self):
        print("")
        print("#--------Customer Metrics--------")
        print(" ")
        print(f"#  Travel Time: {self.get_travel_time()} ")
        print(f"#  Waiting Time: {self.get_overall_waiting_time()} ")
        print(f"#  Costs: {self.get_cost()} ")
        print(" ")
        print("-" * 40)
