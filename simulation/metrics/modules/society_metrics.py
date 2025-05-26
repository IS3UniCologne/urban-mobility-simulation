class SocietyMetrics:
    __slots__ = ("_transactions",)

    def __init__(self, transactions):  # noqa: ANN001, ANN204
        self._transactions = transactions

    def get_co2_emissions(self, co2_per_km_per_vehicle):  # noqa: ANN001, ANN201
        self._transactions["trip_emissions"] = self._transactions[
            "distance"
        ] * self._transactions["selected_vehicle_mode"].map(co2_per_km_per_vehicle)

        return self._transactions.groupby("selected_vehicle_mode")[
            "trip_emissions"
        ].sum()

    def print_summary(self, co2_per_km_per_vehicle: dict):  # noqa: ANN201
        print("")  # noqa: T201
        print("#--------Society Metrics--------")  # noqa: T201
        print(" ")  # noqa: T201
        print(  # noqa: T201
            f"#  Co2 Emissions: {self.get_co2_emissions(co2_per_km_per_vehicle).sum()} "
        )
        print(" ")  # noqa: T201
        print("-" * 40)  # noqa: T201
