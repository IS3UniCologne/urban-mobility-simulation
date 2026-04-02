from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.vehicle_allocation import (
        VehicleAllocation,
    )


class AllocationEngineInterface(ABC):  # noqa: D101
    @abstractmethod
    def request_vehicle_allocation(  # noqa: D102
        self,
        user,  # noqa: ANN001
        selected_transportation_alternative: TransportationAlternative,
    ) -> Generator[Event, Any, VehicleAllocation | None]:
        pass  # Implement filtering
