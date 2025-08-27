from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import simpy

from simulation.helper.configuration.enums import VehicleState, VehicleType
from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import FleetConfig
    from simulation.operator.interface.operator_interface import OperatorInterface
    from simulation.vehicle.vehicle import Vehicle
    from simulation.world.world import World


class VehicleFleetError(Exception):
    """Base class for all vehicle fleet-related exceptions."""


@dataclass(frozen=True, slots=True)
class VehicleFleetDependencies:
    """Dependencies required for the VehicleFleet.

    This class ensures all subclasses maintain the same init signature.

    Parameters
    ----------
    operator : OperatorInterface
        The operator managing the vehicle fleet.
    sim : SimulationContext
        The simulation context.
    world : World
        The world instance.
    config : FleetConfig
        The fleet configuration.
    """

    operator: OperatorInterface
    sim: SimulationContext
    world: World
    config: FleetConfig


class VehicleFleet(SimulationBase):
    """Class representing a fleet of vehicles.

    Contains methods to manage and track vehicles within the fleet.
    """

    __slots__ = (
        "_config",
        "_operator",
        "_resource",
        "_sim",
        "_vehicles",
        "_vehicles_by_region",
        "_vehicles_by_state",
        "_vehicles_by_type",
        "_world",
    )

    def __init__(self, deps: VehicleFleetDependencies) -> None:
        super().__init__(deps.sim)

        self._sim = deps.sim
        self._operator = deps.operator
        self._world = deps.world
        self._config = deps.config

        self._vehicles: list[Vehicle] = []

        # Vehicle collections for faster access. We use sets for faster removals and intersections
        self._vehicles_by_type: dict[VehicleType, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_region: dict[str, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_state: dict[VehicleState, set[Vehicle]] = defaultdict(set)
        self._resource = simpy.Resource(deps.sim.env)  # Semaphore

    @classmethod
    def from_deps(cls, deps: VehicleFleetDependencies) -> VehicleFleet:
        fleet_type = deps.config.FLEET_TYPE
        return fleet_type(deps)

    @property
    def config(self) -> FleetConfig:
        """Get the fleet configuration.

        Returns
        -------
        FleetConfig
            The fleet configuration.

        """
        return self._config

    @property
    def operator(self) -> OperatorInterface:
        """Get the operator managing the vehicle fleet.

        Returns
        -------
        OperatorInterface
            The operator managing the vehicle fleet.

        """
        return self._operator

    @property
    def vehicle_types(self) -> list[VehicleType]:
        """Get all unique vehicle types in the fleet.

        Returns
        -------
        list[VehicleType]
            A list of all unique VehicleType enums available in the fleet.
        """
        return list(self._vehicles_by_type.keys())

    @property
    def count_by_type(self) -> dict[VehicleType, int]:
        """Get the count of vehicles by type.

        Returns
        -------
        dict[VehicleType, int]
            A dictionary mapping each VehicleType to the number of vehicles in that type.

        """
        return {
            type_: len(vehicles) for type_, vehicles in self._vehicles_by_type.items()
        }

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

    @property
    def vehicles_by_state(self) -> dict[VehicleState, set[Vehicle]]:
        return self._vehicles_by_state

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

    def vehicles_of_type(self, type: VehicleType) -> set[Vehicle]:
        """Get all vehicles currently in a specific type.

        Parameters
        ----------
        type : VehicleType
            The type of the vehicle (e.g., CAR, SCOOTER, etc.).

        Returns
        -------
        set[Vehicle]
            Set of vehicles currently in the specified type.
        """
        return self._vehicles_by_type[type]

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
            self._vehicles_by_type[vehicle.vehicle_type].add(vehicle)

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
        self._world.add_vehicle(vehicle)

    def remove_vehicle(self, vehicle: Vehicle) -> None:
        """Remove a vehicle from the fleet."""
        if vehicle in self._vehicles:
            self._vehicles.remove(vehicle)
            self._world.remove_vehicle(vehicle)
            # Remove from all tracking collections
            self._vehicles_by_state[vehicle.state].remove(vehicle)
            self._vehicles_by_region[vehicle.current_region].remove(vehicle)
            self._vehicles_by_type[vehicle.vehicle_type].remove(vehicle)
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
