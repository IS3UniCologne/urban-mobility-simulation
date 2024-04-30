class SocietyMetrics:
    def __init__(self, transactions):
        self._transactions = transactions

    def get_co2_emissions(self, co2_per_km_per_vehicle):
        self._transactions["trip_emissions"] = self._transactions[
            "distance"
        ] * self._transactions["selected_vehicle_mode"].map(co2_per_km_per_vehicle)

        return self._transactions.groupby("selected_vehicle_mode")[
            "trip_emissions"
        ].sum()

    def print_summary(self, co2_per_km_per_vehicle: dict):
        print("")
        print("#--------Society Metrics--------")
        print(" ")
        print(
            f"#  Co2 Emissions: {self.get_co2_emissions(co2_per_km_per_vehicle).sum()} "
        )
        print(" ")
        print("-" * 40)
