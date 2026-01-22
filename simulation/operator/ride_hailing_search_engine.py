from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING, cast

from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.ride_hailing_fleet import RideHailingFleet
from simulation.operator.search_engine import SearchEngine, SearchEngineDependencies

if TYPE_CHECKING:
    from simulation.helper.configuration.configuration import (
        RideHailingOperationsConfig,
    )
    from simulation.tasks.transport_task import TransportTask
    from simulation.vehicle.vehicle import Vehicle

from simulation.helper.configuration.enums import AutonomyType, VehicleState
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
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

        ops_config = cast(
            "RideHailingOperationsConfig", deps.operator.operations.config
        )

        if not isinstance(deps.operator.fleet, RideHailingFleet):
            raise TypeError("Fleet must be of type RideHailingFleet")

        self._fleet: RideHailingFleet = deps.operator.fleet

        self._AV_price_reduction = ops_config.AV_PRICE_REDUCTION
        self._price_entering = ops_config.PRICE_ENTERING
        self._price_per_minute = ops_config.PRICE_PER_MINUTE
        self._price_per_km = ops_config.PRICE_PER_KM
        self._min_price = ops_config.MINIMUM_PRICE

    def search_for_transportation_alternatives(
        self, transport_task: TransportTask
    ) -> TransportationAlternativeBrowser:
        """Spot all available vehicles to user.

        :param transport_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """
        browser = TransportationAlternativeBrowser()

        # hexagon_origin = vehicle_search_task.agent_position.get_default_hexagon()

        origin = transport_task.origin

        # TODO: These are vehicles, not necessarily cars
        cars_in_area = self._fleet.get_available_vehicles_to_user(origin)

        destination = transport_task.destination

        # Info about the route - if we distinguish between car/scooter and ks/bike routes, move to for loop
        # Calc Route
        route = Route(origin=origin, destination=destination)

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
                if car.current_task is None:
                    # This should not happen, but just in case
                    self._logger.warning("search found non-parking car without task")
                    continue
                # TODO: this does not consider that the car will deplete energy to current_task.destination
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

            # calculate pick up time

            pickup_time = self._calculate_pickup_time(
                vehicle=car, route_to_pick_up=route_to_pick_up
            )

            # Put together
            transportation_alternative = TransportationAlternative(
                vehicle=car,
                route=route,
                price=price,
                duration=trip_duration,
                distance=distance,
                convenience=3,
                operator=self.operator,
                route_to_pickup=route_to_pick_up,
                est_pickup_time=pickup_time,
            )

            total_distance = distance + distance_to_pick_up
            if car.energy_system.has_enough_energy(total_distance) and car.state in [
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
                if car.current_task is None:
                    # This should not happen, but just in case
                    self._logger.warning("search found non-parking car without task")
                    continue
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

            pickup_time = self._calculate_pickup_time(
                vehicle=car, route_to_pick_up=route_to_pick_up
            )

            # Put together
            transportation_alternative = TransportationAlternative(
                vehicle=car,
                route=route,
                price=price,
                duration=trip_duration,
                distance=distance,
                convenience=3,
                operator=self.operator,
                route_to_pickup=route_to_pick_up,
                est_pickup_time=pickup_time,
            )

            total_distance = distance + distance_to_pick_up
            if car.energy_system.has_enough_energy(total_distance) and car.state in [
                VehicleState.PARKING,
                VehicleState.DRIVING,
            ]:
                browser.add_transportation_alternative(transportation_alternative)

        return browser

    def _calculate_pickup_time(
        self, vehicle: Vehicle, route_to_pick_up: Route
    ) -> float:
        if vehicle.state == VehicleState.PARKING:
            return route_to_pick_up.distance / vehicle.velocity

        elif vehicle.state == VehicleState.DRIVING:
            return (
                route_to_pick_up.distance / vehicle.velocity
                + vehicle.estimated_completion_time
                - self._sim.env.now
            )
