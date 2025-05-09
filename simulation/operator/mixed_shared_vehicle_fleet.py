from simpy import Environment

from simulation.helper.configuration.enums import VehicleMode
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.vehicle.vehicle import VehicleState


class MixedSharedVehicleFleet(VehicleFleet):
    def __init__(self, env: Environment):
        super(MixedSharedVehicleFleet, self).__init__(env)

    def vehicles_in_region(self, region):
        """
        Return all vehicles which are located in a region

        Example
        cars, scooters, kick_scooters, bikes = fleet.get_all_vehicles('871f1d4acffffff')

        :param region: Hexagon ID
        :return: Lists of vehicles in area
        """
        vehicles_in_region = self._vehicles_by_region[region]

        cars_in_area = vehicles_in_region.intersection(
            self._vehicles_by_mode[VehicleMode.Car]
        )
        scooters_in_area = vehicles_in_region.intersection(
            self._vehicles_by_mode[VehicleMode.Scooter]
        )
        kick_scooters_in_area = vehicles_in_region.intersection(
            self._vehicles_by_mode[VehicleMode.KickScooter]
        )
        bikes_in_area = vehicles_in_region.intersection(
            self._vehicles_by_mode[VehicleMode.Bike]
        )

        return cars_in_area, scooters_in_area, kick_scooters_in_area, bikes_in_area

    def get_parking_vehicles_in_region(self, region):
        """
        Return all parking vehicles which are located in a region

        Example
        cars, scooters, kick_scooters, bikes = fleet.get_all_vehicles('871f1d4acffffff')

        :param region: Hexagon ID
        :return: Lists of vehicles in area
        """
        vehicles_in_region = self._vehicles_by_region[region]
        parking_vehicles = self._vehicles_by_state[VehicleState.PARKING]
        parking_vehicles_in_region = vehicles_in_region.intersection(parking_vehicles)

        parking_cars_in_region = list(
            parking_vehicles_in_region.intersection(
                self._vehicles_by_mode[VehicleMode.Car]
            )
        )
        parking_scooters_in_region = list(
            parking_vehicles_in_region.intersection(
                self._vehicles_by_mode[VehicleMode.Scooter]
            )
        )
        parking_kick_scooters_in_region = list(
            parking_vehicles_in_region.intersection(
                self._vehicles_by_mode[VehicleMode.KickScooter]
            )
        )
        parking_bikes_in_region = list(
            parking_vehicles_in_region.intersection(
                self._vehicles_by_mode[VehicleMode.Bike]
            )
        )

        return (
            parking_cars_in_region,
            parking_scooters_in_region,
            parking_kick_scooters_in_region,
            parking_bikes_in_region,
        )

    def get_all_vehicles_below_soc_level(self, state_of_charge_threshold):
        """
        Return all vehicles that need to be refueled/recharged
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """
        below_soc_level_vehicles = []
        all_vehicle_list = self.vehicles

        for vehicle in all_vehicle_list:
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold:
                below_soc_level_vehicles.append(vehicle)

        return below_soc_level_vehicles

    def get_all_vehicles_below_soc_level_in_region(
        self, state_of_charge_threshold, region
    ):
        """
        Return all vehicles that need to be refueled/recharged in a region
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """
        below_soc_level_vehicles = []
        cars_in_area, scooters_in_area, kick_scooters_in_area, bikes_in_area = (
            self.vehicles_in_region(region)
        )

        for vehicle in [
            *cars_in_area,
            *scooters_in_area,
            *kick_scooters_in_area,
            *bikes_in_area,
        ]:
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold:
                below_soc_level_vehicles.append(vehicle)

        return below_soc_level_vehicles

    def calc_supply_per_region(self):
        """# TODO: Implement when vehicle by type is in
        Return a list of number of vehicles in each region
        :return: Dictionary, where key = hex_id and value is a dictionary with mode and count values
                e.g., {"H1212j1": {"SharedKickScooters": 0, "SharedScooters": 1, "SharedCars": 2}, "h12h1j2": ...}
        """
        supply = {}

        # For each region with vehicles
        for region_id, vehicles_in_region in self._vehicles_by_region.items():
            if not vehicles_in_region:  # Skip empty regions
                continue

            # Initialize the region in our supply dictionary
            supply[region_id] = {mode.name: 0 for mode in VehicleMode}

            # Count vehicles by mode in this region
            for mode in VehicleMode:
                count = len(
                    vehicles_in_region.intersection(
                        self._vehicles_by_mode.get(mode, set())
                    )
                )
                if count > 0:
                    supply[region_id][mode.name] = count

        return supply

    def calc_vehicles_to_be_charged_per_region(self, state_of_charge_threshold):
        """
        Return a list of number of vehicles that need to be charged in each area.

        :param state_of_charge_threshold:
        :return: Dictionary, where key = hex_id and value is a dictionary counting the vehicles to be charged
                 e.g., {"H1212j1": {"SharedKickScooters": 0, "SharedScooters": 1, "SharedCars": 2}, "h12h1j2": ...}
        """

        low_soc_supply = {}

        # Get all vehicles below SOC threshold
        vehicles_needing_charge = [
            v
            for v in self.vehicles
            if v.current_relative_state_of_charge < state_of_charge_threshold
        ]

        if not vehicles_needing_charge:
            return low_soc_supply

        # Group them by region
        for vehicle in vehicles_needing_charge:
            region_id = vehicle.position.get_region_id()

            # Initialize region dictionary if needed
            if region_id not in low_soc_supply:
                low_soc_supply[region_id] = {mode.name: 0 for mode in VehicleMode}

            # Increment the count for this vehicle's mode
            low_soc_supply[region_id][vehicle.mode.name] += 1

        return low_soc_supply
