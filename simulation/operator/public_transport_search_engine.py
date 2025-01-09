import logging

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.time import SimulationTimeConverter
from simulation.infrastructure.transit_network.stop import Stop
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transportation_search_task import TransportationSearchTask
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle


class PublicTransportSearchEngine(SearchEngineInterface):
    def __init__(self, env):
        self._env = env
        self._fleet = None
        self._busses = []
        self._config = Configuration.instance()
        self._operator_config = self._config.transit_operator_config
        self._user_config = self._config.user_config

    def register_fleet(self, fleet: VehicleFleet):
        pass

    def register_bus(self, bus):
        self._busses.append(bus)

    def find_viable_transit(
        self,
        transportation_search_task,
        spatial_strategy="hexagon",
        temporal_lookahead=10,
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

        if not self._busses:
            # No busses are en-route, report no viable alternative
            # TODO: fallback to timetable if temporal_lookahead > transit operator planning window?
            if temporal_lookahead > self._operator_config.planning_lookahead:
                raise NotImplementedError(
                    "temporal lookahead of user > planning lookahead of operator currently not supported"
                )

        for vehicle in self._busses:
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
                    logging.debug(
                        f"Bus {vehicle.id} is a viable transport alternative from "
                        f"{transportation_search_task.transport_task.origin} to "
                        f"{transportation_search_task.transport_task.destination}!",
                        extra={"clazz": self.__class__.__name__, "oid": ""},
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
            self._user_config.spatial_strategy,
            self._user_config.max_wait,
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
            ) + (walking_dist_to_destination / self._user_config.walking_speed)

            # TODO: convenience=0 is only a placeholder
            transportation_alternative = TransportationAlternative(
                vehicle, subroute, price, duration, distance, 0
            )
            browser.add_transportation_alternative(transportation_alternative)

        return browser

    @staticmethod
    def _check_viable_stops(
        vehicle: PublicTransitVehicle,
        strategy,
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
            origin_hex, origin_poly = origin.get_hexagon()
            destination_hex, destination_poly = destination.get_hexagon()
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

    def _reachable_in_time(
        self,
        stop: Stop,
        vehicle: PublicTransitVehicle,
        current_time,
        current_position: GeodesicPosition,
        latest_departure,
    ):
        walking_dist = stop >> current_position
        # reachable within the specified temporal_lookahead and depart after arrival by foot
        reachable = (
            SimulationTimeConverter.as_str(
                current_time + (walking_dist / self._user_config.walking_speed)
            )
            <= vehicle.prognose_arrival(stop)
            <= latest_departure
        )
        return reachable, walking_dist
