"""Interface for driver behavior in vehicles."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event


class DriverInterface(ABC):  # noqa: D101
    @abstractmethod
    def mount_vehicle_as_driver(self, vehicle):  # noqa: ANN001, ANN201, D102
        pass

    @abstractmethod
    def unmount_vehicle_as_driver(self, vehicle):  # noqa: ANN001, ANN201, D102
        pass

    @abstractmethod
    def drive_vehicle(self, vehicle, route) -> Generator[Event, Any, float]:  # noqa: ANN001, D102
        pass

    @abstractmethod
    def park_vehicle(self, vehicle):  # noqa: ANN001, ANN201, D102
        pass

    @abstractmethod
    def identify_driver(self) -> str:  # noqa: D102
        pass
