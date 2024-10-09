import logging

import pandas as pd
import simpy

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.time import SimulationTime, SimulationTimeConverter
from simulation.infrastructure.route import PublicTransitRoute
from simulation.infrastructure.transit_network.route_segment import RouteSegment
from simulation.infrastructure.transit_network.stop import Stop
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.vehicle.public_transit_bus import Bus
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle
from simulation.world.world import World
from tracking.tracking import Tracking

# Move to config
walking_speed_in_mpm = 5
grace_period = 10  # in minutes?


class OperationsPublicTransport(OperationsInterface):
    def __init__(self, env, timetable):
        super(OperationsPublicTransport, self).__init__(env=env)
        self._env = env
        self._timetable = timetable
        self._busses = []
        self._time = SimulationTime(env)
        # Config
        self._config = Configuration.instance()
        self._operator_config = self._config.transit_operator_config
        # Environment
        self._geodesic_env = GeodesicEnvironment.getInstance()
        self._world = (
            None  # defer loading to run process, otherwise circular dependency
        )
        # Tracking
        self._tracking = (
            None  # defer loading to run process, otherwise circular dependency
        )

    def execute(self):
        """
        TransitOperator Lifecycle
        """
        self._world = World.instance()
        self._tracking = Tracking.instance()

        while True:
            try:
                logging.debug(
                    f"TransitOperator is at time {self._time.now_as_str()}",
                    extra={"clazz": self.__class__.__name__, "oid": ""},
                )

                if len(self._busses) < self._operator_config.max_busses:
                    trips = self._timetable.next_trips(
                        self._time, self._operator_config.planning_lookahead
                    )

                    if trips:  # non-empty list is True
                        # spawn busses only for trips that are not yet spawned
                        # TODO: can there be a case of overlapping trips with the same trip id? i.e. extreme delay?
                        for trip_id in (
                            t
                            for t in trips
                            if t not in [b.route.trip_id for b in self._busses]
                        ):
                            trip = self._timetable.trip_by_id(trip_id)
                            route = self._build_route(trip)
                            bus = self._spawn_bus(route)

                            # also spawn a cleanup process that waits for completion of trip
                            self._env.process(self._clean_up_bus(bus))

                            if len(self._busses) >= self._operator_config.max_busses:
                                break

                yield self._env.timeout(1)
            except simpy.Interrupt:
                # quit this process
                break

    # Add the bus
    def _spawn_bus(self, route: PublicTransitRoute):
        init_position = GeodesicPosition(*route.origin.getExactLocation())

        bus = Bus(
            env=self._env, route=route, position=init_position, use_learning_agent=False
        )

        self._busses.append(bus)
        self._world.add_vehicle(bus)

        self._tracking.register(bus)

        return bus

    def _build_route(self, trip: pd.DataFrame) -> PublicTransitRoute:
        origin_row = trip.iloc[0]
        destination_row = trip.iloc[-1]

        origin = Stop(
            0,
            origin_row["stop_id"],
            origin_row["stop_lat"],
            origin_row["stop_lon"],
            origin_row["departure_time"],
            origin_row["dep_next_day"],
        )
        destination = Stop(
            len(trip.index) - 1,
            destination_row["stop_id"],
            destination_row["stop_lat"],
            destination_row["stop_lon"],
            destination_row["departure_time"],
            destination_row["dep_next_day"],
        )

        route_id = origin_row["route_id"]
        trip_id = origin_row["trip_id"]

        # create route prototype with OD and add first stop
        route = PublicTransitRoute(origin, destination, route_id, trip_id)
        route.add_route_stop(origin)

        last_stop = origin
        total_traveled = 0

        # skip origin as it is already added
        for stop_id, row in enumerate(trip[1:].itertuples(index=False), start=1):
            stop = Stop(
                stop_id,
                row.stop_id,
                row.stop_lat,
                row.stop_lon,
                row.departure_time,
                row.dep_next_day,
            )

            # Actual distance traveled along the associated shape, from the first stop to the stop specified in this record
            distance = row.shape_dist_traveled - total_traveled

            route_segment = RouteSegment(stop_id - 1, last_stop, stop, distance)

            # add route segment and next stop
            route.add_route_segment(route_segment)
            route.add_route_stop(stop)

            last_stop = stop
            total_traveled += distance

        return route

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

    @staticmethod
    def _reachable_in_time(
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
                current_time + (walking_dist / walking_speed_in_mpm)
            )
            <= vehicle.prognose_arrival(stop)
            <= latest_departure
        )
        return reachable, walking_dist

    def _clean_up_bus(self, bus: Bus):
        yield bus._has_reached_terminal

        self._busses.remove(bus)
        self._world.remove_vehicle(bus)
        self._tracking.unregister_by_obj(bus)

        # Check this again, what happens when the trip time is over but there are still passengers in the bus?
        # TODO: unmount all remaining passengers - is there a need for this?
        logging.debug(
            f"There are still {str(len(bus._seats))} passengers onboard the bus",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
        self._unserved_passengers = len(bus._seats)
