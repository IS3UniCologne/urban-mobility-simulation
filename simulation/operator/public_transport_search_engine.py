from simulation.helper.configuration.configuration import Configuration
from simulation.helper.time import SimulationTimeConverter
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.operations_management.operations_public_transport import (
    OperationsPublicTransport,
)
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transportation_search_task import TransportationSearchTask


class PublicTransportSearchEngine(SearchEngineInterface):
    def __init__(self, env):
        self._env = env
        self._fleet = None
        self._config = Configuration.instance()

    def search_for_transportation_alternatives(
        self, transportation_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        user_config = self._config.user_config

        browser = TransportationAlternativeBrowser()
        search_time = transportation_search_task.transport_task.time

        for viable_transit in OperationsPublicTransport.find_viable_transit(
            transportation_search_task,
            user_config.spatial_strategy,
            user_config.max_wait,
        ):
            vehicle = viable_transit["vehicle"]
            subroute = viable_transit["subroute"]
            walking_dist_to_start = viable_transit["initial_walking"]
            walking_dist_to_destination = viable_transit["final_walking"]

            price = 0  # for PublicTransit we assume the perfect world
            distance = (
                subroute.total_distance()
                + walking_dist_to_start
                + walking_dist_to_destination
            )

            # from search to arrival + walk to final destination
            duration = SimulationTimeConverter.duration_between(
                SimulationTimeConverter.as_str(search_time),
                vehicle.prognose_arrival(subroute.destination),
            ) + (walking_dist_to_destination / user_config.walking_speed_kph)

            # TODO: convenience=0 is only a placeholder
            transportation_alternative = TransportationAlternative(
                vehicle, subroute, price, duration, distance, 0
            )
            browser.add_transportation_alternative(transportation_alternative)

        return browser

    def register_fleet(self, fleet: VehicleFleet):
        pass
