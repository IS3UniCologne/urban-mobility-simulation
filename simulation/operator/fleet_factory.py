from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet


class FleetFactory:


    def generate_mixed_fleet(self, fleet_config):
        import pandas as pd

        fleet = MixedSharedVehicleFleet()

        fleet_config.apply(lambda row: row["cars"], axis = 1)

        hex_column = "hex_id_7"

        for index, row in fleet_config.iterrows():
            # We need to spawn vehicles in this hexagon
            hex_id = row[hex_column]

            # We need to spawn vehicles according to
            car_count = row["cars"]
            scooter_count = row["scooters"]
            kick_scooter_count = row["kick_scooters"]
            bike_count = row["bikes"]

            # TODO: Create Vehicle Object and place on random point on hex.
