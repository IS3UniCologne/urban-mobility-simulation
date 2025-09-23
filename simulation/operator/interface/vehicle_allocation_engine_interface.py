from abc import ABC, abstractmethod  # noqa: D100

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
    ) -> VehicleAllocation:
        pass  # Implement filtering
