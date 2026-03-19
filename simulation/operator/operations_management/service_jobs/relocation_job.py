"""Service job for relocating shared vehicles between regions."""

from __future__ import annotations

import heapq
from typing import TYPE_CHECKING

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.operator.operations_management.service_jobs.service_job import (
    ServiceJob,
)
from simulation.tasks.base.vehicle_session import VehicleSession
from simulation.tasks.operations.service_worker_relocation_task import (
    ServiceWorkerRelocationTask,
)
from simulation.vehicle.mixins.reservable_mixin import ReservableMixin

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.enums import VehicleType
    from simulation.helper.types import RegionId
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.vehicle.reservation import Reservation
    from simulation.vehicle.vehicle import Vehicle


class RelocationJob(ServiceJob):
    """Relocates shared vehicles between regions using a service worker."""

    __slots__ = (
        "_config",
        "_destination",
        "_distance",
        "_geo_env",
        "_number_of_vehicles_to_relocate",
        "_origin",
        "_vehicle_fleet",
        "_vehicle_type",
    )

    def __init__(
        self,
        sim: SimulationContext,
        origin: RegionId,
        destination: RegionId,
        number_of_vehicles_to_relocate: int,
        distance: float,
        vehicle_type: VehicleType,
        vehicle_fleet: VehicleFleet,
    ) -> None:
        super().__init__(sim)

        self._config = sim.config
        self._geo_env = sim.geo_env

        self._origin = origin
        self._destination = destination
        self._number_of_vehicles_to_relocate = number_of_vehicles_to_relocate
        self._vehicle_type = vehicle_type

        self._vehicle_fleet = vehicle_fleet
        self._distance = distance

    def execute(self) -> Generator[Event, None, None]:
        """Execute relocation: select vehicles and move them to destination."""
        with self._vehicle_fleet.resource.request() as req:
            # Multiple service workers cannot access the vehicle list in parallel
            yield req

            potential_vehicles_to_relocate: set[Vehicle] = (
                self._vehicle_fleet.vehicles_in_region(self._origin)
            )
            eligible_vehicles = (
                vehicle
                for vehicle in potential_vehicles_to_relocate
                if vehicle.vehicle_type == self._vehicle_type
                and isinstance(vehicle, ReservableMixin)
                and not vehicle.is_reserved
            )
            max_candidates = max(0, int(self._number_of_vehicles_to_relocate))
            candidates = heapq.nsmallest(
                max_candidates, eligible_vehicles, key=lambda v: v.uid
            )
            selected_vehicles_to_relocate: list[tuple[Vehicle, Reservation]] = [
                (vehicle, vehicle.reserve()) for vehicle in candidates
            ]

        for vehicle, reservation in selected_vehicles_to_relocate:
            lat, lng = self._geo_env.get_random_position(self._destination)
            vehicle_dest = GeodesicPosition(self._sim, lat, lng, self._destination)

            distance = vehicle.position << vehicle_dest
            vehicle_relocation_velocity = self._config.operators[
                0
            ].OPERATIONS_CONFIG.VEHICLE_RELOCATION_VELOCITY
            relocation_duration_per_vehicle = (
                distance / vehicle_relocation_velocity
            ) / len(selected_vehicles_to_relocate)

            task = ServiceWorkerRelocationTask(
                sim=self._sim,
                vehicle=vehicle,
                destination=vehicle_dest,
                relocation_duration=relocation_duration_per_vehicle,
            )

            session = VehicleSession(
                sim=self._sim,
                vehicle=vehicle,
                reservation=reservation,
                tasks=[task],
                holder=None,
            )

            yield from session.execute()

        self._finished.succeed()

    def __str__(self) -> str:  # noqa: D105
        return f"RelocationJob for {self._number_of_vehicles_to_relocate} {self._vehicle_type} from {self._origin} to {self._destination} (distance = {self._distance})"

    def __repr__(self) -> str:  # noqa: D105
        return self.__str__()
