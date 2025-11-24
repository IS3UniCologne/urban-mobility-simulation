"""Passenger interface for vehicle interactions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Process

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
    ) -> Generator[Process, Any, None]:
        """Ride in vehicle to destination as a passenger."""
        pass

    @abstractmethod
    def identify_passenger(self) -> str:  # noqa: D102
        pass
