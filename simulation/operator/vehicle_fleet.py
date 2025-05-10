from abc import ABC, abstractmethod
from collections import defaultdict

import simpy

from simulation.helper.configuration.enums import VehicleMode
from simulation.vehicle.vehicle import Vehicle, VehicleState
from tracking.tracking import Tracking


class VehicleFleet(ABC):
    __slots__ = (
        "_id",
        "_env",
        "_vehicles",
        "_resource",
        "_tracking",
        "_vehicles_by_mode",
        "_vehicles_by_state",
        "_vehicles_by_region",
    )

    fleet_id = 0

    def __init__(self, env: simpy.Environment):
        self._id = VehicleFleet.fleet_id
        VehicleFleet.fleet_id += 1
        self._env = env
        self._vehicles = []

        # Vehicle collections for faster access. We use sets for faster removals and intersections
        self._vehicles_by_mode: dict[VehicleMode, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_region: dict[str, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_state: dict[int, set[Vehicle]] = defaultdict(set)
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
        return self._vehicles

    def parking_vehicles_in_region(self, region) -> set[Vehicle]:
        """
        Return all parking vehicles which are located in a region

        Example
        cars, scooters, kick_scooters, bikes = fleet.get_all_vehicles('871f1d4acffffff')

        :param region: Hexagon ID
        :return: Lists of vehicles in area
        """

        # Use set intersection
        parking_vehicles_in_region = self._vehicles_by_region[region].intersection(
            self._vehicles_by_state[VehicleState.PARKING]
        )

        return parking_vehicles_in_region

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
            self._vehicles_by_region[vehicle.current_region].add(vehicle)
            self._vehicles_by_mode[vehicle.mode].add(vehicle)

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

    def update_vehicle_region(self, vehicle: Vehicle, new_region_id: str):
        """
        Update the position of a vehicle in the fleet.
        """

        # Remove vehicle from old hexagon
        self._vehicles_by_region[vehicle.current_region].remove(vehicle)

        # Add vehicle to new hexagon's set
        self._vehicles_by_region[new_region_id].add(vehicle)

    def get_vehicles_in_region(self, region):
        """
        Return all vehicles (mixed) in a list from passed region
        :param region: Spatial Region
        :return: List of all vehicle
        """

        return list(self._vehicles_by_region[region])
