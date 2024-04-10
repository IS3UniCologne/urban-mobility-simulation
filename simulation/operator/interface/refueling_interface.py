from abc import ABC, abstractmethod

from simulation.operator.vehicle_fleet import VehicleFleet


class RefuelingInterface(ABC):
    """
    A class that implements this interface supplies strategy and functionality for keeping a fleet of vehicles charged/fueled.

    Operators expect to periodically call the @refuel_fleet method to keep their fleet charged/fueled.
    """

    @abstractmethod
    def refuel_fleet(self, fleet: VehicleFleet):
        pass
