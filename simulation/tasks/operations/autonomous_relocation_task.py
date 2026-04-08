"""Vehicle task for relocating an autonomous vehicle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.infrastructure.route import Route
from simulation.tasks.base.vehicle_task import VehicleTask

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


class AutonomousRelocationTask(VehicleTask["RideHailingVehicle"]):
    """Relocates an autonomous vehicle to a destination.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    vehicle : RideHailingVehicle
        The vehicle to relocate.
    destination : GeodesicPosition
        The destination position for the vehicle.
    distance : float
        Pre-calculated distance to destination (in meters).
    """

    __slots__ = ("_destination", "_distance")

    def __init__(
        self,
        sim: SimulationContext,
        vehicle: RideHailingVehicle,
        destination: GeodesicPosition,
        distance: float,
    ) -> None:
        super().__init__(sim, vehicle)
        self._destination = destination
        self._distance = distance

    def _run(self) -> Generator[Event, None, None]:
        """Relocate vehicle to destination.

        Yields
        ------
        Event
            Events during relocation.
        """
        self.logger.debug(
            "Autonomously relocating vehicle %s to %s (%.0f m).",
            self._vehicle.uid,
            self._destination,
            self._distance,
        )

        relocation_route = Route(
            origin=self._vehicle.position, destination=self._destination
        )

        yield from self._vehicle.relocate(relocation_route)

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
        energy_required = self._vehicle.energy_system.calculate_energy_required(
            self._distance
        )
        return -energy_required

    def get_predicted_duration(self, current_energy: float | None = None) -> float:
        """Calculate predicted duration for relocation.

        Parameters
        ----------
        current_energy : float or None
            Unused; relocation duration depends on distance only.

        Returns
        -------
        float
            Predicted duration in minutes based on distance and velocity.
        """
        return self._vehicle.calculate_travel_time(self._distance)
