import logging
from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative
from simulation.operator.data_transfer_object.transportation_alternative_browser import TransportationAlternativeBrowser
from simulation.operator.interface.fleet_interface import FleetInterface
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.walking_fleet import WalkingFleet
from simulation.tasks.transport_task import TransportTask
from simulation.tasks.transportation_search_task import TransportationSearchTask


class WalkingSearchEngine(SearchEngineInterface, PaymentInterface):

    def __init__(self, env):
        PaymentInterface.__init__(self)
        self._env = env
        self._fleet = None

    def search_for_transportation_alternatives(self, vehicle_search_task: TransportationSearchTask) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user
        :param vehicle_search_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """
        browser = TransportationAlternativeBrowser()

        walking = self.fleet.walking

        origin = vehicle_search_task.transport_task.origin
        destination = vehicle_search_task.transport_task.destination

        # Calc Route
        route = Route(origin, destination)

        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # Calc Duration
        duration = distance/walking.velocity

        # Calc Price
        price = 0

        # Put together
        transportation_alternative = TransportationAlternative(walking, route, price, duration, distance, 3)

        browser.add_transportation_alternative(transportation_alternative)

        return browser

    def pay_for_fulfilled_transportation_task(self, user, transportation_task: TransportTask, selected_transportation_alternative: TransportationAlternative):
        pass

    def withdraw_transportation_task(self, user, transportation_task: TransportTask):
        pass

    def register_fleet(self, fleet: WalkingFleet):
        self._fleet = fleet

    @property
    def fleet(self):
        if self._fleet:
            return self._fleet
        raise Exception("Fleet was not registred. Inject fleet instance to search engine using register_fleet")