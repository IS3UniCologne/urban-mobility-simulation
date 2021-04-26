from simulation.environment.geodesic_position import GeodesicPosition
from simulation.infrastructure.Route import Route
from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative
from simulation.operator.data_transfer_object.transportation_alternative_browser import TransportationAlternativeBrowser
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.tasks.transportation_search_task import TransportationSearchTask
from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedVehicleSearchEngine(SearchEngineInterface):

    def __init__(self, env):
        self._env = env

    def search_for_transportation_alternatives(self, vehicle_search_task: TransportationSearchTask) -> TransportationAlternativeBrowser:
        browser = TransportationAlternativeBrowser()

        # Implement Search Behavior
        transportation_alternative = TransportationAlternative(SharedVehicle(GeodesicPosition(13.4, 53.3)), Route(GeodesicPosition(13.4, 53.3), GeodesicPosition(13.4, 53.3)), price = 0, distance = 0, duration = 0)
        browser.add_transportation_alternative(transportation_alternative)

        return browser