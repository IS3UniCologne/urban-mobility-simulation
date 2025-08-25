from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.configuration.enums import AutonomyType, VehicleState
from simulation.helper.time import SimulationTimeConverter
from simulation.operator.vehicle_fleet import VehicleFleet

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.position import Position
    from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle
    from simulation.vehicle.vehicle import Vehicle
    from simulation.world.world import World


class MixedRideHailingFleet(VehicleFleet):
    __slots__ = (
        "_autonomous_cars",
        "_config",
        "_distance_threshold_to_user",
        "_driver_availability_vector",
        "_env",
        "_recharging_threshold",
        "_ridehailing_cars",
    )

    def __init__(self, sim: SimulationContext, world: World) -> None:
        super().__init__(sim=sim, world=world)
        self._config = sim.config
        self._env = sim.env
        self._ridehailing_cars = []
        self._autonomous_cars = []
        self._distance_threshold_to_user = (
            self._config.ride_hailing_global.MAX_PICKUP_DISTANCE
        )
        self._driver_availability_vector = (
            self._config.ride_hailing_global.DRIVER_AVAILABILITY_VECTOR
        )
        self._recharging_threshold = self._config.operators[
            0
        ].OPERATIONS_CONFIG.RECHARGE_THRESHOLD  # TODO: Get this from somewhere else
        self._env.process(self.fleet_size_monitor())

    def _add_vehicle(self, vehicle: RideHailingVehicle):  # noqa: ANN202
        if vehicle not in self._vehicles:
            if vehicle.autonomy_type == AutonomyType.HUMAN_DRIVEN:
                self._vehicles.append(vehicle)
                self._world.add_vehicle(vehicle)
                self._ridehailing_cars.append(vehicle)
            elif vehicle.autonomy_type == AutonomyType.AUTONOMOUS:
                self._vehicles.append(vehicle)
                self._world.add_vehicle(vehicle)
                self._autonomous_cars.append(vehicle)

        else:
            raise Exception(f"Vehicle {vehicle} is already registered in Fleet")

    def get_available_vehicles_to_user(self, origin: Position):  # noqa: ANN201
        """
        Find available vehicles that can serve a user at a given origin location.

        This method identifies two types of available vehicles:
        1. Parked vehicles within a distance threshold from the user's origin
        2. Currently serving vehicles that will complete their service and be within the distance threshold

        The availability considers the vehicle's state, whether it has been suggested to another user,
        and for serving vehicles, the battery state of charge must exceed a threshold.

        Parameters
        ----------
        origin : Position
            The location where the user is requesting a vehicle

        Returns
        -------
        list
            A combined list of parked and serving vehicles that are available to the user
            at the specified origin location
        """

        parking_cars: set[Vehicle] = self._vehicles_by_state[VehicleState.PARKING]

        # TODO: Check if this is necessary
        parking_cars_sorted = sorted(parking_cars, key=lambda v: v.uid)
        parking_cars_not_suggested: list[Vehicle] = [
            car
            for car in parking_cars_sorted
            # TODO: we should not acceess _suggested directly
            if not car._suggested  # noqa: SLF001
        ]

        if not parking_cars_not_suggested:
            parking_cars_in_area = []
        else:
            parking_cars_in_area = [
                car
                for car in parking_cars_not_suggested
                if (car.position << origin) <= self._distance_threshold_to_user
            ]

        serving_state = VehicleState.DRIVING
        serving_vehicles = self._vehicles_by_state[serving_state]
        hour = SimulationTimeConverter.hour_of_day(self._env.now)
        state_of_charge_threshold = self._recharging_threshold[hour]
        # TODO: Check if this is necessary
        serving_vehicles_sorted = sorted(serving_vehicles, key=lambda v: v.uid)
        serving_cars = [
            car
            for car in serving_vehicles_sorted
            if car._suggested  # noqa: SLF001
            and car.current_relative_state_of_charge > state_of_charge_threshold + 5
        ]

        serving_cars_in_area = []
        for car in serving_cars:
            distance_to_current_destination = (
                car.estimated_completion_time - self._env.now
            ) * car.velocity
            if (
                car.destination.position << origin
            ) + distance_to_current_destination <= self._distance_threshold_to_user:
                serving_cars_in_area.append(car)

        return parking_cars_in_area + serving_cars_in_area

    def count_vehicles_below_soc_level(self, state_of_charge_threshold):  # noqa: ANN001, ANN201
        """
        Return all vehicles that need to be refueled/recharged
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """
        hour = SimulationTimeConverter.hour_of_day(self._env.now)
        state_of_charge_threshold = state_of_charge_threshold[hour]
        return sum(
            1
            for vehicle in self._vehicles
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold
        )

    def get_operational_costs(self):  # noqa: ANN201
        operational_costs = 0
        all_vehicle_list = self._vehicles
        for vehicle in all_vehicle_list:
            if vehicle.autonomy_type == AutonomyType.AUTONOMOUS:
                operational_costs += vehicle.travel_costs + vehicle.charging_costs
        return operational_costs

    def get_all_vehicles_below_soc_level_in_region(  # noqa: ANN201
        self,
        state_of_charge_threshold,  # noqa: ANN001
        region,  # noqa: ANN001
    ):
        """
        Return all vehicles that need to be refueled/recharged in a region
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """
        below_soc_level_vehicles = []
        cars_in_area = self.vehicles_in_region(region)
        # TODO: Check if this is necessary
        cars_in_area_sorted = sorted(cars_in_area, key=lambda v: v.uid)

        for vehicle in cars_in_area_sorted:
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold:
                below_soc_level_vehicles.append(vehicle)

        return below_soc_level_vehicles

    def count_cars(self):  # noqa: ANN201
        return len(self._vehicles)

    def driver_availability_vector(self):  # noqa: ANN201
        return self._driver_availability_vector

    def count_total(self):  # noqa: ANN201
        return self.count_cars()

    def calc_supply_per_region(self):  # noqa: ANN201
        """TODO: We can probably get rid of this ? If we need it in the future we should implement it with cached values
        Return a list of number of vehicles in each region
        :return: Dictionary, where key = hex_id and value is a dictionary with mode and count values
                e.g., {"H1212j1": {"SharedKickScooters": 0, "SharedScooters": 1, "SharedCars": 2}, "h12h1j2": ...}
        """
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

                if vehicle.current_relative_state_of_charge < state_of_charge_threshold:
                    low_soc_supply[hex_id][mode] += 1

        return low_soc_supply

    def mark_vehicles_to_be_charged(self, state_of_charge_threshold):  # noqa: ANN001, ANN201
        """
        Return a list of number of vehicles that need to be charged in each area.

        :param state_of_charge_threshold:
        :return: List, vehicles with low SoC}
        """
        # available_vehicles = ["RideHailingCar"]
        # values = [0] * len(available_vehicles)

        # Set counter to 0 for all vehicle types
        # vehicle_dict = dict(zip(available_vehicles, values))

        low_soc_supply = []
        hour = SimulationTimeConverter.hour_of_day(self._env.now)
        state_of_charge_threshold = state_of_charge_threshold[hour]

        parking_vehicles = self._vehicles_by_state[VehicleState.PARKING]
        # TODO: Check if this is necessary
        parking_vehicles_sorted = sorted(parking_vehicles, key=lambda v: v.uid)

        for vehicle in parking_vehicles_sorted:
            if (
                vehicle.current_relative_state_of_charge < state_of_charge_threshold
                and not vehicle._suggested  # noqa: SLF001
            ):
                low_soc_supply.append(vehicle)

        low_soc_supply = sorted(
            low_soc_supply, key=lambda x: x.current_relative_state_of_charge
        )
        return low_soc_supply

    def get_online_vehicles(self):  # noqa: ANN201
        """
        Return all vehicles which are online

        :param
        :return: Lists of online vehicles
        """

        online_vehicles = [
            car for car in self._ridehailing_cars if car.state != VehicleState.OFFLINE
        ]

        return online_vehicles

    def get_offline_vehicles(self):  # noqa: ANN201
        """
        Return all vehicles which are online

        :param
        :return: Lists of online vehicles
        """

        online_vehicles = [
            car for car in self._ridehailing_cars if car.state == VehicleState.OFFLINE
        ]

        return online_vehicles

    def fleet_size_monitor(self):  # noqa: ANN201
        """
        Monitoring the number of online vehicles
        :return:
        """
        while True:
            number_of_online_vehicles = len(self.get_online_vehicles())
            self.logger.info("Fleet has %s online vehicles", number_of_online_vehicles)
            yield self._env.timeout(60)
