"""Passenger interface for vehicle interactions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.infrastructure.route import Route
    from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


class PassengerInterface(ABC):  # noqa: D101
    @abstractmethod
    def mount_vehicle(self, vehicle: RideHailingVehicle) -> None:
        """Mount vehicle as passenger."""
        pass

    @abstractmethod
    def unmount_vehicle(self, vehicle: RideHailingVehicle) -> None:
        """Unmount vehicle as passenger."""
        pass

    @abstractmethod
    def ride_in_vehicle(
        self, vehicle: RideHailingVehicle, route: Route
    ) -> Generator[Event, Any, float]:
        """Ride in vehicle to destination as a passenger."""
        pass

    @abstractmethod
    def identify_passenger(self) -> str:  # noqa: D102
        pass

    @abstractmethod
    def on_vehicle_moved(self, position: GeodesicPosition) -> None:
        """Update position when the vehicle carrying this passenger moves.

        Parameters
        ----------
        position : GeodesicPosition
            The new position of the vehicle.
        """
        pass
