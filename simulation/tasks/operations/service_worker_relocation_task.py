"""VehicleTask for relocating a single vehicle with a service worker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.infrastructure.route import Edge
from simulation.tasks.base.vehicle_task import VehicleTask
from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition


class ServiceWorkerRelocationTask(VehicleTask[SharedVehicle]):
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
    """

    __slots__ = ("_relocation_duration",)

    _destination: GeodesicPosition  # Narrowed from optional type in parent class

    def __init__(
        self,
        sim: SimulationContext,
        vehicle: SharedVehicle,
        destination: GeodesicPosition,
        relocation_duration: float,
    ) -> None:
        super().__init__(sim, vehicle, destination)
        self._relocation_duration = relocation_duration

    def _run(self) -> Generator[Event, None, None]:
        """Relocate vehicle to destination.

        Yields
        ------
        Event
            Events during relocation.
        """
        distance = self._vehicle.position << self._destination
        relocation_route = Edge(distance, self._vehicle.position, self._destination)

        yield self._env.process(
            self._vehicle.relocate(relocation_route, self._relocation_duration)
        )

    def get_predicted_energy_delta(self, current_energy: float | None = None) -> float:
        """Return predicted energy for relocation: Zero, as service worker is assumed to use external energy source.

        Parameters
        ----------
        current_energy : float or None
            Unused; relocation energy depends on distance only.

        Returns
        -------
        float
            Zero, as service worker is assumed to use external energy source.
        """
        return 0.0

    def get_predicted_duration(self, current_energy: float | None = None) -> float:
        """Calculate predicted duration for relocation.

        Parameters
        ----------
        current_energy : float or None
            Unused; relocation duration is pre-calculated.

        Returns
        -------
        float
            Predicted duration in minutes (provided by relocation job).
        """
        return self._relocation_duration
