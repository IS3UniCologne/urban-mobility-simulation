from abc import ABC, abstractmethod

from simulation.operator.vehicle_fleet import VehicleFleet


class RelocationInterface(ABC):
    """
    A class that implements this interface supplies strategy and functionality for spatially rebalancing a fleet of vehicles.

    Operators expect to periodically call the @relocate_fleet method to rebalance their fleet.
    """

    @abstractmethod
    def relocate_fleet(self, fleet: VehicleFleet, ):
        pass
    