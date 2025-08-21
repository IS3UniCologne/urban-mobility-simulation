from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import TransitOperatorConfig
    from simulation.infrastructure.transit_network.stop import Stop
    from simulation.operator.public_transport_vehicle_fleet import (
        PublicTransportVehicleFleet,
    )
    from simulation.tasks.transportation_search_task import TransportationSearchTask
    from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle

from simulation.helper.simulation_base import SimulationBase
from simulation.helper.time import SimulationTimeConverter
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface


class PublicTransportSearchEngine(SearchEngineInterface, SimulationBase):
    __slots__ = (
        "_env",
        "_fleet",
        "_geo_env",
        "_operator_config",
        "_sim",
        "_user_config",
    )

    def __init__(
        self,
        sim: SimulationContext,
        fleet: PublicTransportVehicleFleet,
        operator_config: TransitOperatorConfig,
    ) -> None:
        super().__init__(sim=sim)
        self._sim = sim
        self._env = sim.env
        self._fleet = fleet
        self._operator_config = operator_config
        self._user_config = self._sim.config.user
        self._geo_env = sim.geo_env

    def find_viable_transit(  # noqa: ANN201
        self,
        transportation_search_task,  # noqa: ANN001
        spatial_strategy="hexagon",  # noqa: ANN001
        temporal_lookahead=10,  # noqa: ANN001
    ):
        search_time = transportation_search_task.transport_task.time
        latest_departure = SimulationTimeConverter.as_str(
            search_time + temporal_lookahead
        )
        walk_alternative = (
            transportation_search_task.transport_task.origin
            >> transportation_search_task.transport_task.destination
        )

        viable_transit = []
        busses = self._fleet.get_busses()

        if not busses:
            # No busses are en-route, report no viable alternative
            # TODO: fallback to timetable if temporal_lookahead > transit operator planning window?
            if (
                temporal_lookahead
                > self._operator_config.OPERATIONS_CONFIG.PLANNING_LOOKAHEAD
            ):
                raise NotImplementedError(
                    "temporal lookahead of user > planning lookahead of operator currently not supported"
                )

        for vehicle in busses:
            viable_stops = self._check_viable_stops(
                vehicle,
                spatial_strategy,
                transportation_search_task.transport_task.origin,
                transportation_search_task.transport_task.destination,
            )
            if viable_stops:
                # check for temporal alignment
                reachable_stops = []
                for stop in viable_stops["origin"]:
                    reachable, distance = self._reachable_in_time(
                        stop,
                        vehicle,
                        search_time,
                        transportation_search_task.transport_task.origin,
                        latest_departure,
                    )
                    if reachable:
                        reachable_stops.append(
                            (stop, distance)
                        )  # tuple of (Stop, walking distance to/from)

                if reachable_stops:
                    self.logger.debug(
                        "Bus %s is a viable transport alternative from %s to %s!",
                        vehicle.uid,
                        transportation_search_task.transport_task.origin,
                        transportation_search_task.transport_task.destination,
                    )

                    # build all possible combinations of viable subroutes
                    for start, walk_to_start in reachable_stops:
                        for end in viable_stops["destination"]:
                            if start.stop_id >= end.stop_id:
                                # only look at travel in the right direction
                                continue

                            subroute = vehicle.route.subroute(start, end)
                            walk_from_end = (
                                end
                                >> transportation_search_task.transport_task.destination
                            )

                            if (
                                walk_to_start >= walk_alternative
                                or walk_from_end >= walk_alternative
                                or (walk_to_start + walk_from_end) >= walk_alternative
                            ):
                                # if any one or the sum of both walking distances is larger than the alternative
                                # of walking the complete distance of the transport demand, then it's unlogical
                                # i.e. you are better off walking ;)
                                continue

                            # TODO: what if the combined duration of walking + driving + walking is longer than walking
                            # in this case, is transit really a viable alternative?

                            viable_transit.append(
                                {
                                    "vehicle": vehicle,
                                    "subroute": subroute,
                                    "initial_walking": walk_to_start,
                                    "final_walking": walk_from_end,
                                }
                            )

        return viable_transit

    def search_for_transportation_alternatives(
        self, transportation_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        browser = TransportationAlternativeBrowser()
        search_time = transportation_search_task.transport_task.time

        for viable_transit in self.find_viable_transit(
            transportation_search_task,
            self._user_config.SPATIAL_STRATEGY,
            self._user_config.TRANSIT_MAX_WAIT,
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
            ) + (walking_dist_to_destination / self._user_config.WALKING_SPEED)

            # TODO: convenience=0 is only a placeholder
            transportation_alternative = TransportationAlternative(
                vehicle, subroute, price, duration, distance, 0
            )
            browser.add_transportation_alternative(transportation_alternative)

        return browser

    def _check_viable_stops(  # noqa: ANN202
        self,
        vehicle: PublicTransitVehicle,
        strategy,  # noqa: ANN001
        origin: GeodesicPosition,
        destination: GeodesicPosition,
    ):
        """
        Check for viable transit stops nearby origin - destination travel demand for a given vehicle
        This only checks spatial alignment
        :param vehicle: PublicTransitVehicle
        :param strategy: e.g. 'hexagon' (viable when in same hexagon), 'euclidean' (viable when eucl. dist. <= X), ...
        :param origin: GeodesicPosition
        :param destination: GeodesicPosition
        :return: dict
        """
        if strategy == "hexagon":
            # trips are viable that start/end in the same hexagon as origin and destination
            origin_poly = self._geo_env.get_hexagon(origin.get_region_id())

            destination_poly = self._geo_env.get_hexagon(destination.get_region_id())
            in_vicinity = [
                {
                    "origin": x.is_in_geometry(origin_poly),
                    "destination": x.is_in_geometry(destination_poly),
                }
                for x in vehicle.route.route_stops
            ]
            origin_in_vicinity_at = [
                ix for ix, element in enumerate(in_vicinity) if element["origin"]
            ]
            destination_in_vicinity_at = [
                ix for ix, element in enumerate(in_vicinity) if element["destination"]
            ]

            # now we know which stops would potentially be in vicinity of each origin and destination
            if not origin_in_vicinity_at or not destination_in_vicinity_at:
                # if either no stop is in vicinity for origin or destination, return no viable stops
                return {}
            else:
                # otherwise return a dict of viable stops for origin and destination
                return {
                    "origin": [
                        vehicle.route.route_stop_by_id(ix)
                        for ix in origin_in_vicinity_at
                    ],
                    "destination": [
                        vehicle.route.route_stop_by_id(ix)
                        for ix in destination_in_vicinity_at
                    ],
                }
        else:
            raise NotImplementedError(
                "Other strategies for aligning travel demands are not implemented."
            )

    def _reachable_in_time(  # noqa: ANN202
        self,
        stop: Stop,
        vehicle: PublicTransitVehicle,
        current_time,  # noqa: ANN001
        current_position: GeodesicPosition,
        latest_departure,  # noqa: ANN001
    ):
        walking_dist = stop >> current_position
        # reachable within the specified temporal_lookahead and depart after arrival by foot
        reachable = (
            SimulationTimeConverter.as_str(
                current_time + (walking_dist / self._user_config.WALKING_SPEED)
            )
            <= vehicle.prognose_arrival(stop)
            <= latest_departure
        )
        return reachable, walking_dist
