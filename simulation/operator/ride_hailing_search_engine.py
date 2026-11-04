"""Search engine for ride-hailing transportation alternatives."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from simulation.helper.vehicle_states import VehicleStates
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.ride_hailing_fleet import RideHailingFleet
from simulation.operator.search_engine import SearchEngine, SearchEngineDependencies

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import (
        RideHailingSearchEngineConfig,
    )
    from simulation.helper.types import SimTime
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )
    from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle

from simulation.helper.enums import AutonomyType
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)


class RideHailingSearchEngine(SearchEngine):
    """Search engine for ride-hailing vehicles.

    Parameters
    ----------
    deps : SearchEngineDependencies
        Shared search engine dependencies, with a RideHailingSearchEngineConfig as config.

    Raises
    ------
    TypeError
        If the operator fleet is not a RideHailingFleet.
    """

    __slots__ = (
        "_AV_price_reduction",
        "_arrival_lookahead_min",
        "_env",
        "_fleet",
        "_max_pickup_distance",
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

        config = cast("RideHailingSearchEngineConfig", deps.config)

        if not isinstance(deps.operator.fleet, RideHailingFleet):
            raise TypeError("Fleet must be of type RideHailingFleet")

        self._fleet: RideHailingFleet = deps.operator.fleet

        self._AV_price_reduction = config.AV_PRICE_REDUCTION
        self._price_entering = config.PRICE_ENTERING
        self._price_per_minute = config.PRICE_PER_MINUTE
        self._price_per_km = config.PRICE_PER_KM
        self._min_price = config.MINIMUM_PRICE
        self._max_pickup_distance = config.MAX_PICKUP_DISTANCE
        self._arrival_lookahead_min = config.ARRIVAL_LOOKAHEAD_MIN

    def search_for_transportation_alternatives(
        self, transport_task: TransportRequest
    ) -> TransportationAlternativeBrowser:
        """Spot all available vehicles to user.

        Offers each vehicle within the pickup radius that has the energy for the pickup and the trip.
        Prices and the pickup radius come from the search engine configuration.

        Parameters
        ----------
        transport_task : TransportRequest
            Transport demand to serve.

        Returns
        -------
        TransportationAlternativeBrowser
            Available alternatives with auxiliary trip information.
        """
        browser = TransportationAlternativeBrowser()

        # hexagon_origin = vehicle_search_task.agent_position.get_default_hexagon()

        origin = transport_task.origin
        destination = transport_task.destination

        # Info about the route - if we distinguish between car/scooter and ks/bike routes, move to for loop
        # Calc Route
        route = Route(origin=origin, destination=destination)

        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # human-driven vehicles first, this just preserves old behavior, but is not necessary for correctness
        candidates = sorted(
            self._candidates(origin, distance),
            key=lambda car: car.autonomy_type is AutonomyType.AUTONOMOUS,
        )
        for car in candidates:
            is_autonomous = car.autonomy_type is AutonomyType.AUTONOMOUS
            if car.is_reserved and not is_autonomous:
                continue

            if car.state is VehicleStates.STANDBY:
                route_to_pick_up = Route(car.position, origin)
            elif car.current_request is None:
                self._logger.warning("search found non-parking car without request")
                continue
            else:
                route_to_pick_up = Route(car.current_request.destination, origin)

            trip_duration = car.calculate_travel_time(distance)
            price = max(
                self._price_entering
                + trip_duration * self._price_per_minute
                + distance / 1000 * self._price_per_km,
                self._min_price,
            )
            if is_autonomous:
                price *= self._AV_price_reduction

            browser.add_transportation_alternative(
                TransportationAlternative(
                    vehicle=car,
                    route=route,
                    price=price,
                    duration=trip_duration,
                    distance=distance,
                    convenience=3,
                    operator=self.operator,
                    route_to_pickup=route_to_pick_up,
                    est_pickup_time=self._calculate_pickup_time(
                        vehicle=car, route_to_pick_up=route_to_pick_up
                    ),
                )
            )

        return browser

    def _candidates(
        self, origin: GeodesicPosition, trip_distance_m: float
    ) -> list[RideHailingVehicle]:
        """Find vehicles within the pickup radius with the energy to serve the trip.

        A parking vehicle needs the energy to drive to the origin and then the trip.
        A vehicle expected to arrive within the radius and the arrival lookahead needs the energy to finish its current request first.

        Parameters
        ----------
        origin : GeodesicPosition
            Trip origin.
        trip_distance_m : float
            Trip length from origin to destination.

        Returns
        -------
        list of RideHailingVehicle
            Parking vehicles, then vehicles expected to arrive.
        """
        parking = [
            car
            for car in self._fleet.parking_vehicles_in_radius(
                origin, radius=self._max_pickup_distance
            )
            if car.energy_system.has_enough_energy(
                (car.position << origin) + trip_distance_m
            )
        ]
        arriving = [
            car
            for car in self._fleet.expected_arrivals_in_radius(
                origin,
                self._max_pickup_distance,
                self._sim.time + self._arrival_lookahead_min,
            )
            if car.current_request is not None
            and car.energy_system.has_enough_energy(
                (car.current_request.origin << car.current_request.destination)
                + (car.current_request.destination << origin)
                + trip_distance_m
            )
        ]
        # will remove this cast in the future when fleets are typed properly
        return cast("list[RideHailingVehicle]", parking + arriving)

    def _calculate_pickup_time(
        self, vehicle: RideHailingVehicle, route_to_pick_up: Route
    ) -> SimTime | None:
        """
        Calculate the estimated pickup time for a vehicle.

        If the vehicle is currently parking, the pickup time is calculated as the time it takes to drive to the pickup location plus the current simulation time.
        If the vehicle is currently driving, the pickup time is calculated as the time it takes to drive to the pickup location plus the estimated completion time of the vehicle's current task.

        Parameters
        ----------
        vehicle : RideHailingVehicle
            Vehicle to calculate the pickup time for.
        route_to_pick_up : Route
            Route from vehicle position to pickup location.

        Returns
        -------
        SimTime or None
            Estimated absolute pickup time. None if neither parking nor in use.
        """
        if vehicle.state is VehicleStates.STANDBY:
            return (
                vehicle.calculate_travel_time(route_to_pick_up.distance)
                + self._sim.time
            )

        elif vehicle.is_in_use:
            return (
                vehicle.calculate_travel_time(route_to_pick_up.distance)
                + vehicle.estimated_completion_time
            )

        return None
