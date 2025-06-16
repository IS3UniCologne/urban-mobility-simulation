import logging

import pandas as pd
import simpy

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.time import SimulationTime
from simulation.infrastructure.route import PublicTransitRoute
from simulation.infrastructure.transit_network.route_segment import RouteSegment
from simulation.infrastructure.transit_network.stop import Stop
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.public_transport_vehicle_fleet import (
    PublicTransportVehicleFleet,
)
from simulation.world.world import World
from tracking.tracking import Tracking


class OperationsPublicTransport(OperationsInterface):
    __slots__ = (
        "_bus_velocity",
        "_config",
        "_fleet",
        "_geodesic_env",
        "_operator_config",
        "_time",
        "_timetable",
        "_tracking",
        "_walking_speed",
        "_world",
    )

    def __init__(self, env, timetable, fleet: PublicTransportVehicleFleet):  # noqa: ANN001, ANN204
        super(OperationsPublicTransport, self).__init__(env=env)  # noqa: UP008
        self._env = env
        self._timetable = timetable
        self._time = SimulationTime(env)
        self._fleet = fleet

        # Config
        self._config = Configuration()
        self._operator_config = self._config.transit_operators[
            0
        ]  # TODO: This should not be hardcoded, pass an operator object instead
        # Environment
        self._geodesic_env = GeodesicEnvironment.getInstance()
        self._world = (
            None  # defer loading to run process, otherwise circular dependency
        )
        # Tracking
        self._tracking = (
            None  # defer loading to run process, otherwise circular dependency
        )
        self._walking_speed = self._config.user.WALKING_SPEED
        self._bus_velocity = self._config.transit_vehicles["Bus"].VELOCITY

    def execute(self):  # noqa: ANN201
        """
        TransitOperator Lifecycle
        """
        self._world = World.instance()
        self._tracking = Tracking.instance()

        while True:
            try:
                logging.debug(
                    "TransitOperator is at time %s",
                    self._time.now_as_str(),
                    extra={"clazz": self.__class__.__name__, "oid": ""},
                )

                if len(self._fleet._busses) < self._operator_config.MAX_BUSSES:  # noqa: SLF001
                    trips = self._timetable.next_trips(
                        self._time, self._operator_config.PLANNING_LOOKAHEAD
                    )

                    if trips:  # non-empty list is True
                        # spawn busses only for trips that are not yet spawned
                        # TODO: can there be a case of overlapping trips with the same trip id? i.e. extreme delay?
                        for trip_id in (
                            t
                            for t in trips
                            if t not in [b.route.trip_id for b in self._fleet._busses]  # noqa: SLF001
                        ):
                            trip = self._timetable.trip_by_id(trip_id)
                            route = self._build_route(trip)
                            bus = self._fleet.spawn_bus(route)

                            # also spawn a cleanup process that waits for completion of trip
                            self._env.process(self._fleet.clean_up_bus(bus))

                            if (
                                len(self._fleet.get_busses())
                                >= self._operator_config.MAX_BUSSES
                            ):
                                break

                yield self._env.timeout(1)
            except simpy.Interrupt:
                # quit this process
                break

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
