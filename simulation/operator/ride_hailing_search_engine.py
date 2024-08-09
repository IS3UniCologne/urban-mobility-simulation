from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.tasks.transportation_search_task import TransportationSearchTask
from simulation.vehicle.vehicle import VehicleState


class RideHailingSearchEngine(SearchEngineInterface):
    def __init__(self, env):
        self._env = env
        self._fleet = None

        self._AV_price_reduction = Configuration.instance().get_AV_price_reduction()

        self._price_entering = (
            Configuration.instance().get_price_parameters_ride_hailing()[0]
        )
        self._price_per_minute = (
            Configuration.instance().get_price_parameters_ride_hailing()[1]
        )
        self._price_per_km = (
            Configuration.instance().get_price_parameters_ride_hailing()[2]
        )
        self._min_price = Configuration.instance().get_price_parameters_ride_hailing()[
            3
        ]

    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user
        :param vehicle_search_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """
        browser = TransportationAlternativeBrowser()

        # hexagon_origin = vehicle_search_task.agent_position.get_default_hexagon()

        origin = vehicle_search_task.transport_task.origin

        cars_in_area = self._fleet.get_available_vehicles_to_user(origin)

        destination = vehicle_search_task.transport_task.destination

        # Info about the route - if we distinguish between car/scooter and ks/bike routes, move to for loop
        # Calc Route
        route = Route(origin, destination)

        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # Add all available cars to alternative browser
        AVs_in_area = [
            car for car in cars_in_area if car.__class__.__name__ == "RideHailingAV"
        ]
        CVs_in_area = [
            car for car in cars_in_area if car.__class__.__name__ == "RideHailingCar"
        ]
        # if vehicle_search_task.transport_task.viable_vehicle_modes['RideHailingCar'] == 1:
        for car in CVs_in_area:
            # Calc waiting time
            route_to_pick_up = Route(car.position, origin)
            distance_to_pick_up = route_to_pick_up.distance

            # Calc Duration
            trip_duration = distance / car.velocity

            # Calc Price
            price = max(
                self._price_entering
                + trip_duration * self._price_per_minute
                + distance / 1000 * self._price_per_km,
                self._min_price,
            )

            # Put together
            transportation_alternative = TransportationAlternativeRideHailing(
                car, route, price, trip_duration, distance, 3, route_to_pick_up
            )

            total_distance = distance + distance_to_pick_up
            if car.has_enough_state_of_charge(total_distance) and car.state in [
                VehicleState.PARKING,
                VehicleState.DRIVING,
            ]:
                browser.add_transportation_alternative(transportation_alternative)

        # if vehicle_search_task.transport_task.viable_vehicle_modes['AutonomousCar'] == 1:
        for car in AVs_in_area:
            # Calc waiting time
            route_to_pick_up = Route(car.position, origin)
            distance_to_pick_up = route_to_pick_up.distance

            # Calc Duration
            trip_duration = distance / car.velocity

            # Calc Price
            # TODO: update the price for ride-hailing
            price = (
                max(
                    self._price_entering
                    + trip_duration * self._price_per_minute
                    + distance / 1000 * self._price_per_km,
                    self._min_price,
                )
                * self._AV_price_reduction
            )

            # Put together
            transportation_alternative = TransportationAlternativeRideHailing(
                car, route, price, trip_duration, distance, 3, route_to_pick_up
            )

            total_distance = distance + distance_to_pick_up
            if car.has_enough_state_of_charge(total_distance) and car.state in [
                VehicleState.PARKING,
                VehicleState.DRIVING,
            ]:
                browser.add_transportation_alternative(transportation_alternative)

        return browser
