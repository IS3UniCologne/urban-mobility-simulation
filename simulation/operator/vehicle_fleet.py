from abc import ABC, abstractmethod

import simpy

from simulation.vehicle.vehicle import Vehicle
from tracking.tracking import Tracking


class VehicleFleet(ABC):
    __slots__ = ("_id", "_env", "_vehicles", "_resource", "_tracking")

    fleet_id = 0

    def __init__(self, env: simpy.Environment):
        self._id = VehicleFleet.fleet_id
        VehicleFleet.fleet_id += 1
        self._env = env
        self._vehicles = []
        self._resource = simpy.Resource(env)  # Semaphore

        # tracking
        self._tracking = Tracking.instance()

    @property
    def id(self):
        return self._id

    @property
    def resource(self):
        """
        SimPy Resource to handle parallel access
        :return:
        """
        return self._resource

    @property
    def vehicles(self):
        # TODO: most probably Unfug
        return (
            self._vehicles.copy()
        )  # to avoid that the fleet can be changed from outside

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
            raise Exception(f"Vehicle {vehicle} is already registered in Fleet")

    def remove_vehicle(self, vehicle: Vehicle):
        if vehicle in self._vehicles:
            self._vehicles.remove(vehicle)
        else:
            raise Exception(f"Vehicle {vehicle} is not registered in Fleet yet")
