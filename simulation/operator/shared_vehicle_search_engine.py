from simulation.environment.geodesic_position import GeodesicPosition
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative
from simulation.operator.data_transfer_object.transportation_alternative_browser import TransportationAlternativeBrowser
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.tasks.transportation_search_task import TransportationSearchTask
from simulation.vehicle.shared_vehicle import SharedVehicle

import logging

class SharedVehicleSearchEngine(SearchEngineInterface, PaymentInterface):

    def __init__(self, env):
        PaymentInterface.__init__(self)
        self._env = env

    def search_for_transportation_alternatives(self, vehicle_search_task: TransportationSearchTask) -> TransportationAlternativeBrowser:
        browser = TransportationAlternativeBrowser()

        # Implement Search Behavior
        transportation_alternative = TransportationAlternative(SharedVehicle(self._env, GeodesicPosition(13.4, 53.3)), Route(GeodesicPosition(13.4, 53.3), GeodesicPosition(16.4, 55.3)), price = 9.35, distance = 0, duration = 45)
        browser.add_transportation_alternative(transportation_alternative)

        return browser

    def pay_for_fulfilled_transportation_task(self, user, selected_transportation_alternative: TransportationAlternative):
        payment = selected_transportation_alternative.price
        self.increase_total_revenue(payment)

        logging.debug(f"New Payment ({payment}) received from User {user.user_id}. Current Total Revenue: {self.total_revenue}.",
                      extra={"clazz": self.__class__.__name__, "oid": ""})
