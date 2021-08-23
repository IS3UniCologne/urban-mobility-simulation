import datetime
import logging
import geopandas as gpd
import pandas as pd

from simpy import Environment
from simulation.infrastructure.helper.timetable import Timetable
from simulation.helper.time import SimulationTime
from simulation.vehicle.public_transit_bus import Bus
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicleState
from simulation.infrastructure.route import PublicTransitRoute
from simulation.infrastructure.transit_network.stop import Stop
from simulation.infrastructure.transit_network.route_segment import RouteSegment
from simulation.environment.geodesic_position import GeodesicPosition


class TransitOperator:
    def __init__(self, env: Environment, timetable: Timetable):
        self._timetable = timetable
        self._env = env
        self._time = SimulationTime(env)
        self._busses = []

        self._process = self._env.process(self._run())

    def _run(self):
        """
        TransitOperator Lifecycle
        """
        while True:
            logging.debug(f'TransitOperator is at time {self._time.now_as_str()}',
                          extra={"clazz": self.__class__.__name__, "oid": ""})

            spawned = self._env.event()

            trips = self._timetable.next_trips(self._time)
            # non-empty list is True
            if trips:
                for trip_id in trips:
                    trip = self._timetable.trip_by_id(trip_id)
                    route = self._build_route(trip)
                    self._spawn_bus(route)

            yield spawned.succeed()

            yield self._env.timeout(1)

    def _build_route(self, trip: pd.DataFrame) -> PublicTransitRoute:
        origin_row = trip.iloc[0]
        destination_row = trip.iloc[-1]

        origin = Stop(0, origin_row['stop_id'], origin_row['stop_lat'], origin_row['stop_lon'])
        destination = Stop(len(trip.index)-1, destination_row['stop_id'], destination_row['stop_lat'], destination_row['stop_lon'])

        route_id = origin_row['route_id']
        trip_id = origin_row['trip_id']

        # create route prototype with OD and add first stop
        route = PublicTransitRoute(origin, destination, route_id, trip_id)
        route.add_route_stop(origin)

        last_stop = origin
        total_traveled = 0

        # skip origin as it is already added
        for stop_id, row in enumerate(trip[1:].itertuples(index=False), start=1):
            stop = Stop(stop_id, row.stop_id, row.stop_lat, row.stop_lon)
            # Actual distance traveled along the associated shape, from the first stop to the stop specified in this record
            distance = row.shape_dist_traveled - total_traveled

            route_segment = RouteSegment(stop_id-1, last_stop, stop, distance)

            # add route segment and next stop
            route.add_route_segment(route_segment)
            route.add_route_stop(stop)

            last_stop = stop
            total_traveled += distance

        return route

    def _spawn_bus(self, route: PublicTransitRoute):
        init_position = GeodesicPosition(*route.origin.getExactLocation())
        bus = Bus(self._env, route, init_position)
        bus.current_stop = route.origin # TODO: move to Bus/PublicTransitVehicle?
