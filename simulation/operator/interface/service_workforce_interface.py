from abc import ABC, abstractmethod

from simulation.operator.service_workforce import ServiceWorkforce


class ServiceWorkforceInterface(ABC):
    @abstractmethod
    def register_workforce(self, workforce: ServiceWorkforce):
        pass
