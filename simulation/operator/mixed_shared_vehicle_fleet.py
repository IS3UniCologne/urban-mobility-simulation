from __future__ import annotations

import pandas as pd

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import VehicleType
from simulation.operator.vehicle_fleet import VehicleFleet, VehicleFleetDependencies
from simulation.vehicle.shared_vehicle import SharedVehicle


# TODO : rename SharedVehicleFleet, there are only mixed fleets
class MixedSharedVehicleFleet(VehicleFleet):  # noqa: D101
    def __init__(self, deps: VehicleFleetDependencies) -> None:
        super().__init__(deps)

        rng = deps.sim.random_manager.get_rng(component_name="FLEETFACTORY")
        hex_columns = deps.sim.config.world.SPATIAL_RESOLUTION.column_name

        supply_path = deps.sim.config.path.PATH_VEHICLE_SUPPLY
        supply_probabilities = pd.read_csv(supply_path)

        for vehicle_config, total_count in deps.config.VEHICLES.items():
            # TODO: We shouldn't hardcode the columns
            if vehicle_config.VEHICLE_TYPE == VehicleType.CAR:
                vehicle_probabilities = supply_probabilities["cars_prob"].to_numpy()
            elif vehicle_config.VEHICLE_TYPE == VehicleType.BIKE:
                vehicle_probabilities = supply_probabilities["bikes_prob"].to_numpy()
            elif vehicle_config.VEHICLE_TYPE == VehicleType.SCOOTER:
                vehicle_probabilities = supply_probabilities["scooters_prob"].to_numpy()
            elif vehicle_config.VEHICLE_TYPE == VehicleType.KICK_SCOOTER:
                vehicle_probabilities = supply_probabilities[
                    "kick_scooters_prob"
                ].to_numpy()

            else:
                self.logger.error(
                    "MixedSharedVehicleFleet does not support vehicle type %s",
                    vehicle_config.VEHICLE_TYPE,
                )

            vehicle_count = pd.DataFrame(
                rng.multinomial(
                    n=total_count, pvals=vehicle_probabilities, size=1
                ).transpose(),
                columns=["count"],
            )
            vehicle_count.index = supply_probabilities.index
            supply_probabilities["count"] = vehicle_count["count"]

            for _index, row in supply_probabilities.iterrows():
                hex_id = row[hex_columns]
                local_count = row["count"]
                for _ in range(local_count):
                    rdm_lat, rdm_lng = deps.sim.geo_env.get_random_position(hex_id)
                    pos = GeodesicPosition(deps.sim, rdm_lat, rdm_lng, hex_id)
                    SharedVehicle(
                        sim=deps.sim,
                        position=pos,
                        fleet=self,
                        vehicle_config=vehicle_config,
                    )

    def vehicles_below_soc_threshold(self, state_of_charge_threshold):  # noqa: ANN001, ANN201
        """
        Return all vehicles that need to be refueled/recharged
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """  # noqa: D205, D400
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
        """  # noqa: D205, D400
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
        """  # noqa: D401
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
