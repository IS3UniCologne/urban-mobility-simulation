from abc import ABC, abstractmethod


class FleetInterface(ABC):

    @abstractmethod
    def get_all_vehicles(self, region):
        pass

    @abstractmethod
    def get_available_vehicles(self, region):
        pass