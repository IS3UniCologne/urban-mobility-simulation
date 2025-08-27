from abc import ABC, abstractmethod

from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.vehicle_allocation import (
    VehicleAllocation,
)


class AllocationEngineInterface(ABC):
    @abstractmethod
    def request_vehicle_allocation(
        self,
        user,  # noqa: ANN001
        selected_transportation_alternative: TransportationAlternative,
    ) -> VehicleAllocation:
        pass  # Implement filtering

    @abstractmethod
    def notify_user_arrival_at_pick_up_position(
        self, vehicle_assignment: VehicleAllocation
    ) -> None:
        pass  # Implement Notification
