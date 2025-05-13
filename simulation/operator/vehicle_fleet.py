from abc import ABC
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

    fleet_id: int = 0

    def __init__(self, env: simpy.Environment):
        self._id = VehicleFleet.fleet_id
        VehicleFleet.fleet_id += 1
        self._env: simpy.Environment = env
        self._vehicles: list[Vehicle] = []

        # Vehicle collections for faster access. We use sets for faster removals and intersections
        self._vehicles_by_mode: dict[VehicleMode, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_region: dict[str, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_state: dict[int, set[Vehicle]] = defaultdict(set)
        self._resource = simpy.Resource(env)  # Semaphore

        # tracking
        self._tracking: Tracking = Tracking.instance()

    @property
    def id(self) -> int:
        """Get the unique identifier of the vehicle fleet.

        Returns:
            int: The unique identifier assigned to this vehicle fleet.

        """
        return self._id

    @property
    def resource(self) -> simpy.Resource:
        """SimPy Resource to handle parallel access.

        Returns:
            simpy.Resource: The SimPy resource used for managing access to the fleet.

        """
        return self._resource

    @property
    def vehicles(self) -> list[Vehicle]:
        """Gets all vehicles in the fleet.

        Returns:
            list[Vehicle]: A list of all Vehicle objects in the fleet.

        """
        return self._vehicles

    def parking_vehicles_in_region(self, region: str) -> set[Vehicle]:
        """Retrieve all vehicles that are currently in the PARKING state within a specified region.

        Args:
            region: The region identifier (e.g., hexagon ID) to search for vehicles.

        Returns:
            set[Vehicle]: A set of Vehicle objects that are both located in the specified region
                  and currently in the PARKING state.

        """
        # Use set intersection
        parking_vehicles_in_region = self._vehicles_by_region[region].intersection(
            self._vehicles_by_state[VehicleState.PARKING]
        )

        return parking_vehicles_in_region

    def vehicles_in_region(self, region: str) -> set[Vehicle]:
        """Get all vehicles currently located in a specific region.

        Args:
        region : str
            The region identifier.

        Returns:
        set[Vehicle]
            A set of Vehicle objects that are currently in the specified region.

        """
        return self._vehicles_by_region[region]

    def register_vehicle(self, vehicle: Vehicle):
        if vehicle in self._vehicles:
            raise Exception(f"Vehicle {vehicle} is already registered in Fleet")
        else:
            self._add_vehicle(vehicle)
            self._vehicles_by_state[vehicle.state].add(vehicle)
            self._vehicles_by_region[vehicle.current_region].add(vehicle)
            self._vehicles_by_mode[vehicle.mode].add(vehicle)

    def _add_vehicle(self, vehicle: Vehicle):
        """Add a vehicle to the fleet. This is used internally and should not be called from outside."""
        self._vehicles.append(vehicle)

    def remove_vehicle(self, vehicle: Vehicle):
        if vehicle in self._vehicles:
            self._vehicles.remove(vehicle)
        else:
            raise Exception(f"Vehicle {vehicle} is not registered in Fleet yet")

    def update_vehicle_state(self, vehicle: Vehicle, new_state: VehicleState):
        """Update the state of a vehicle in the fleet."""
        # If this throws an exception, the vehicle state is probably being
        # incorrectly set through the private attribute
        self._vehicles_by_state[vehicle.state].remove(vehicle)
        self._vehicles_by_state[new_state].add(vehicle)

    def update_vehicle_region(self, vehicle: Vehicle, new_region_id: str):
        """Update the position of a vehicle in the fleet."""
        # Remove vehicle from old hexagon
        self._vehicles_by_region[vehicle.current_region].remove(vehicle)

        # Add vehicle to new hexagon's set
        self._vehicles_by_region[new_region_id].add(vehicle)

    def get_vehicles_in_region(self, region):
        """Return all vehicles (mixed) in a list from passed region
        :param region: Spatial Region
        :return: List of all vehicle
        """
        return list(self._vehicles_by_region[region])
