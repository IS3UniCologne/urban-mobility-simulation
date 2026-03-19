"""VehicleTask for relocating a single vehicle with a service worker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.infrastructure.route import Edge, Vertex
from simulation.tasks.base.vehicle_task import VehicleTask

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.vehicle.shared_vehicle import SharedVehicle


class ServiceWorkerRelocationTask(VehicleTask["SharedVehicle"]):
    """Single vehicle relocation operation with a service worker.

    TODO: implement actual service worker behavior.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle : SharedVehicle
        The vehicle to relocate.
    destination : GeodesicPosition
        The destination position for the vehicle.
    relocation_duration : float
        Duration to relocate vehicle (in minutes).
    service_worker_uid : str
        Identifier of the service worker performing this task.
    """

    __slots__ = ("_destination", "_relocation_duration", "_service_worker_uid")

    def __init__(
        self,
        sim: SimulationContext,
        vehicle: SharedVehicle,
        destination: GeodesicPosition,
        relocation_duration: float,
        service_worker_uid: str,
    ) -> None:
        super().__init__(sim, vehicle)
        self._destination = destination
        self._relocation_duration = relocation_duration
        self._service_worker_uid = service_worker_uid

    def _run(self) -> Generator[Event, None, None]:
        """Relocate vehicle to destination.

        Yields
        ------
        Event
            Events during relocation.
        """
        distance = self._vehicle.position << self._destination
        relocation_route = Edge(
            distance, Vertex(self._vehicle.position), Vertex(self._destination)
        )

        yield self._env.process(
            self._vehicle.relocate(
                relocation_route, self._relocation_duration, self._service_worker_uid
            )
        )

    def get_predicted_energy_delta(self, current_energy: float | None = None) -> float:
        """Calculate predicted energy for relocation.

        Parameters
        ----------
        current_energy : float or None
            Unused; relocation energy depends on distance only.

        Returns
        -------
        float
            Predicted energy delta in kWh for relocating to destination.
        """
        distance = self._vehicle.position << self._destination
        energy_required = self._vehicle.energy_system.calculate_energy_required(
            distance
        )
        return -energy_required

    def get_predicted_duration(self, current_energy: float | None = None) -> float:
        """Calculate predicted duration for relocation.

        Parameters
        ----------
        current_energy : float or None
            Unused; relocation duration is pre-calculated.

        Returns
        -------
        float
            Predicted duration in minutes (provided by coordinator).
        """
        return self._relocation_duration
