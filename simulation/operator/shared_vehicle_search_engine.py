import logging

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative import \
    TransportationAlternative
from simulation.operator.data_transfer_object.transportation_alternative_browser import \
    TransportationAlternativeBrowser
from simulation.operator.interface.search_engine_interface import \
    SearchEngineInterface
from simulation.tasks.transport_task import TransportTask
from simulation.tasks.transportation_search_task import \
    TransportationSearchTask


class SharedVehicleSearchEngine(SearchEngineInterface):
    def __init__(self, env):
        self._env = env
        self._fleet = None

    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user
        :param vehicle_search_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """
        browser = TransportationAlternativeBrowser()

        hexagon_origin = vehicle_search_task.agent_position.get_default_hexagon()

        (cars_in_area, scooters_in_area, kick_scooters_in_area, bikes_in_area) = (
            self._fleet.get_available_vehicles(hexagon_origin)
        )

        origin = vehicle_search_task.transport_task.origin
        destination = vehicle_search_task.transport_task.destination

        origin.get_default_hexagon()
        destination.get_default_hexagon()

        # Info about the route - if we distinguish between car/scooter and ks/bike routes, move to for loop
        # Calc Route
        route = Route(origin, destination)

        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # Add all available cars to alternative browser
        for car in cars_in_area:
            # Calc Duration
            duration = distance / car.velocity

            # Calc Price
            price = duration * car.price_per_minute

            # Put together
            transportation_alternative = TransportationAlternative(
                car, route, price, duration, distance, 3
            )

            if car.has_enough_state_of_charge(distance):
                browser.add_transportation_alternative(transportation_alternative)

        # Add all available scooter to alternative browser
        for scooter in scooters_in_area:
            # Calc Duration
            duration = distance / scooter.velocity

            # Calc Price
            price = duration * scooter.price_per_minute

            # Put together
            transportation_alternative = TransportationAlternative(
                scooter, route, price, duration, distance, 2
            )

            if scooter.has_enough_state_of_charge(distance):
                browser.add_transportation_alternative(transportation_alternative)

        # Add all available kick scooter to alternative browser
        for kick_scooter in kick_scooters_in_area:
            # Calc Duration
            duration = distance / kick_scooter.velocity

            # Calc Price
            price = duration * kick_scooter.price_per_minute + 1.0  # 1€ Unlock Fee

            # Put together
            transportation_alternative = TransportationAlternative(
                kick_scooter, route, price, duration, distance, 1
            )

            if kick_scooter.has_enough_state_of_charge(distance):
                browser.add_transportation_alternative(transportation_alternative)

        return browser
