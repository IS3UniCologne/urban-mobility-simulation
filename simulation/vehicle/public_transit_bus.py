import logging
from datetime import datetime

from simpy import Environment
from enum import Enum

from simulation.agent.action_space import ActionSpace
from simulation.agent.user import TransitUserState
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.transit_network.route_segment import RouteSegment
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle, PublicTransitVehicleState
from simulation.infrastructure.route import PublicTransitRoute
from simulation.helper.time import SimulationTime, SimulationTimeConverter
from simulation.world.world import World


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
        self._has_reached_destination = self._env.event()

        # Environment / World state
        self._geodesic_env = GeodesicEnvironment.getInstance()
        self._world = World.instance()
        self._env_state = {}

        # Action space
        self._action_space = ActionSpace.instance()

        # Config
        self._config = Configuration.instance()

        self._process = self._env.process(self._run_agent())

    def _run(self):
        """
        Bus Lifecycle

        Time 12:00:00 - Departure 12:10:00 - wait
        Time 23:59:00 - Departure 00:06:00 - next_day = True - wait
        Time 00:03:00 - Departure 00:04:00 - next_day = False - wait
        Time 00:03:00 - Departure 00:04:00 - next_day = True - should not happen
        """
        while self._state is not BusState.AT_TERMINAL_DESTINATION:

            self._env.process(self._update_env_state())

            strf = '%H:%M:%S'
            early_arrival = (self._time.now_as_str() < self._current_stop.departure and
                             not self._current_stop.departure_next_day) or \
                            (self._time.now_as_str() > self._current_stop.departure and
                             self._current_stop.departure_next_day)

            if self._state is BusState.AT_TERMINAL_ORIGIN and self._time.now_as_str() < self._current_stop.departure:
                # bus was pre-initialized by transit operator
                wait = SimulationTimeConverter.duration_between(self._time.now_as_str(strf),
                                                                self._current_stop.departure, strf)
                logging.debug(f'Bus waits for scheduled departure from terminal origin',
                              extra={"clazz": self.__class__.__name__, "oid": self._id})
                yield self._env.timeout(wait)

            elif early_arrival:
                # if the bus has reached the planned stop earlier, wait
                wait = SimulationTimeConverter.duration_between(self._time.now_as_str(strf),
                                                                self._current_stop.departure, strf,
                                                                self._current_stop.departure_next_day)
                logging.debug(f'Bus is ahead of schedule and will wait for scheduled departure.',
                              extra={"clazz": self.__class__.__name__, "oid": self._id})
                self._delay = 0 # reset delay
                yield self._env.timeout(wait)

            elif self._time.now_as_str() > self._current_stop.departure and not self._current_stop.departure_next_day:
                # if the bus has reached the planned stop late, set delay
                diff = datetime.strptime(self._time.now_as_str(strf), strf) - \
                       datetime.strptime(self._current_stop.departure, strf)
                self._delay = diff.total_seconds()

            # otherwise move on with driving
            yield self._env.process(self._move_to_next_stop())

        self._has_reached_destination.succeed()

    def _run_agent(self):
        while self._state is not BusState.AT_TERMINAL_DESTINATION:

            self._env.process(self._update_env_state())
            yield self._env.process(self._take_action())

    def _take_action(self):
        """
        Actions in hexagonal grid, stay is also allowed.

                     up
                     __
        up-left    /    \  up-right
        down-left  \ __ /  down-right
                    down

        Here, and only here is the following mapping between the hex above and below guaranteed:
              ___0___
           /           \
         /5/          \1\
                hex
         \4\          /2/
          \  ________  /
                3

        Because h3 cells are never oriented the same way across the globe, we need to hack around the fact that there
        are no directed neighbors. We do this by moving in one of six directions, which are equally spaced from each
        other. We assume to be in the middle of the cell and move the current resolution's edge length in one direction.
        This should be sufficient to "be in the next cell". To be in the exact middle of that cell we do a final geotoh3
        and h3togeo hicky-hacky conversion. Because we do not really care if up always means up in a sense of north, as
        long as it always goes to the same direction, the described methodology is sufficient.

        """

        ACTION_SPACE_MAPPING = {
            'UP': 0,
            'UP_RIGHT': 1,
            'DOWN_RIGHT': 2,
            'DOWN': 3,
            'DOWN_LEFT': 4,
            'UP_LEFT': 5
        }

        action = self._action_space.sample_action()
        logging.debug(f'Bus takes action {action}')

        try:
            hex_id = self._position.get_default_hexagon()
        except AttributeError:
            hex_id, _ = self._position.get_hexagon(resolution=self._config.transit_agent_config.action_resolution)

        if action == 'STAY':
            yield self._env.timeout(.01)
        else:
            try:
                movement = ACTION_SPACE_MAPPING[action]
            except KeyError:
                raise Exception('non-permitted action, check action space config')

            new_hex = self._geodesic_env.move_in_layer(hex_id, movement)
            new_centroid = self._geodesic_env.get_centroid(new_hex, f'hex_{self._config.transit_agent_config.action_resolution}')
            new_position = GeodesicPosition(*new_centroid)

            distance = self._position >> new_position
            duration = distance / self._velocity # in minutes

            self._state = BusState.EN_ROUTE_DETOUR

            yield self._env.timeout(duration)

            self._update_positions(new_position)

    def _move_to_next_stop(self):
        route_segment = self._route.route_segment_by_id(self._current_stop.stop_id)
        yield self._env.process(self.move(route_segment))

    def move(self, route_segment: RouteSegment):
        # TODO: use road network speed limits?

        distance = route_segment.distance # in meter
        duration = distance / self._velocity # in minutes

        self._state = BusState.EN_ROUTE_PLANNED

        logging.debug(f'Bus has started driving from stop {route_segment.start.stop_id} to stop {route_segment.end.stop_id}.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

        yield self._env.timeout(duration)

        self._current_stop = route_segment.end
        self._update_positions(route_segment.end)

        if self._current_stop == self._route.destination:
            self._state = BusState.AT_TERMINAL_DESTINATION
            logging.debug(f'Bus has arrived at its terminal destination - stop {self._current_stop.stop_id} '
                          f'at time {self._time.now_as_str()}',
                          extra={"clazz": self.__class__.__name__, "oid": self._id})
        else:
            self._state = BusState.AT_STOP
            logging.debug(f'Bus has arrived at stop {self._current_stop.stop_id} at time {self._time.now_as_str()}',
                          extra={"clazz": self.__class__.__name__, "oid": self._id})

    def _update_positions(self, new_position):
        # Update Vehicle Position
        self.position = new_position

        # Update Position of Passengers
        for passenger in self._seats:
            passenger.position = new_position

        region_id, _ = self._position.get_hexagon()

        logging.debug(f'Current position {self._position} in region {region_id}.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    @property
    def env_state(self):
        return self._env_state

    def _update_env_state(self):
        """
        We need:
        - Distance to terminal destination
        - Passengers [{distance to destination, remaining wait/walk}, ...]
        - Demands [{distance to origin, distance to destination, wait/walk}, ...]
        - Delay

        which represents the most complete picture of the environment/world the agent has at the moment
        """

        # wait for external (world) or self (position) change
        yield self._world.changed | self._position_changed

        self._env_state['d_terminal'] = self._route.destination.difference(self._position)
        self._env_state['passengers'] = [{'d_destination': self._position.difference(x.transport_task.destination),
                                          'time': x.available_time} for x in self._seats]
        self._env_state['demand'] = [{'d_origin': self._position.difference(x.transport_task.origin),
                                      'd_destination': self._position.difference(x.transport_task.destination),
                                      'time': x.available_time} for x in self._world.users
                                     if x.state is TransitUserState.SEARCHING_TRANSPORT_ALTERNATIVES]
        self._env_state['delay'] = self._delay

    def __str__(self):
        return f'I have {len(self._seats)} passengers on boards'
