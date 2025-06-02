class GeneralMetrics:
    __slots__ = ("_transactions",)

    def __init__(self, transactions):  # noqa: ANN001, ANN204
        self._transactions = transactions

    def get_num_user_requests(self) -> int:
        return len(self._transactions)

    def get_fulfilled_trips(self):  # noqa: ANN201
        return self._transactions[self._transactions["state"] == "Fulfilled"]

    def get_missed_trips(self):  # noqa: ANN201
        return self._transactions[self._transactions["state"] == "Missed"]

    def get_num_fulfilled_trips(self):  # noqa: ANN201
        return len(self.get_fulfilled_trips())

    def get_num_missed_trips(self):  # noqa: ANN201
        return len(self.get_missed_trips())

    def get_fulfillment_rate(self):  # noqa: ANN201
        num_user_requests = self.get_num_user_requests()
        return (
            self.get_num_fulfilled_trips() / num_user_requests
            if num_user_requests > 0
            else 0
        )

    def get_traveled_distance(self):  # noqa: ANN201
        return self._transactions["distance"].sum()

    def __str__(self):  # noqa: ANN204
        return self.print_summary()

    def print_summary(self):  # noqa: ANN201
        print("")  # noqa: T201
        print("#--------General Metrics--------")  # noqa: T201
        print(" ")  # noqa: T201
        print(f"#  Num. Trips: {len(self._transactions)} ")  # noqa: T201
        print(f"#  Num. Ful. Trips: {self.get_num_fulfilled_trips()} ")  # noqa: T201
        print(f"#  Num. Miss. Trips: {self.get_num_missed_trips()} ")  # noqa: T201
        print(f"#  Num. Ful. Rate: {self.get_fulfillment_rate()} ")  # noqa: T201
        print(f"#  Distance: {self.get_traveled_distance()} ")  # noqa: T201
        print(" ")  # noqa: T201
        print("-" * 40)  # noqa: T201
