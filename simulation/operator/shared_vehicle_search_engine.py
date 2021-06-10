from simulation.environment.geodesic_position import GeodesicPosition
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative
from simulation.operator.data_transfer_object.transportation_alternative_browser import TransportationAlternativeBrowser
from simulation.operator.interface.fleet_interface import FleetInterface
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.tasks.transport_task import TransportTask
from simulation.tasks.transportation_search_task import TransportationSearchTask
from simulation.vehicle.shared_vehicle import SharedVehicle

import logging

class SharedVehicleSearchEngine(SearchEngineInterface, PaymentInterface):

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

        hexagon_origin, _ = vehicle_search_task.agent_position.get_hexagon()

        cars_in_area, scooters_in_area, kick_scooters_in_area, bikes_in_area = self.fleet.get_available_vehicles(hexagon_origin)

        origin = vehicle_search_task.transport_task.origin
        destination = vehicle_search_task.transport_task.destination

        o_hex,_ = origin.get_hexagon()
        d_hex,_ = destination.get_hexagon()

        for car in cars_in_area:
            # Calc Route
            route = Route(origin, destination)

            # Calc Distance
            distance = route.distance          # Euclidean Distance

            # Calc Duration
            duration = distance/car.velocity

            # Calc Price
            price = duration*car.price_per_minute

            # Put together
            transportation_alternative = TransportationAlternative(car, route, price, duration, distance)

            browser.add_transportation_alternative(transportation_alternative)

        return browser

    def pay_for_fulfilled_transportation_task(self, user, selected_transportation_alternative: TransportationAlternative):
        payment = selected_transportation_alternative.price
        self.increase_total_revenue(payment)

        logging.info(f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",
                      extra={"clazz": self.__class__.__name__, "oid": ""})

    def withdraw_transportation_task(self, user, transportation_task : TransportTask):
        self.increase_total_missed_trips()
        logging.info(f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",
                      extra={"clazz": self.__class__.__name__, "oid": ""})

    def register_fleet(self, fleet: FleetInterface):
        self._fleet = fleet

    @property
    def fleet(self):
        if self._fleet:
            return self._fleet
        raise Exception("Fleet was not registred. Inject fleet instance to search engine using register_fleet")