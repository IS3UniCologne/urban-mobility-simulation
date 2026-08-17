"""Interface for vehicle allocation engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.agent.user import User
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.vehicle_allocation import (
        VehicleAllocation,
    )


class AllocationEngineInterface(ABC):
    """Interface all vehicle allocation engines must implement."""

    @abstractmethod
    def request_vehicle_allocation(
        self, user: User, selected_transportation_alternative: TransportationAlternative
    ) -> Generator[Event, Any, VehicleAllocation | None]:
        """
        User requests allocation of selected TransportationAlternative.

        Parameters
        ----------
        user : User
            User requesting the allocation.
        selected_transportation_alternative : TransportationAlternative
            Alternative containing the vehicle to allocate.

        Yields
        ------
        Event
            Events awaited while the allocation is processed.

        Returns
        -------
        VehicleAllocation or None
            Allocation if successful, None otherwise.
        """
