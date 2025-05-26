from abc import ABC
from collections import defaultdict

import simpy

from simulation.helper.configuration.enums import VehicleMode, VehicleState
from simulation.vehicle.vehicle import Vehicle
from tracking.tracking import Tracking


class VehicleFleetError(Exception):
    """Base class for all vehicle fleet-related exceptions."""


class VehicleFleet(ABC):
    """Class representing a fleet of vehicles.

    Contains methods to manage and track vehicles within the fleet.
    """

    __slots__ = (
        "_env",
        "_id",
        "_resource",
        "_tracking",
        "_vehicles",
        "_vehicles_by_mode",
        "_vehicles_by_region",
        "_vehicles_by_state",
    )

    fleet_id: int = 0

    def __init__(self, env: simpy.Environment):  # noqa: ANN204
        self._id = VehicleFleet.fleet_id
        VehicleFleet.fleet_id += 1
        self._env: simpy.Environment = env
        self._vehicles: list[Vehicle] = []

        # Vehicle collections for faster access. We use sets for faster removals and intersections
        self._vehicles_by_mode: dict[VehicleMode, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_region: dict[str, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_state: dict[VehicleState, set[Vehicle]] = defaultdict(set)
        self._resource = simpy.Resource(env)  # Semaphore

        # tracking
        self._tracking: Tracking = Tracking.instance()

    @property
    def id(self) -> int:
        """Get the unique identifier of the vehicle fleet.

        Returns
        -------
        int
            The unique identifier of the vehicle fleet.

        """
        return self._id

    @property
    def resource(self) -> simpy.Resource:
        """SimPy Resource to handle parallel access.

        Returns
        -------
        simpy.Resource
            The SimPy resource used for managing access to the fleet.

        """
        return self._resource

    @property
    def vehicles(self) -> list[Vehicle]:
        """Gets all vehicles in the fleet.

        Returns
        -------
        list[Vehicle]
            A list of all Vehicle objects in the fleet.

        """
        return self._vehicles

    def parking_vehicles_in_region(self, region: str) -> set[Vehicle]:
        """Retrieve all vehicles currently in the PARKING state within the specified region.

        Parameters
        ----------
        region : str
            Region identifier (e.g., hexagon ID).

        Returns
        -------
            Set of vehicles located in the region and currently parking.
        """
        return self.vehicles_in_region_with_state(region, VehicleState.PARKING)

    def vehicles_in_region(self, region: str) -> set[Vehicle]:
        """Get all vehicles currently located in a specific region.

        Parameters
        ----------
        region : str
            Region identifier (e.g., hexagon ID).

        Returns
        -------
        set[Vehicle]
                Set of vehicles located in the specified region.
        """
        return self._vehicles_by_region[region]

    def vehicles_in_region_with_state(
        self, region: str, state: VehicleState
    ) -> set[Vehicle]:
        """Get vehicles in a specific region with a specific state.

        Parameters
        ----------
        region : str
            Region identifier (e.g., hexagon ID).
        state : VehicleState
            The state of the vehicle (e.g., PARKING, MOVING, etc.).

        Returns
        -------
        set[Vehicle]
            Set of vehicles located in the specified region with the specified state.
        """
        return self._vehicles_by_region[region].intersection(
            self._vehicles_by_state[state]
        )

    def register_vehicle(self, vehicle: Vehicle) -> None:
        """Register a new vehicle to the fleet."""
        if vehicle in self._vehicles:
            raise VehicleFleetError(f"Vehicle {vehicle} is already registered in Fleet")
        else:
            self._add_vehicle(vehicle)
            self._vehicles_by_state[vehicle.state].add(vehicle)
            self._vehicles_by_region[vehicle.current_region].add(vehicle)
            self._vehicles_by_mode[vehicle.mode].add(vehicle)

    def _add_vehicle(self, vehicle: Vehicle) -> None:
        """Add a vehicle to the fleet.

        This is used internally and should not be called from outside.
        Use register_vehicle instead.

        Parameters
        ----------
        vehicle : Vehicle
            The vehicle to be added to the fleet.
        """
        self._vehicles.append(vehicle)

    def remove_vehicle(self, vehicle: Vehicle) -> None:
        """Remove a vehicle from the fleet."""
        if vehicle in self._vehicles:
            self._vehicles.remove(vehicle)
        else:
            raise VehicleFleetError(f"Vehicle {vehicle} is not registered in Fleet yet")

    def update_vehicle_state(self, vehicle: Vehicle, new_state: VehicleState) -> None:
        """Update the state of a vehicle in the fleet.

        This is used when a vehicle's state changes (e.g., from PARKING to MOVING).

        Parameters
        ----------
        vehicle : Vehicle
            The vehicle whose state is being updated.
        new_state : VehicleState
            The new state of the vehicle (e.g., PARKING, MOVING, etc.).

        If this throws an exception, the vehicle state is probably being
        incorrectly set through the private attribute
        """
        self._vehicles_by_state[vehicle.state].remove(vehicle)
        self._vehicles_by_state[new_state].add(vehicle)

    def update_vehicle_region(self, vehicle: Vehicle, new_region_id: str) -> None:
        """Update the region of a vehicle in the fleet.

        This is used when a vehicle moves from one region to another.

        Parameters
        ----------
        vehicle : Vehicle
            The vehicle whose region is being updated.
        new_region_id : str
            The new region identifier (e.g., hexagon ID).
        """
        # Remove vehicle from old hexagon
        self._vehicles_by_region[vehicle.current_region].remove(vehicle)

        # Add vehicle to new hexagon's set
        self._vehicles_by_region[new_region_id].add(vehicle)

    def get_vehicles_in_region(self, region: str) -> list[Vehicle]:
        """Return all vehicles in a passed region.

        Parameters
        ----------
        region : str
            Spatial Region identifier.

        Returns
        -------
        list
            List of all vehicles in the region.
        """
        return list(self._vehicles_by_region[region])
