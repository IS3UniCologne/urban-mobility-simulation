import logging
from copy import deepcopy
from datetime import datetime
import h3
import simpy
from simpy import Environment
from enum import Enum

from simulation.agent.action_space import ActionSpace
from simulation.agent.episodic_semi_gradient_sarsa import reward_bus, policy, vectorize_state, ValueFunctionApproximator
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

    def __init__(self, env: Environment, route: PublicTransitRoute, position: GeodesicPosition,
                 q_hat: ValueFunctionApproximator, max_available_seats=100, velocity=833.33):
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
        self._action_taken = self._env.event()
        self._agent_completed_step = self._env.event()

        # Environment / World state
        self._geodesic_env = GeodesicEnvironment.getInstance()
        self._world = World.instance()
        self._env_state = {
            'd_terminal': self._route.destination.difference(self._position)
            # 'passengers': [{'d_destination': self._position.difference(x.transport_task.destination),
            #                 'time': x.available_time} for x in self._seats],
            # 'demand': [{'d_origin': self._position.difference(x.transport_task.origin),
            #             'd_destination': self._position.difference(x.transport_task.destination),
            #             'time': x.available_time} for x in self._world.users
            #            if x.state is TransitUserState.SEARCHING_TRANSPORT_ALTERNATIVES],
            # 'delay': self._delay
        }

        # Action space
        self._action_space = ActionSpace.instance()

        # Rewards
        self._reward = 0
        self._reward_cum = 0

        # Value function
        self._q_hat = q_hat

        # Config
        self._config = Configuration.instance()
        self._eps = self._config.transit_agent_config.eps  # epsilon for e-greedy action selection
        self._gamma = self._config.transit_agent_config.gamma  # discount rate
        self._alpha = self._config.transit_agent_config.alpha # step size for updates

        self._process = self._env.process(self._run_agent())
        self._state_update_process = self._env.process(self._update_state())

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
                self._delay = 0  # reset delay
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

        while not self._state == BusState.AT_TERMINAL_DESTINATION:
            # to get a value copy of a state we need to deepcopy, otherwise modifying self._env_state results in
            # modifying the "copy" which really is just a reference
            before_state = deepcopy(self._env_state)
            self._env.process(self._update_reward(before_state))
            action = yield self._env.process(self._take_action())

            s = vectorize_state(before_state)
            s_ = vectorize_state(self._env_state)
            a = self._action_space.action_as_binary_vector(action)
            if self._state is BusState.AT_TERMINAL_DESTINATION:
                # update weights
                self._q_hat.weights = self._q_hat.weights + \
                                      self._alpha * (self._reward -
                                                     self._q_hat.evaluate_value(s, a)) * \
                                      self._q_hat.evaluate_gradient(s, a)
                # and go to next episode
                break

            a_ = self._action_space.action_as_binary_vector(policy(s_, self._q_hat, self._eps))

            # update weights based on semi gradient sarsa
            self._q_hat.weights = self._q_hat.weights + \
                                  self._alpha * (self._reward +
                                                 self._gamma * self._q_hat.evaluate_value(s_, a_) -
                                                 self._q_hat.evaluate_value(s, a)) * self._q_hat.evaluate_gradient(s, a)

        # clean up processes
        self._state_update_process.interrupt()

        # and let the operator know
        self._has_reached_destination.succeed()

    def _take_action(self):
        """
        Actions in hexagonal grid, stay is also allowed.

                     up
                     __
        up-left    /    \  up-right
        down-left  \ __ /  down-right
                    down

        """

        new_centroid = None

        while True:
            action = policy(vectorize_state(self._env_state), self._q_hat, self._eps)

            hex_id = h3.geo_to_h3(*self._position.getExactLocation(),
                                  resolution=self._config.transit_agent_config.action_resolution)

            if action == 'STAY':
                break
            else:
                new_hex = self._geodesic_env.move_in_layer(hex_id, action)
                try:
                    new_centroid = self._geodesic_env.get_centroid(new_hex,
                                                                   f'hex_{self._config.transit_agent_config.action_resolution}')
                except KeyError:
                    # hexagon is out of layer bounding box - action is forbidden
                    logging.debug(f'Action {action} is forbidden, sampling again',
                                  extra={"clazz": self.__class__.__name__, "oid": self._id})
                    continue
                break

        logging.debug(f'Bus takes action {action}',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

        if new_centroid is None:
            yield self._env.timeout(.01)
        else:
            new_position = GeodesicPosition(*new_centroid)

            distance = self._position >> new_position
            duration = distance / self._velocity  # in minutes

            self._state = BusState.EN_ROUTE_DETOUR

            yield self._env.timeout(duration)

            self._update_positions(new_position)

        self._action_taken.succeed(action)
        self._action_taken = self._env.event()

        return action

    def _move_to_next_stop(self):
        route_segment = self._route.route_segment_by_id(self._current_stop.stop_id)
        yield self._env.process(self.move(route_segment))

    def move(self, route_segment: RouteSegment):
        # TODO: use road network speed limits?

        distance = route_segment.distance  # in meter
        duration = distance / self._velocity  # in minutes

        self._state = BusState.EN_ROUTE_PLANNED

        logging.debug(
            f'Bus has started driving from stop {route_segment.start.stop_id} to stop {route_segment.end.stop_id}.',
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

        region_id, _ = self._position.get_hexagon(self._config.transit_agent_config.action_resolution)

        logging.debug(f'Current position {self._position} in region {region_id}.',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    @property
    def env_state(self):
        return self._env_state

    def _update_state(self):
        """
        We need:
        - Distance to terminal destination
        - Passengers [{distance to destination, remaining wait/walk}, ...]
        - Demands [{distance to origin, distance to destination, wait/walk}, ...]
        - Delay

        which represents the most complete picture of the environment/world the agent has at the moment
        """

        # wait for external (world) or self (position) change
        while True:
            try:
                # TODO incorporate external change here or somewhere else again
                # yield simpy.events.AnyOf(self._env, [self._position_changed, self._world.changed])
                yield self._position_changed

                self._env_state['d_terminal'] = self._route.destination.difference(self._position)
                # self._env_state['passengers'] = [{'d_destination': self._position.difference(x.transport_task.destination),
                #                                   'time': x.available_time} for x in self._seats]
                # self._env_state['demand'] = [{'d_origin': self._position.difference(x.transport_task.origin),
                #                               'd_destination': self._position.difference(x.transport_task.destination),
                #                               'time': x.available_time} for x in self._world.users
                #                              if x.state is TransitUserState.SEARCHING_TRANSPORT_ALTERNATIVES]
                # self._env_state['delay'] = self._delay

                region_id, _ = self._position.get_hexagon(self._config.transit_agent_config.action_resolution)

                if region_id == \
                        self._route.destination.get_hexagon(self._config.transit_agent_config.action_resolution)[0]:
                    self._state = BusState.AT_TERMINAL_DESTINATION
                    logging.info(f'Bus has arrived at its terminal destination at time {self._time.now_as_str()}',
                                 extra={"clazz": self.__class__.__name__, "oid": self._id})
            except simpy.Interrupt:
                # stop process loop
                break

    def _update_reward(self, before_state):

        # wait for action
        action = yield self._action_taken

        self._reward = reward_bus(self._env_state, self._state == BusState.AT_TERMINAL_DESTINATION)
        self._reward_cum = self._reward_cum + self._reward

        logging.debug(f'Current reward: {self._reward}, overall reward: {self._reward_cum}',
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

        self._agent_completed_step.succeed((before_state, action, self._reward, self._reward_cum))
        self._agent_completed_step = self._env.event()

    @property
    def reward(self):
        return self._reward

    @property
    def reward_sum(self):
        return self._reward_cum

    def __str__(self):
        return f'I have {len(self._seats)} passengers on boards'
