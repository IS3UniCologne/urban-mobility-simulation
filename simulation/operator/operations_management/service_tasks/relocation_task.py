from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import VehicleState, VehicleType
from simulation.infrastructure.network.edge import Edge
from simulation.infrastructure.network.vertex import Vertex
from simulation.operator.operations_management.service_tasks.service_task import (
    ServiceTask,
)

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.vehicle_fleet import VehicleFleet


class RelocationTask(ServiceTask):
    __slots__ = (
        "_config",
        "_destination",
        "_distance",
        "_geo_env",
        "_number_of_vehicles_to_relocate",
        "_origin",
        "_vehicle_fleet",
        "_vehicle_type",
        "destination",
    )

    def __init__(
        self,
        sim: SimulationContext,
        origin: GeodesicPosition,
        destination: GeodesicPosition,
        number_of_vehicles_to_relocate: int,
        distance: float,
        vehicle_type: VehicleType,
        vehicle_fleet: VehicleFleet,
    ) -> None:
        super().__init__(sim)

        self._sim = sim
        self._config = sim.config
        self._geo_env = sim.geo_env

        self._origin = origin
        self._destination = destination
        self._number_of_vehicles_to_relocate = number_of_vehicles_to_relocate
        self._vehicle_type = vehicle_type

        self._vehicle_fleet = vehicle_fleet
        self._distance = distance

    def execute(self, *args):  # noqa: ANN002, ANN201
        # Get Spatial Environment

        with self._vehicle_fleet.resource.request() as req:
            """Multiple Service Workers (within same hexagon) cannot access the vehicle list in parallel"""
            # We mark vehilces which are already scheduled using (prepare_for_service_task) in a thread safe way
            yield req

            # Identify vehicles to relocate
            potential_vehicles_to_relocate = self._vehicle_fleet.vehicles_in_region(
                self._origin
            )
            # TODO: Make sure this is necessary
            potential_vehicles_sorted = sorted(
                potential_vehicles_to_relocate, key=lambda v: v.uid
            )
            selected_vehicles_to_relocate = []

            # Filter relevant vehicles
            for vehicle in potential_vehicles_sorted:
                # Filter by vehicle type and only parking vehicles (possibly some vehicles are driving around with low soc)
                if (
                    vehicle.vehicle_type == self._vehicle_type
                    and vehicle.state == VehicleState.PARKING
                ):
                    # Mark Vehicle => Change state su
                    # ch that other service workers don't touch it!!
                    vehicle.prepare_for_service_task(
                        f"Service Worker {args[0]}", self.__class__.__name__
                    )
                    # Add to charging list
                    selected_vehicles_to_relocate.append(vehicle)
                    if (
                        len(selected_vehicles_to_relocate)
                        >= self._number_of_vehicles_to_relocate
                    ):
                        # leave the loop if we have enough vehicles
                        break
        # Start Relocation Process
        for vehicle in selected_vehicles_to_relocate:
            # Random Destination at Dest Region
            lat, lng = self._geo_env.get_random_position(self._destination)
            vehicle_dest = GeodesicPosition(self._sim, lat, lng, self._destination)

            # Relocation Route
            relocation_route = Edge(
                self._distance, Vertex(vehicle.position), Vertex(vehicle_dest)
            )

            # Calculate Relocation Cost based on distance, relocation velocity and number of vehicles to relocate.
            # As in the charging task, we linearize the relocation task if multiple vehicles need to be relocated.
            # Thus, we ensure that the total relocation cost corresponds to the parallel case.
            vehicle_relocation_velocity = self._config.operators[
                0
            ].OPERATIONS_CONFIG.VEHICLE_RELOCATION_VELOCITY
            relocation_duration_per_vehicle = (
                relocation_route.distance / vehicle_relocation_velocity
            ) / len(selected_vehicles_to_relocate)

            yield self._env.process(
                vehicle.relocate(
                    relocation_route,
                    relocation_duration_per_vehicle,
                    f"Service Worker {args[0]}",
                )
            )

        # Notify all
        self._task_finished.succeed()

        # Notify all
        self._task_finished = self._env.event()

    def __str__(self) -> str:
        return f"Relocating {self._number_of_vehicles_to_relocate} {self._vehicle_type} from {self._origin} to {self._destination} (distance = {self._distance})"

    def __repr__(self) -> str:
        return self.__str__()
