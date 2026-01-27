from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd
import simpy

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.enums import AutonomyType, VehicleType
from simulation.helper.exceptions import VehicleFleetError
from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import FleetConfig, VehicleConfig
    from simulation.helper.types import RegionId
    from simulation.helper.vehicle_states import VehicleState
    from simulation.operator.interface.operator_interface import OperatorInterface
    from simulation.vehicle.vehicle import Vehicle
    from simulation.world.world import World


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


class VehicleFleet(SimulationBase, ABC):
    """Class representing a fleet of vehicles.

    Contains methods to manage and track vehicles within the fleet.
    """

    __slots__ = (
        "_config",
        "_operator",
        "_resource",
        "_sim",
        "_vehicles",
        "_vehicles_by_autonomy",
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
        self._vehicles_by_region: dict[RegionId, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_state: dict[VehicleState, set[Vehicle]] = defaultdict(set)
        self._vehicles_by_autonomy: dict[AutonomyType, set[Vehicle]] = defaultdict(set)
        self._resource = simpy.Resource(deps.sim.env)  # Semaphore

    def _create_fleet_vehicles(self, deps: VehicleFleetDependencies) -> None:
        """Create fleet vehicles using spatial distribution from supply data."""
        rng = deps.sim.random_manager.get_rng(component_name="FLEETFACTORY")
        hex_columns = deps.sim.config.world.SPATIAL_RESOLUTION.column_name

        supply_path = deps.sim.config.path.PATH_VEHICLE_SUPPLY
        supply_probabilities = pd.read_csv(supply_path)

        # TODO: This mapping should come from configuration
        vehicle_type_to_prob_column = {
            VehicleType.CAR: "cars_prob",
            VehicleType.BIKE: "bikes_prob",
            VehicleType.SCOOTER: "scooters_prob",
            VehicleType.KICK_SCOOTER: "kick_scooters_prob",
        }

        for vehicle_config, total_count in deps.config.VEHICLES.items():
            prob_column = vehicle_type_to_prob_column.get(vehicle_config.VEHICLE_TYPE)

            if prob_column is None:
                self.logger.error(
                    "Fleet does not support vehicle type %s",
                    vehicle_config.VEHICLE_TYPE,
                )
                continue

            vehicle_probabilities = supply_probabilities[prob_column].to_numpy()

            # Sample vehicle distribution based on probabilities
            vehicle_count = pd.DataFrame(
                rng.multinomial(
                    n=total_count, pvals=vehicle_probabilities, size=1
                ).transpose(),
                columns=["count"],
            )
            vehicle_count.index = supply_probabilities.index
            supply_probabilities["count"] = vehicle_count["count"]

            # Create vehicles in their assigned regions
            for _index, row in supply_probabilities.iterrows():
                hex_id = row[hex_columns]
                local_count = row["count"]
                for _ in range(local_count):
                    rdm_lat, rdm_lng = deps.sim.geo_env.get_random_position(hex_id)
                    pos = GeodesicPosition(deps.sim, rdm_lat, rdm_lng, hex_id)

                    # Call subclass-specific vehicle creation
                    self._create_vehicle(deps, pos, vehicle_config)

    @abstractmethod
    def _create_vehicle(
        self,
        deps: VehicleFleetDependencies,
        position: GeodesicPosition,
        vehicle_config: VehicleConfig,
    ) -> None:
        """Create a vehicle instance."""
        pass

    @staticmethod
    def from_deps(deps: VehicleFleetDependencies) -> VehicleFleet:  # noqa: D102
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
        """Get vehicles grouped by state.

        Supports hierarchical state queries - vehicles are indexed by both their
        current leaf state and all ancestor states. This enables O(1) queries at
        any hierarchy level.

        Returns
        -------
        dict[VehicleState, set[Vehicle]]
            Dictionary mapping states to sets of vehicles. Includes entries for:
            - Leaf states (e.g., PICK_UP, TRANSPORTING)
            - Parent states (e.g., SERVING_PASSENGERS, IN_USE)
        """
        return self._vehicles_by_state

    @property
    def vehicles_by_autonomy(self) -> dict[AutonomyType, set[Vehicle]]:  # noqa: D102
        return self._vehicles_by_autonomy

    def region_vehicle_distribution(self) -> dict[RegionId, int]:
        """Get vehicle count per region (hex ID).

        Returns
        -------
        dict[RegionId, int]
            Mapping of region (hexagon ID) to number of vehicles currently located there.
        """
        return {
            region: len(vehicles)
            for region, vehicles in self._vehicles_by_region.items()
        }

    def vehicles_in_region(self, region: RegionId) -> set[Vehicle]:
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
        self, region: RegionId, state: VehicleState
    ) -> set[Vehicle]:
        """Get vehicles in a specific region with a specific state.

        Supports hierarchical state queries - passing a parent state will return
        all vehicles in any child state.

        Parameters
        ----------
        region : RegionId
            Region identifier (e.g., hexagon ID).
        state : VehicleState
            The state to query (e.g., IDLE, SERVING_PASSENGERS, IN_USE).
            Can be a leaf state or parent state in the hierarchy.

        Returns
        -------
        set[Vehicle]
            Set of vehicles located in the specified region with the specified state
            or any of its child states.
        """
        return self._vehicles_by_region[region].intersection(
            self._vehicles_by_state[state]
        )

    def vehicles_below_energy_threshold(self, energy_threshold: float) -> set[Vehicle]:
        """Return all vehicles that need to be refueled/recharged.

        Parameters
        ----------
        energy_threshold : float
            Threshold value between 0 and 1

        Returns
        -------
        set[Vehicle]
            Set of vehicles with energy level below the threshold
        """
        return {
            vehicle
            for vehicle in self.vehicles
            if vehicle.energy_system.current_energy_relative < energy_threshold
        }

    def vehicles_below_energy_threshold_in_region(
        self, energy_threshold: float, region: RegionId
    ) -> list[Vehicle]:
        """Return all vehicles that need to be refueled/recharged in a region.

        Parameters
        ----------
        energy_threshold : float
            Threshold value between 0 and 1
        region : RegionId
            Region identifier (e.g., hexagon ID)

        Returns
        -------
        list[Vehicle]
            List of vehicles in the region with energy level below the threshold
        """
        below_energy_level_vehicles = []
        vehicles_in_region = self.vehicles_in_region(region)
        # TODO: Check if this is necessary
        vehicles_in_region_sorted = sorted(vehicles_in_region, key=lambda v: v.uid)

        for vehicle in vehicles_in_region_sorted:
            if vehicle.energy_system.current_energy_relative < energy_threshold:
                below_energy_level_vehicles.append(vehicle)

        return below_energy_level_vehicles

    def register_vehicle(self, vehicle: Vehicle) -> None:
        """Register a new vehicle to the fleet."""
        if vehicle in self._vehicles:
            raise VehicleFleetError(f"Vehicle {vehicle} is already registered in Fleet")
        else:
            self._add_vehicle(vehicle)
            self._vehicles_by_state[vehicle.state].add(vehicle)
            for ancestor in vehicle.state.get_ancestors():
                self._vehicles_by_state[ancestor].add(vehicle)
            self._vehicles_by_region[vehicle.current_region].add(vehicle)
            self._vehicles_by_type[vehicle.vehicle_type].add(vehicle)
            self._vehicles_by_autonomy[vehicle.autonomy_type].add(vehicle)

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
            self._vehicles_by_state[vehicle.state].remove(vehicle)
            for ancestor in vehicle.state.get_ancestors():
                self._vehicles_by_state[ancestor].remove(vehicle)
            self._vehicles_by_region[vehicle.current_region].remove(vehicle)
            self._vehicles_by_type[vehicle.vehicle_type].remove(vehicle)
            self._vehicles_by_autonomy[vehicle.autonomy_type].remove(vehicle)
        else:
            raise VehicleFleetError(f"Vehicle {vehicle} is not registered in Fleet yet")

    def update_vehicle_state(
        self, vehicle: Vehicle, old_state: VehicleState, new_state: VehicleState
    ) -> None:
        """Update the state of a vehicle in the fleet.

        This is used when a vehicle's state changes (e.g., from IDLE to PICK_UP).

        Updates both the leaf state and all ancestor states in the hierarchy.

        Parameters
        ----------
        vehicle : Vehicle
            The vehicle whose state is being updated.
        old_state : VehicleState
            The old state of the vehicle.
        new_state : VehicleState
            The new state of the vehicle (e.g., IDLE, PICK_UP, etc.).

        If this throws an exception, the vehicle state is probably being
        incorrectly set through the private attribute
        """
        # Remove from old state and all its ancestors
        self._vehicles_by_state[old_state].remove(vehicle)
        for ancestor in old_state.get_ancestors():
            self._vehicles_by_state[ancestor].remove(vehicle)

        # Add to new state and all its ancestors
        self._vehicles_by_state[new_state].add(vehicle)
        for ancestor in new_state.get_ancestors():
            self._vehicles_by_state[ancestor].add(vehicle)

    def update_vehicle_region(self, vehicle: Vehicle, new_region_id: RegionId) -> None:
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
