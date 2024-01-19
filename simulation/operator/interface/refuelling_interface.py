from abc import ABC, abstractmethod

from simulation.operator.vehicle_fleet import VehicleFleet


class RefuellingInterface(ABC):

    @abstractmethod
    def refuel_fleet(self, fleet: VehicleFleet, ):
        pass
    