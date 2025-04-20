import logging

import numpy as np
from haversine import Unit, haversine_vector
from simpy import Environment

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import Configuration
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.vehicle.ride_hailing_AV import RideHailingAV
from simulation.vehicle.ride_hailing_car import RideHailingCar
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle
from simulation.vehicle.vehicle import VehicleState


class MixedRideHailingFleet(VehicleFleet):
    __slots__ = (
        "_config",
        "_ridehailing_cars",
        "_autonomous_cars",
        "_distance_threshold_to_user",
        "_driver_availability_vector",
        "_recharging_threshold",
    )

    def __init__(self, env: Environment):
        super(MixedRideHailingFleet, self).__init__(env)
        self._env = env
        self._config = Configuration()

        self._ridehailing_cars = []
        self._autonomous_cars = []
        self._distance_threshold_to_user = (
            self._config.ride_hailing_global.MAX_PICKUP_DISTANCE
        )
        self._driver_availability_vector = (
            self._config.ride_hailing_global.DRIVER_AVAILABILITY_VECTOR
        )
        self._recharging_threshold = self._config.ride_hailing_operators[
            0
        ].RECHARGE_THRESHOLD
        self._env.process(self.fleet_size_monitor())

    def _add_vehicle(self, vehicle: RideHailingVehicle):
        if vehicle not in self._vehicles:
            if isinstance(vehicle, RideHailingCar):
                self._vehicles.append(vehicle)
                self._ridehailing_cars.append(vehicle)
            elif isinstance(vehicle, RideHailingAV):
                self._vehicles.append(vehicle)
                self._autonomous_cars.append(vehicle)

            self._tracking.register(vehicle)
        else:
            raise Exception(f"Vehicle {vehicle} is already registered in Fleet")

    def vehicles_in_region(self, region):
        """
        Return all vehicles which are located in a region

        Example
        cars, scooters, kick_scooters, bikes = fleet.get_all_vehicles('871f1d4acffffff')

        :param region: Hexagon ID
        :return: Lists of vehicles in area
        """
        cars_in_area = []

        geo_env = GeodesicEnvironment.getInstance()
        Configuration()
        geometry = geo_env.get_hexagon(region)

        for car in self._vehicles:
            if car.position.is_in_geometry(geometry):
                cars_in_area.append(car)

        return cars_in_area

    def get_available_vehicles(self, region):
        """
        Return all vehicles which are located in a region

        Example
        cars, scooters, kick_scooters, bikes = fleet.get_all_vehicles('871f1d4acffffff')

        :param region: Hexagon ID
        :return: Lists of vehicles in area
        """
        cars_in_area = []

        parking_cars = [
            car for car in self._vehicles if car.state == VehicleState.PARKING
        ]
        for car in parking_cars:
            if car.position.get_hexagon_id() == region:
                cars_in_area.append(car)

        return cars_in_area

    def get_available_vehicles_to_user(self, origin):
        """
        Return all vehicles which are located in a region

        Example
        cars, scooters, kick_scooters, bikes = fleet.get_all_vehicles('871f1d4acffffff')

        :param region: Hexagon ID
        :return: Lists of vehicles in area
        """

        # TODO: this can be made faster by using np.array and boolean indexing probably
        parking_state = VehicleState.PARKING
        parking_cars = [
            car
            for car in self._vehicles
            if car.state == parking_state and not car._suggested
        ]
        parking_cars_in_area = (
            np.array(parking_cars)[
                haversine_vector(
                    [(c.position._lat, c.position._lng) for c in parking_cars],
                    [(origin._lat, origin._lng)],
                    comb=True,
                    unit=Unit.METERS,
                )[0]
                <= self._distance_threshold_to_user
            ]
            if parking_cars
            else np.array([])
        )

        serving_state = VehicleState.DRIVING
        hour = int((self._env.now % 1440 - self._env.now % 60) / 60)
        state_of_charge_threshold = self._recharging_threshold[hour]
        serving_cars = [
            car
            for car in self._vehicles
            if car.state == serving_state
            and not car._suggested
            and car.current_relative_state_of_charge > state_of_charge_threshold + 5
        ]

        serving_cars_in_area = []
        for car in serving_cars:
            distance_to_current_destination = (
                car.estimated_completion_time - self._env.now
            ) * car.velocity
            if (
                car.destination.position >> origin
            ) + distance_to_current_destination <= self._distance_threshold_to_user:
                serving_cars_in_area.append(car)

        return parking_cars_in_area.tolist() + serving_cars_in_area

    def get_all_available_vehicles(self, region):
        """
        Return all vehicles (mixed) in a list from passed region
        :param region: Spatial Region
        :return: List of all vehicle
        """

        cars = self.get_available_vehicles(region)

        all_vehicle_list = cars

        return all_vehicle_list

    def count_vehicles_below_soc_level(self, state_of_charge_threshold):
        """
        Return all vehicles that need to be refueled/recharged
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """
        hour = int((self._env.now % 1440 - self._env.now % 60) / 60)
        state_of_charge_threshold = state_of_charge_threshold[hour]
        return sum(
            1
            for vehicle in self._vehicles
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold
        )

    def get_operational_costs(self):
        operational_costs = 0
        all_vehicle_list = self._vehicles
        for vehicle in all_vehicle_list:
            if isinstance(vehicle, RideHailingAV):
                operational_costs += vehicle.travel_costs + vehicle.charging_costs
        return operational_costs

    def get_all_vehicles_below_soc_level_in_region(
        self, state_of_charge_threshold, region
    ):
        """
        Return all vehicles that need to be refueled/recharged in a region
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """
        below_soc_level_vehicles = []
        cars_in_area = self.vehicles_in_region(region)

        for vehicle in [*cars_in_area]:
            if vehicle.current_relative_state_of_charge < state_of_charge_threshold:
                below_soc_level_vehicles.append(vehicle)

        return below_soc_level_vehicles

    def count_cars(self):
        return len(self._vehicles)

    def driver_availability_vector(self):
        return self._driver_availability_vector

    def count_total(self):
        return self.count_cars()

    def calc_supply_per_region(self):
        """
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
                hex_id = vehicle.position.get_hexagon_id()

                if hex_id not in supply:
                    supply[hex_id] = dict(zip(available_vehicles, values))

                supply[hex_id][mode] += 1

        return supply

    def calc_vehicles_to_be_charged_per_region(self, state_of_charge_threshold):
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
                hex_id = vehicle.position.get_hexagon_id()

                if hex_id not in low_soc_supply:
                    low_soc_supply[hex_id] = dict(zip(available_vehicles, values))

                if vehicle.current_relative_state_of_charge < state_of_charge_threshold:
                    low_soc_supply[hex_id][mode] += 1

        return low_soc_supply

    def mark_vehicles_to_be_charged(self, state_of_charge_threshold):
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
        hour = int((self._env.now % 1440 - self._env.now % 60) / 60)
        state_of_charge_threshold = state_of_charge_threshold[hour]

        vehicle_list = self._vehicles

        for vehicle in vehicle_list:
            if (
                vehicle.current_relative_state_of_charge < state_of_charge_threshold
                and vehicle.state == VehicleState.PARKING
                and not vehicle._suggested
            ):
                low_soc_supply.append(vehicle)

        low_soc_supply = sorted(
            low_soc_supply, key=lambda x: x.current_relative_state_of_charge
        )
        return low_soc_supply

    def get_online_vehicles(self):
        """
        Return all vehicles which are online

        :param
        :return: Lists of online vehicles
        """

        online_vehicles = [
            car for car in self._ridehailing_cars if car.state != VehicleState.OFFLINE
        ]

        return online_vehicles

    def get_offline_vehicles(self):
        """
        Return all vehicles which are online

        :param
        :return: Lists of online vehicles
        """

        online_vehicles = [
            car for car in self._ridehailing_cars if car.state == VehicleState.OFFLINE
        ]

        return online_vehicles

    def fleet_size_monitor(self):
        """
        Monitoring the number of online vehicles
        :return:
        """
        while True:
            number_of_online_vehicles = len(self.get_online_vehicles())
            logging.info(
                f"Fleet has {number_of_online_vehicles} online vehicles",
                extra={"clazz": self.__class__.__name__},
            )
            yield self._env.timeout(60)
