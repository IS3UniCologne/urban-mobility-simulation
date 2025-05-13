from simpy import Environment

from simulation.helper.configuration.enums import VehicleMode
from simulation.operator.vehicle_fleet import VehicleFleet


class MixedSharedVehicleFleet(VehicleFleet):
    def __init__(self, env: Environment):
        super(MixedSharedVehicleFleet, self).__init__(env)

    def vehicles_below_soc_threshold(self, state_of_charge_threshold):
        """
        Return all vehicles that need to be refueled/recharged
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """

        return {
            vehicle
            for vehicle in self.vehicles
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold
        }

    def vehicles_below_soc_threshold_in_region(self, state_of_charge_threshold, region):
        """
        Return all vehicles that need to be refueled/recharged in a region
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """
        below_soc_level_vehicles = []
        vehicles_in_region = self.get_vehicles_in_region(region)

        for vehicle in vehicles_in_region:
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold:
                below_soc_level_vehicles.append(vehicle)

        return below_soc_level_vehicles

    def supply_per_region(self):
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

    def vehicles_to_be_charged_per_region(self, state_of_charge_threshold):
        """
        Return a list of number of vehicles that need to be charged in each area.

        :param state_of_charge_threshold:
        :return: Dictionary, where key = hex_id and value is a dictionary counting the vehicles to be charged
                 e.g., {"H1212j1": {"SharedKickScooters": 0, "SharedScooters": 1, "SharedCars": 2}, "h12h1j2": ...}
        """

        low_soc_supply = {}

        # Create a set of vehicles needing charge for fast lookups
        vehicles_needing_charge = self.vehicles_below_soc_threshold(
            state_of_charge_threshold
        )

        if not vehicles_needing_charge:
            return low_soc_supply

        # For each region with vehicles
        for region_id, vehicles_in_region in self._vehicles_by_region.items():
            # Find vehicles in this region that need charging
            region_vehicles_needing_charge = vehicles_in_region.intersection(
                vehicles_needing_charge
            )

            if not region_vehicles_needing_charge:
                continue

            # Initialize region entry
            low_soc_supply[region_id] = {mode.name: 0 for mode in VehicleMode}

            # Count vehicles by mode in this region that need charging
            for mode in VehicleMode:
                if mode not in self._vehicles_by_mode:
                    continue

                count = len(
                    region_vehicles_needing_charge.intersection(
                        self._vehicles_by_mode[mode]
                    )
                )
                if count > 0:
                    low_soc_supply[region_id][mode.name] = count

        return low_soc_supply
