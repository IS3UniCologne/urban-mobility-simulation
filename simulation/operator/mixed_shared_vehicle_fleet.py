from simpy import Environment

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import Configuration
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.vehicle.shared_bike import SharedBike
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.vehicle.shared_vehicle import SharedVehicle
from simulation.vehicle.vehicle import VehicleState


class MixedSharedVehicleFleet(VehicleFleet):

    __slots__ = (
        "_scooters",
        "_kick_scooters", "_cars",
        "_bikes",)
    
    def __init__(self, env: Environment):
        super(MixedSharedVehicleFleet, self).__init__(env)

        self._scooters = []
        self._kick_scooters = []
        self._cars = []
        self._bikes = []

    def add_shared_vehicle(self, vehicle: SharedVehicle):
        if isinstance(vehicle, SharedCar):
            self._cars.append(vehicle)
        elif isinstance(vehicle, SharedScooter):
            self._scooters.append(vehicle)
        elif isinstance(vehicle, SharedKickScooter):
            self._kick_scooters.append(vehicle)
        elif isinstance(vehicle, SharedBike):
            self._bikes.append(vehicle)
        else:
            raise Exception("Unknown Vehicle type", type(vehicle))

        self._vehicles.append(vehicle)

    def vehicles_in_region(self, region):
        """
        Return all vehicles which are located in a region

        Example
        cars, scooters, kick_scooters, bikes = fleet.get_all_vehicles('871f1d4acffffff')

        :param region: Hexagon ID
        :return: Lists of vehicles in area
        """
        cars_in_area = []
        scooters_in_area = []
        kick_scooters_in_area = []
        bikes_in_area = []

        geo_env = GeodesicEnvironment.getInstance()
        Configuration()
        geometry = geo_env.get_hexagon(region)

        for car in self._cars:
            if car.position.is_in_geometry(geometry):
                cars_in_area.append(car)

        for scooter in self._scooters:
            if scooter.position.is_in_geometry(geometry):
                scooters_in_area.append(scooter)

        for kick_scooter in self._kick_scooters:
            if kick_scooter.position.is_in_geometry(geometry):
                kick_scooters_in_area.append(kick_scooter)

        for bike in self._bikes:
            if bike.position.is_in_geometry(geometry):
                bikes_in_area.append(bike)

        return cars_in_area, scooters_in_area, kick_scooters_in_area, bikes_in_area

    def get_available_vehicles(self, region):
        """
        Return all vehicles which are located in a region

        Example
        cars, scooters, kick_scooters, bikes = fleet.get_all_vehicles('871f1d4acffffff')

        :param region: Hexagon ID
        :return: Lists of vehicles in area
        """
        cars_in_area = []
        scooters_in_area = []
        kick_scooters_in_area = []
        bikes_in_area = []

        # geo_env = GeodesicEnvironment.getInstance()
        # geometry = geo_env.get_hexagon(region)

        for car in self._cars:
            if (
                car.position.get_hexagon_id() == region
                and car.state == VehicleState.PARKING
            ):
                cars_in_area.append(car)

        for scooter in self._scooters:
            if (
                scooter.position.get_hexagon_id() == region
                and scooter.state == VehicleState.PARKING
            ):
                scooters_in_area.append(scooter)

        for kick_scooter in self._kick_scooters:
            if (
                kick_scooter.position.get_hexagon_id() == region
                and kick_scooter.state == VehicleState.PARKING
            ):
                kick_scooters_in_area.append(kick_scooter)

        for bike in self._bikes:
            if (
                bike.position.get_hexagon_id() == region
                and bike.state == VehicleState.PARKING
            ):
                bikes_in_area.append(bike)

        return cars_in_area, scooters_in_area, kick_scooters_in_area, bikes_in_area

    def get_all_available_vehicles(self, region):
        """
        Return all vehicles (mixed) in a list from passed region
        :param region: Spatial Region
        :return: List of all vehicle
        """

        cars, scooters, kick_scooters, bikes = self.get_available_vehicles(region)

        all_vehicle_list = cars + scooters + kick_scooters + bikes

        return all_vehicle_list

    def get_all_vehicles_below_soc_level(self, state_of_charge_threshold):
        """
        Return all vehicles that need to be refueled/recharged
        :param state_of_charge_threshold: between 0 and 1
        :return: Vehicle list in which all vehicles soc < state_of_charge_threshold
        """
        below_soc_level_vehicles = []
        all_vehicle_list = (
            self._cars + self._scooters + self._kick_scooters + self._bikes
        )

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

    def count_scooters(self):
        return len(self._scooters)

    def count_kick_scooters(self):
        return len(self._kick_scooters)

    def count_cars(self):
        return len(self._cars)

    def count_bikes(self):
        return len(self._bikes)

    def count_total(self):
        return (
            self.count_cars()
            + self.count_bikes()
            + self.count_scooters()
            + self.count_kick_scooters()
        )

    def calc_supply_per_region(self):
        """
        Return a list of number of vehicles in each region
        :return: Dictionary, where key = hex_id and value is a dictionary with mode and count values
                e.g., {"H1212j1": {"SharedKickScooters": 0, "SharedScooters": 1, "SharedCars": 2}, "h12h1j2": ...}
        """
        available_vehicles = [
            "SharedKickScooter",
            "SharedScooter",
            "SharedCar",
            "SharedBike",
        ]
        values = [0] * len(available_vehicles)

        # Set counter to 0 for all vehicle types
        # vehicle_dict = dict(zip(available_vehicles, values))

        supply = {}

        for mode in available_vehicles:
            if mode == "SharedKickScooter":
                vehicle_list = self._kick_scooters
            elif mode == "SharedScooter":
                vehicle_list = self._scooters
            elif mode == "SharedCar":
                vehicle_list = self._cars
            elif mode == "SharedBike":
                vehicle_list = self._bikes
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
        available_vehicles = [
            "SharedKickScooter",
            "SharedScooter",
            "SharedCar",
            "SharedBike",
        ]
        values = [0] * len(available_vehicles)

        # Set counter to 0 for all vehicle types
        # vehicle_dict = dict(zip(available_vehicles, values))

        low_soc_supply = {}

        for mode in available_vehicles:
            if mode == "SharedKickScooter":
                vehicle_list = self._kick_scooters
            elif mode == "SharedScooter":
                vehicle_list = self._scooters
            elif mode == "SharedCar":
                vehicle_list = self._cars
            elif mode == "SharedBike":
                vehicle_list = self._bikes
            else:
                raise NotImplementedError(f"Fleet Not Ready to Work with {mode}")

            for vehicle in vehicle_list:
                hex_id = vehicle.position.get_hexagon_id()

                if hex_id not in low_soc_supply:
                    low_soc_supply[hex_id] = dict(zip(available_vehicles, values))

                if vehicle.current_relative_state_of_charge < state_of_charge_threshold:
                    low_soc_supply[hex_id][mode] += 1

        return low_soc_supply
