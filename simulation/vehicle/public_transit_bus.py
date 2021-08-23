import logging
from simpy import Environment
from enum import Enum

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.infrastructure.transit_network.route_segment import RouteSegment
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle, PublicTransitVehicleState
from simulation.infrastructure.route import PublicTransitRoute
from simulation.helper.time import SimulationTime


class BusState(PublicTransitVehicleState, Enum):
    EN_ROUTE_PLANNED = 2011
    EN_ROUTE_DETOUR = 2012


class Bus(PublicTransitVehicle):

    bus_id = 0

    def __init__(self, env: Environment, route: PublicTransitRoute, position: GeodesicPosition, max_available_seats=100, velocity = 833.33):
        """

        :param env:
        :param position: GeodesicPosition
        :param max_available_seats: depends on type of bus - TODO: see SVG busses
        :param velocity: 16.67 m/min * 50 (city limit)
        """
        super(Bus, self).__init__(env, route, position, max_available_seats, velocity)

        self._id = Bus.bus_id
        self._time = SimulationTime(self._env)
        Bus.bus_id += 1

        # Events
        # self._has_reached_destination = self._env.event()

        self._process = self._env.process(self._run())

    def _run(self):
        """
        Bus Lifecycle
        """
        while self._state is not BusState.AT_TERMINAL_DESTINATION:
            logging.debug(f'Bus is at stop {self._current_stop.stop_id} at time {self._time.now_as_str()}',
                          extra={"clazz": self.__class__.__name__, "oid": self._id})

            yield self._env.process(self._move_to_next_stop())

        # yield self._has_reached_destination.succeed()

    def _move_to_next_stop(self):
        route_segment = self._route.route_segment_by_id(self._current_stop.stop_id)
        yield self._env.process(self.move(route_segment))

    def move(self, route_segment: RouteSegment):
        # TODO: use road network speed limits?

        distance = route_segment.distance # in meter
        velocity = self._velocity # in meter / minute
        time = distance / velocity # in minutes

        self._state = BusState.EN_ROUTE_PLANNED

        yield self._env.timeout(time)

        self._update_positions(route_segment.end)
        self._current_stop = route_segment.end
        if self._current_stop == self._route.destination:
            self._state = BusState.AT_TERMINAL_DESTINATION
        else:
            self._state = BusState.AT_STOP

    def _update_positions(self, new_position):
        # Update Vehicle Position
        self._position = new_position

        # Update Position of Passengers
        for passenger in self._seats:
            passenger.position = new_position

        region_id, _ = self._position.get_hexagon()

        logging.debug(f'Current position {self._position} in region {region_id}.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def __str__(self):
        return f'I have {len(self._seats)} passengers on boards'
