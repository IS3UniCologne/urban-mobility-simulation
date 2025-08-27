from __future__ import annotations

from typing import TYPE_CHECKING, cast

from simulation.operator.search_engine import SearchEngine, SearchEngineDependencies

if TYPE_CHECKING:
    from simulation.helper.configuration.configuration import (
        RideHailingSearchEngineConfig,
    )
    from simulation.operator.ride_hailing_operator import RideHailingOperator
    from simulation.tasks.transportation_search_task import TransportationSearchTask

from simulation.helper.configuration.enums import AutonomyType, VehicleState
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)


class RideHailingSearchEngine(SearchEngine):
    """Search engine for ride-hailing vehicles."""

    __slots__ = (
        "_AV_price_reduction",
        "_env",
        "_fleet",
        "_min_price",
        "_price_entering",
        "_price_per_km",
        "_price_per_minute",
        "_sim",
    )

    def __init__(self, deps: SearchEngineDependencies) -> None:
        super().__init__(deps)
        self._sim = deps.sim
        self._env = deps.sim.env
        self._fleet = deps.operator.fleet
        self._AV_price_reduction = self.operator.operations.config.AV_PRICE_REDUCTION
        self._price_entering = self.operator.operations.config.PRICE_ENTERING
        self._price_per_minute = self.operator.operations.config.PRICE_PER_MINUTE
        self._price_per_km = self.operator.operations.config.PRICE_PER_KM
        self._min_price = self.operator.operations.config.MINIMUM_PRICE

    @property
    def config(self) -> RideHailingSearchEngineConfig:
        return cast("RideHailingSearchEngineConfig", self._config)

    @property
    def operator(self) -> RideHailingOperator:
        return cast("RideHailingOperator", self._operator)

    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        """Spot all available vehicles to user.

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
        route = Route(origin, destination=destination)

        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # TODO: check for more efficient way of doing this
        # Add all available cars to alternative browser
        AVs_in_area = [
            car for car in cars_in_area if car.autonomy_type == AutonomyType.AUTONOMOUS
        ]
        CVs_in_area = [
            car
            for car in cars_in_area
            if car.autonomy_type == AutonomyType.HUMAN_DRIVEN
        ]
        # if vehicle_search_task.transport_task.viable_vehicle_modes['RideHailingCar'] == 1:
        for car in CVs_in_area:
            # Calc waiting time
            if car.state == VehicleState.PARKING:
                route_to_pick_up = Route(car.position, origin)
            else:
                route_to_pick_up = Route(car.current_task.destination, origin)

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
            if car.state == VehicleState.PARKING:
                route_to_pick_up = Route(car.position, origin)
            else:
                route_to_pick_up = Route(car.current_task.destination, origin)

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
