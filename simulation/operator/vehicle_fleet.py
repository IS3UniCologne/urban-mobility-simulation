from abc import ABC, abstractmethod
from simulation.vehicle.vehicle import Vehicle


class VehicleFleet(ABC):

    def __init__(self, env, capacity):
        self._fleet_capacity = capacity
        self._vehicles = []

    @property
    def vehicles(self):
        # TODO: most probably Unfug
        return self._vehicles.copy() # to avoid that the fleet can be changed from outside

    @abstractmethod
    def get_available_vehicles(self, region):
        pass

    # TODO: implement sane return type (vehicle collection?)
    @abstractmethod
    def vehicles_in_region(self, region: str):
        pass

    def add_vehicle(self, vehicle: Vehicle):
        if vehicle not in self._vehicles:
            self._vehicles.append(vehicle)
        else:
            raise Exception(f'Vehicle {vehicle} is already registered in Fleet')

    def remove_vehicle(self, vehicle: Vehicle):
        if vehicle in self._vehicles:
            self._vehicles.remove(vehicle)
        else:
            raise Exception(f'Vehicle {vehicle} is not registered in Fleet yet')