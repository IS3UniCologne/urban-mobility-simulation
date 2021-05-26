from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.vehicle.shared_car import SharedCar
from simulation.vehicle.shared_kick_scooter import SharedKickScooter
from simulation.vehicle.shared_scooter import SharedScooter
from simulation.vehicle.shared_vehicle import SharedVehicle

class MixedSharedVehicleFleet:

    def __init__(self):
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
        else:
            self._bikes.append(vehicle)

    def get_vehicles_in_area(self, hexagon_id):
        """
        Return all vehicles which are located in a spatial unit

        Example
        cars, scooters, kick_scooters, bikes = fleet.get_vehicles_in_area('871f1d4acffffff')

        :param hexagon_id: Hexagon ID
        :return: Lists of vehicles in area
        """
        cars_in_area = []
        scooters_in_area = []
        kick_scooters_in_area = []
        bikes_in_area = []

        geo_env  = GeodesicEnvironment.getInstance()
        geometry = geo_env.get_hexagon(hexagon_id)

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

    def count_scooters(self):
        return len(self._scooters)

    def count_kick_scooters(self):
        return len(self._kick_scooters)

    def count_cars(self):
        return len(self._cars)

    def count_bikes(self):
        return len(self._bikes)

    def count_total(self):
        return self.count_cars()+self.count_bikes()+self.count_scooters()+self.count_kick_scooters()