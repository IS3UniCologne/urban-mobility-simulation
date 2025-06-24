from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.configuration.enums import VehicleType
from simulation.operator.vehicle_fleet import VehicleFleet

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext


class MixedSharedVehicleFleet(VehicleFleet):
    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim=sim)

    def vehicles_below_soc_threshold(self, state_of_charge_threshold):  # noqa: ANN001, ANN201
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

    def vehicles_below_soc_threshold_in_region(self, state_of_charge_threshold, region):  # noqa: ANN001, ANN201
        """
        Return all vehicles that need to be refueled/recharged in a region
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """
        below_soc_level_vehicles = []
        vehicles_in_region = self.vehicles_in_region(region)
        # TODO: Check if this is necessary
        vehicles_in_region_sorted = sorted(vehicles_in_region, key=lambda v: v.uid)

        for vehicle in vehicles_in_region_sorted:
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold:
                below_soc_level_vehicles.append(vehicle)

        return below_soc_level_vehicles

    def supply_per_region(self) -> dict[str, dict[str, int]]:
        """Calculates the supply of vehicles by mode for each region.

        This method iterates through the regions and counts the number of vehicles
        available in each region, categorized by their mode (e.g., CAR, BIKE, etc.).

        Returns
        -------
        dict
            A dictionary with region IDs as keys. Each value is another dictionary
            mapping vehicle mode names to the count of vehicles of that mode in the region.
            Empty regions and modes with no vehicles are excluded.
            Example:
            {
                '871f1d4f3ffffff': {'CAR': 5, 'BIKE': 3},
                '871f1d4f4ffffff': {'SCOOTER': 2}
            }
        """
        supply = {}

        # For each region with vehicles
        for region_id, vehicles_in_region in self._vehicles_by_region.items():
            if not vehicles_in_region:  # Skip empty regions
                continue

            # Initialize the region in our supply dictionary
            supply[region_id] = {mode: 0 for mode in VehicleType}

            # Count vehicles by mode in this region
            for mode in VehicleType:
                count = len(
                    vehicles_in_region.intersection(
                        self._vehicles_by_type.get(mode, set())
                    )
                )
                if count > 0:
                    supply[region_id][mode] = count

        return supply

    def vehicles_to_be_charged_per_region(self, state_of_charge_threshold):  # noqa: ANN001, ANN201
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
            low_soc_supply[region_id] = {mode: 0 for mode in VehicleType}

            # Count vehicles by mode in this region that need charging
            for mode in VehicleType:
                if mode not in self._vehicles_by_type:
                    continue

                count = len(
                    region_vehicles_needing_charge.intersection(
                        self._vehicles_by_type[mode]
                    )
                )
                if count > 0:
                    low_soc_supply[region_id][mode] = count

        return low_soc_supply
