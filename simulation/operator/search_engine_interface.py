from abc import ABC, abstractmethod

from simulation.tasks.vehicle_search_task import VehicleSearchTask


class SearchEngineInterface(ABC):

    @abstractmethod
    def search_for_vehicles(self, vehicle_search_task: VehicleSearchTask) -> []:
        pass # Implement filtering
        # return []