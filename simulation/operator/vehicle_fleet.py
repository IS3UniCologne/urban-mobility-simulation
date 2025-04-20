from abc import ABC, abstractmethod
from collections import defaultdict

import simpy

from simulation.vehicle.vehicle import Vehicle, VehicleState
from tracking.tracking import Tracking


class VehicleFleet(ABC):
    __slots__ = (
        "_id",
        "_env",
        "_vehicles",
        "_resource",
        "_tracking",
        "_vehicles_by_state",
    )

    fleet_id = 0

    def __init__(self, env: simpy.Environment):
        self._id = VehicleFleet.fleet_id
        VehicleFleet.fleet_id += 1
        self._env = env
        self._vehicles = []
        # self._vehicles_by_type = defaultdict(set) #maybe this can be a list instead of a set
        # # Not sure if we want this one. We could have it only update when vehicles stop moving to make it very efficient
        # self._vehicles_by_region = defaultdict(set)
        self._vehicles_by_state = defaultdict(set)
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

    def register_vehicle(self, vehicle: Vehicle):
        if vehicle in self._vehicles:
            raise Exception(f"Vehicle {vehicle} is already registered in Fleet")
        else:
            self._add_vehicle(vehicle)
            self._vehicles_by_state[vehicle.state].add(vehicle)

    def _add_vehicle(self, vehicle: Vehicle):
        """
        Add a vehicle to the fleet. This is used internally and should not be called from outside.
        """
        self._vehicles.append(vehicle)

    def remove_vehicle(self, vehicle: Vehicle):
        if vehicle in self._vehicles:
            self._vehicles.remove(vehicle)
        else:
            raise Exception(f"Vehicle {vehicle} is not registered in Fleet yet")

    def update_vehicle_state(self, vehicle: Vehicle, new_state: VehicleState):
        """
        Update the state of a vehicle in the fleet.
        """
        # If this throws an exception, the vehicle state is probably being
        # incorrectly set through the private attribute
        self._vehicles_by_state[vehicle.state].remove(vehicle)
        self._vehicles_by_state[new_state].add(vehicle)
