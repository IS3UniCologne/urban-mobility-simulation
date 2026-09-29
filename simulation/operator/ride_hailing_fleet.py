from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

from simulation.helper.enums import AutonomyType
from simulation.helper.time import SimulationTimeConverter
from simulation.helper.vehicle_states import VehicleStates
from simulation.operator.vehicle_fleet import VehicleFleet, VehicleFleetDependencies
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import VehicleConfig


class RideHailingFleet(VehicleFleet):  # noqa: D101
    __slots__ = ("_driver_availability_vectors", "_env", "_recharging_threshold")

    def __init__(self, deps: VehicleFleetDependencies) -> None:
        super().__init__(deps=deps)

        self._driver_availability_vectors: dict[VehicleConfig, list[int] | None] = {}
        # Calculate absolute driver availability for human-driven vehicles
        for vehicle_config in deps.config.VEHICLES:
            if vehicle_config.AUTONOMY_TYPE == AutonomyType.HUMAN_DRIVEN:
                total_count = deps.config.VEHICLES[vehicle_config]
                self._driver_availability_vectors[vehicle_config] = [
                    round(float(x) * total_count) for x in deps.config.RH_AVAILABILITY
                ]
            else:
                self._driver_availability_vectors[vehicle_config] = None

        self._create_fleet_vehicles(deps)

    def count_vehicles_below_soc_level(self, state_of_charge_threshold):  # noqa: ANN001, ANN201
        """
        Return all vehicles that need to be refueled/recharged
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """  # noqa: D205, D400
        hour = SimulationTimeConverter.hour_of_day(self._sim.env.now)
        state_of_charge_threshold = state_of_charge_threshold[hour]
        return sum(
            1
            for vehicle in self._vehicles
            if vehicle.energy_system.current_energy_relative < state_of_charge_threshold
        )

    def get_all_vehicles_below_soc_level_in_region(  # noqa: ANN201
        self,
        state_of_charge_threshold,  # noqa: ANN001
        region,  # noqa: ANN001
    ):
        """
        Return all vehicles that need to be refueled/recharged in a region
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """  # noqa: D205, D400
        below_soc_level_vehicles = []
        cars_in_area = self.vehicles_in_region(region)
        # TODO: Check if this is necessary
        cars_in_area_sorted = sorted(cars_in_area, key=lambda v: v.uid)

        for vehicle in cars_in_area_sorted:
            if (
                vehicle.energy_system.current_energy_relative
                < state_of_charge_threshold
            ):
                below_soc_level_vehicles.append(vehicle)

        return below_soc_level_vehicles

    def count_cars(self):  # noqa: ANN201, D102
        return len(self._vehicles)

    def count_total(self):  # noqa: ANN201, D102
        return self.count_cars()

    def calc_supply_per_region(self):  # noqa: ANN201
        """TODO: We can probably get rid of this ? If we need it in the future we should implement it with cached values
        Return a list of number of vehicles in each region
        :return: Dictionary, where key = hex_id and value is a dictionary with mode and count values
                e.g., {"H1212j1": {"SharedKickScooters": 0, "SharedScooters": 1, "SharedCars": 2}, "h12h1j2": ...}
        """  # noqa: D205, D400
        available_vehicles = ["RideHailingCar"]
        values = [0] * len(available_vehicles)

        # Set counter to 0 for all vehicle types
        # vehicle_dict = dict(zip(available_vehicles, values))

        supply = {}

        for mode in available_vehicles:
            if mode == "RideHailingCar":
                vehicle_list = self._vehicles
            else:
                raise NotImplementedError(f"Fleet Not Ready to Work with {mode}")

            for vehicle in vehicle_list:
                hex_id = vehicle.position.get_region_id()

                if hex_id not in supply:
                    supply[hex_id] = dict(zip(available_vehicles, values))

                supply[hex_id][mode] += 1

        return supply

    def calc_vehicles_to_be_charged_per_region(self, state_of_charge_threshold):  # noqa: ANN001, ANN201
        """
        Return a list of number of vehicles that need to be charged in each area.

        :param state_of_charge_threshold:
        :return: Dictionary, where key = hex_id and value is a dictionary counting the vehicles to be charged
                 e.g., {"H1212j1": {"SharedKickScooters": 0, "SharedScooters": 1, "SharedCars": 2}, "h12h1j2": ...}
        """
        available_vehicles = ["RideHailingCar"]
        values = [0] * len(available_vehicles)

        # Set counter to 0 for all vehicle types
        # vehicle_dict = dict(zip(available_vehicles, values))

        low_soc_supply = {}

        for mode in available_vehicles:
            if mode == "RideHailingCar":
                vehicle_list = self._vehicles

            else:
                raise NotImplementedError(f"Fleet Not Ready to Work with {mode}")

            for vehicle in vehicle_list:
                hex_id = vehicle.position.get_region_id()

                if hex_id not in low_soc_supply:
                    low_soc_supply[hex_id] = dict(zip(available_vehicles, values))

                if (
                    vehicle.energy_system.current_energy_relative
                    < state_of_charge_threshold
                ):
                    low_soc_supply[hex_id][mode] += 1

        return low_soc_supply

    def mark_vehicles_to_be_charged(self, state_of_charge_threshold):  # noqa: ANN001, ANN201
        """Mark and return vehicles that need to be charged.

        Checks all vehicles (STANDBY and in-use) and marks those below the SoC
        threshold for charging. For vehicles in use, uses predicted energy
        after task completion.

        Parameters
        ----------
        state_of_charge_threshold : list
            Hourly thresholds for state of charge (0 to 1).

        Returns
        -------
        list
            Vehicles marked for charging, sorted by current energy level.
        """
        # TODO: Does this really belong in the fleet?
        hour = SimulationTimeConverter.hour_of_day(self._sim.env.now)
        threshold = state_of_charge_threshold[hour]

        low_soc_vehicles = []
        # Only check vehicles that are not OFFLINE
        offline_vehicles = self._vehicles_by_state.get(VehicleStates.OFFLINE, set())
        candidate_vehicles = set(self.vehicles) - offline_vehicles

        for vehicle in sorted(candidate_vehicles, key=lambda v: v.uid):
            if vehicle.is_reserved:
                continue
            if vehicle.energy_system.predicted_energy_relative < threshold:
                low_soc_vehicles.append(vehicle)

        return low_soc_vehicles

    def _create_vehicle(
        self,
        deps: VehicleFleetDependencies,
        position: GeodesicPosition,
        vehicle_config: VehicleConfig,
    ) -> None:
        RideHailingVehicle(
            sim=deps.sim,
            position=position,
            fleet=self,
            vehicle_config=vehicle_config,
            driver_availability_vector=self._driver_availability_vectors[
                vehicle_config
            ],
            cost_reporter=self.operator.cost_ledger,
        )
