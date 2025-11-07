from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

from simulation.helper.configuration.enums import VehicleType
from simulation.operator.vehicle_fleet import VehicleFleet, VehicleFleetDependencies
from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import VehicleConfig


# TODO : rename SharedVehicleFleet, there are only mixed fleets
class MixedSharedVehicleFleet(VehicleFleet):  # noqa: D101
    def __init__(self, deps: VehicleFleetDependencies) -> None:
        super().__init__(deps)

        self._create_fleet_vehicles(deps)

    def _create_vehicle(
        self,
        deps: VehicleFleetDependencies,
        position: GeodesicPosition,
        vehicle_config: VehicleConfig,
    ) -> None:
        SharedVehicle(
            sim=deps.sim, position=position, fleet=self, vehicle_config=vehicle_config
        )

    def vehicles_below_soc_threshold(
        self, state_of_charge_threshold: float
    ) -> set[SharedVehicle]:
        """Return all vehicles that need to be refueled/recharged.

        Parameters
        ----------
        state_of_charge_threshold : float
            Threshold value between 0 and 1

        Returns
        -------
        set[SharedVehicle]
            Set of vehicles with state of charge below the threshold
        """
        return {
            vehicle
            for vehicle in self.vehicles
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold
        }

    def vehicles_below_soc_threshold_in_region(
        self, state_of_charge_threshold: float, region: str
    ) -> list[SharedVehicle]:
        """Return all vehicles that need to be refueled/recharged in a region.

        Parameters
        ----------
        state_of_charge_threshold : float
            Threshold value between 0 and 1
        region : str
            Region identifier (e.g., hexagon ID)

        Returns
        -------
        list[SharedVehicle]
            List of vehicles in the region with state of charge below the threshold
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
        """Calculate the supply of vehicles by mode for each region.

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
            supply[region_id] = {mode: 0 for mode in self.vehicle_types}

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

    def vehicles_to_be_charged_per_region(
        self, state_of_charge_threshold: float
    ) -> dict[str, dict[VehicleType, int]]:
        """Return a count of vehicles that need to be charged in each region.

        Parameters
        ----------
        state_of_charge_threshold : float
            Threshold value between 0 and 1

        Returns
        -------
        dict
            Dictionary where key = hex_id and value is a dictionary counting
            the vehicles to be charged by vehicle type.
            Example: {"H1212j1": {VehicleType.KICK_SCOOTER: 0, VehicleType.SCOOTER: 1}}
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
            low_soc_supply[region_id] = {mode: 0 for mode in self.vehicle_types}

            # Count vehicles by mode in this region that need charging
            for mode in self.vehicle_types:
                if mode not in self._vehicles_by_type:
                    continue

                count = len(
                    region_vehicles_needing_charge.intersection(
                        self._vehicles_by_type[mode]
                    )
                )
                low_soc_supply[region_id][mode] = count

        return low_soc_supply
