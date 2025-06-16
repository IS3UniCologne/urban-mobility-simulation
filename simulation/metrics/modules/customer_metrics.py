class CustomerMetrics:
    __slots__ = ("_transactions",)

    def __init__(self, transactions):  # noqa: ANN001, ANN204
        self._transactions = transactions

    def get_travel_time(self):  # noqa: ANN201
        return self._transactions["duration"].sum()

    def get_cost(self):  # noqa: ANN201
        return self._transactions["price"].sum()

    def get_avg_waiting_time(self):  # noqa: ANN201
        wait_time_by_vehicle = self._transactions.groupby("selected_vehicle_mode")[
            "wait_time"
        ].mean()

        return wait_time_by_vehicle.mean()

    def get_overall_waiting_time(self):  # noqa: ANN201
        wait_time_by_vehicle = self._transactions.groupby("selected_vehicle_mode")[
            "wait_time"
        ].sum()

        return wait_time_by_vehicle.sum()

    def __str__(self):  # noqa: ANN204
        return self.print_summary()

    def print_summary(self):  # noqa: ANN201
        print("")  # noqa: T201
        print("#--------Customer Metrics--------")  # noqa: T201
        print(" ")  # noqa: T201
        print(f"#  Travel Time: {self.get_travel_time()} ")  # noqa: T201
        print(f"#  Waiting Time: {self.get_overall_waiting_time()} ")  # noqa: T201
        print(f"#  Costs: {self.get_cost()} ")  # noqa: T201
        print(" ")  # noqa: T201
        print("-" * 40)  # noqa: T201
