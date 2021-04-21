from simulation.operator.search_engine_interface import SearchEngineInterface
from simulation.tasks.vehicle_search_task import VehicleSearchTask


class SharedVehicleSearchEngine(SearchEngineInterface):

    def search_for_vehicles(self, vehicle_search_task: VehicleSearchTask) -> []:
        # Implement Search Behavior
        return []